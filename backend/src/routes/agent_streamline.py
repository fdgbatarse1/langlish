import json
import base64
import asyncio
import uuid
from typing import Dict, Any, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets
import aiohttp
from src.config import OPENAI_API_KEY
from src.services.s3_service import s3_service
from src.utils.audio import convert_webm_to_pcm16, convert_pcm16_to_webm

# LangGraph imports
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from typing import Annotated

OPENAI_WS_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
)

agent_realtime_router = APIRouter()


async def fetch_dictionary_definition(word: str) -> Dict[str, Any]:
    """
    Fetch word definition from the free dictionary API.
    
    Args:
        word: The word to look up
        
    Returns:
        Dictionary containing definition data or error info
    """
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}"
    print(f"📖 Calling dictionary API for word: {word}")
    print(f"🌐 URL: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                print(f"📡 Dictionary API response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        entry = data[0]
                        # Extract key information
                        meanings = entry.get("meanings", [])
                        phonetics = entry.get("phonetics", [])
                        
                        # Get first definition and example
                        definition = ""
                        example = ""
                        if meanings:
                            if meanings[0].get("definitions"):
                                definition = meanings[0]["definitions"][0].get("definition", "")
                                example = meanings[0]["definitions"][0].get("example", "")
                        
                        # Get audio URL if available
                        audio_url = ""
                        for phonetic in phonetics:
                            if phonetic.get("audio"):
                                audio_url = phonetic["audio"]
                                break
                        
                        print(f"✅ Found definition for '{word}': {definition[:50]}...")
                        return {
                            "found": True,
                            "word": word,
                            "definition": definition,
                            "example": example,
                            "audio_url": audio_url
                        }
                else:
                    print(f"❌ Word '{word}' not found in dictionary")
                    return {"found": False, "word": word, "error": "Word not found"}
                    
    except asyncio.TimeoutError:
        print(f"⚠️ Dictionary API timeout for word: {word}")
        return {"found": False, "word": word, "error": "Request timeout"}
    except Exception as e:
        print(f"🔴 Dictionary API error: {e}")
        return {"found": False, "word": word, "error": str(e)}


# LangGraph State Definition
class ConversationState(TypedDict):
    """State for the conversation workflow"""
    websocket: WebSocket
    session_id: str
    openai_ws: Any
    audio_buffer_size: int
    response_active: bool
    user_audio_buffer: List[bytes]
    assistant_audio_buffer: List[bytes]
    completed: bool
    user_transcript: str  # Track user's speech transcript
    dictionary_word: str  # Word to look up in dictionary
    needs_dictionary: bool  # Flag to check if dictionary lookup is needed


# Create the LangGraph workflow
def create_langlish_workflow():
    """Create the LangGraph workflow for Langlish agent"""
    workflow = StateGraph(ConversationState)
    
    # Add the langlish node
    workflow.add_node("langlish", langlish_node)
    
    # Define the flow: START -> langlish -> END
    workflow.set_entry_point("langlish")
    workflow.add_edge("langlish", END)
    
    return workflow.compile()


async def langlish_node(state: ConversationState) -> ConversationState:
    """
    Langlish node that manages the OpenAI Realtime WebSocket connection.
    This node encapsulates the existing OpenAI Realtime logic.
    """
    websocket = state["websocket"]
    session_id = state["session_id"]
    
    openai_ws = None
    audio_buffer_size = state["audio_buffer_size"]
    response_active = state["response_active"]
    user_audio_buffer = state["user_audio_buffer"]
    assistant_audio_buffer = state["assistant_audio_buffer"]
    
    try:
        print("🔗 Connecting to OpenAI WebSocket...")
        openai_ws = await websockets.connect(
            OPENAI_WS_URL,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1",
            },
        )
        print("✅ Connected to OpenAI WebSocket")

        print("📝 Sending session configuration...")
        session_config: Dict[str, Any] = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True,
                },
                "instructions": (
                    "You are Langlish, a friendly and patient English learning "
                    "assistant. You help students improve their English through "
                    "conversation practice. Your role is to: help the user practice "
                    "english conversation, correct grammar mistakes gently, suggest "
                    "better vocabulary when appropriate, encourage the student, and "
                    "adapt to the student's level. When you receive dictionary "
                    "information, explain it in a clear and educational way."
                ),
            },
        }
        await openai_ws.send(json.dumps(session_config))
        print("✅ Session configuration sent")

        async def handle_client_messages() -> None:
            """
            Handle messages from the frontend client.

            Processes incoming WebM audio data and text messages, converts audio
            to PCM16 format, and sends to OpenAI. Handles EOF signals to trigger
            response generation.

            Returns:
                None
            """
            nonlocal audio_buffer_size, response_active, user_audio_buffer

            try:
                while True:
                    message = await websocket.receive()

                    if "bytes" in message:
                        webm_data = message["bytes"]
                        audio_buffer_size += len(webm_data)

                        # Store original WebM data for S3
                        user_audio_buffer.append(webm_data)

                        print(
                            f"📨 Received WebM audio: {len(webm_data)} bytes "
                            f"(total: {audio_buffer_size} bytes)"
                        )

                        pcm_data = convert_webm_to_pcm16(webm_data)
                        if pcm_data:
                            audio_b64 = base64.b64encode(pcm_data).decode("utf-8")

                            await openai_ws.send(
                                json.dumps(
                                    {
                                        "type": "input_audio_buffer.append",
                                        "audio": audio_b64,
                                    }
                                )
                            )
                            print(
                                f"📤 Sent PCM16 audio to OpenAI ({len(pcm_data)} bytes)"
                            )
                        else:
                            print("🔴 Audio conversion failed, skipping chunk")
                    elif "text" in message:
                        try:
                            data = json.loads(message["text"])
                            if data.get("type") == "EOF" and not response_active:
                                print(
                                    f"🛑 Received EOF with {audio_buffer_size} bytes "
                                    f"of total audio"
                                )

                                # Save user audio to S3 if available
                                if user_audio_buffer and s3_service:
                                    try:
                                        combined_audio = b"".join(user_audio_buffer)
                                        s3_url = await asyncio.to_thread(
                                            s3_service.upload_audio,
                                            audio_data=combined_audio,
                                            file_name=f"{session_id}_user.webm",
                                            content_type="audio/webm",
                                            metadata={
                                                "session_id": session_id,
                                                "audio_type": "user_input",
                                                "size_bytes": str(len(combined_audio)),
                                            },
                                        )
                                        if s3_url:
                                            print(
                                                f"💾 User audio saved to S3: {s3_url}"
                                            )
                                        else:
                                            print("⚠️ Failed to save user audio to S3")
                                    except Exception as e:
                                        print(f"🔴 Error saving user audio to S3: {e}")

                                # Clear user audio buffer
                                user_audio_buffer = []

                                if audio_buffer_size > 5000:
                                    response_active = True
                                    await openai_ws.send(
                                        json.dumps(
                                            {"type": "input_audio_buffer.commit"}
                                        )
                                    )
                                    await openai_ws.send(
                                        json.dumps(
                                            {
                                                "type": "response.create",
                                                "response": {
                                                    "modalities": ["audio", "text"]
                                                },
                                            }
                                        )
                                    )
                                    print("📤 Sent audio-based response request")
                                else:
                                    print("⚠️ Not enough audio data, skipping response")

                                audio_buffer_size = 0

                        except json.JSONDecodeError:
                            print(f"📝 Non-JSON text message: {message['text']}")

            except WebSocketDisconnect:
                print("🔴 Client disconnected")
            except Exception as e:
                print(f"🔴 Error handling client messages: {e}")

        async def handle_openai_responses() -> None:
            """
            Handle responses from OpenAI and send to frontend.

            Processes incoming events from OpenAI WebSocket, including audio deltas,
            text deltas, completion signals, and error messages. Forwards audio
            data to client and manages response state.

            Returns:
                None
            """
            nonlocal response_active, assistant_audio_buffer

            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type", "")

                    print(f"📨 OpenAI event: {event_type}")

                    if event_type == "response.audio.delta":
                        pcm_data = base64.b64decode(event["delta"])

                        # Store assistant audio for S3
                        assistant_audio_buffer.append(pcm_data)

                        await websocket.send_bytes(pcm_data)
                        print(
                            f"🎵 Sent audio chunk to frontend ({len(pcm_data)} bytes)"
                        )

                    elif event_type == "response.text.delta":
                        text_delta = event.get("delta", "")
                        print(f"📝 Text response: {text_delta}")
                    
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        # Capture user transcript
                        transcript = event.get("transcript", "")
                        print(f"📝 User said: {transcript}")
                        
                        # Check if user is asking for a definition
                        lower_transcript = transcript.lower()
                        definition_patterns = [
                            "what is", "what's", "define", "meaning of", 
                            "what does", "definition of", "explain"
                        ]
                        
                        for pattern in definition_patterns:
                            if pattern in lower_transcript:
                                # Extract the word after the pattern
                                words_after_pattern = lower_transcript.split(pattern)[-1].strip()
                                # Remove common filler words and punctuation
                                words_after_pattern = words_after_pattern.replace(" the ", " ").replace(" a ", " ").replace(" an ", " ")
                                # Split and get words
                                words = words_after_pattern.split()
                                if words:
                                    # Take the first meaningful word, removing punctuation
                                    target_word = words[0].strip("?.,!\"'")
                                    # Special case: if the pattern ends with "of" and we have "definition of X"
                                    if pattern == "definition of" or pattern == "meaning of":
                                        # The word is likely right after "of"
                                        target_word = words[0].strip("?.,!\"'")
                                    
                                    if target_word and len(target_word) > 1:
                                        print(f"📚 User asking for definition of: {target_word}")
                                        
                                        # Fetch dictionary definition asynchronously
                                        definition_data = await fetch_dictionary_definition(target_word)
                                        
                                        # Inject dictionary result into conversation using correct format
                                        if definition_data["found"]:
                                            dict_message = {
                                                "type": "conversation.item.create",
                                                "item": {
                                                    "type": "message",
                                                    "role": "system",
                                                    "content": [{
                                                        "type": "input_text",
                                                        "text": (
                                                            f"Dictionary result for '{target_word}': "
                                                            f"Definition: {definition_data['definition']}. "
                                                            f"Example: {definition_data['example'] or 'No example available'}. "
                                                            "Please explain this word to the student in a friendly and educational way."
                                                        )
                                                    }]
                                                }
                                            }
                                        else:
                                            dict_message = {
                                                "type": "conversation.item.create",
                                                "item": {
                                                    "type": "message",
                                                    "role": "system",
                                                    "content": [{
                                                        "type": "input_text",
                                                        "text": (
                                                            f"Could not find '{target_word}' in the dictionary. "
                                                            "Please provide your own explanation of this word if you know it."
                                                        )
                                                    }]
                                                }
                                            }
                                        
                                        await openai_ws.send(json.dumps(dict_message))
                                        print(f"📤 Sent dictionary context to OpenAI")
                                        break

                    elif event_type == "response.done":
                        print("✅ Response completed")
                        response_active = False

                        # Save assistant audio to S3 if available
                        if assistant_audio_buffer and s3_service:
                            try:
                                # Combine PCM chunks
                                combined_pcm = b"".join(assistant_audio_buffer)

                                # Convert PCM to WebM
                                webm_data = convert_pcm16_to_webm(combined_pcm)

                                if webm_data:
                                    s3_url = await asyncio.to_thread(
                                        s3_service.upload_audio,
                                        audio_data=webm_data,
                                        file_name=f"{session_id}_assistant.webm",
                                        content_type="audio/webm",
                                        metadata={
                                            "session_id": session_id,
                                            "audio_type": "assistant_response",
                                            "size_bytes": str(len(webm_data)),
                                            "original_pcm_size": str(len(combined_pcm)),
                                        },
                                    )
                                    if s3_url:
                                        print(
                                            f"💾 Assistant audio saved to S3: {s3_url}"
                                        )
                                    else:
                                        print("⚠️ Failed to save assistant audio to S3")
                                else:
                                    print("⚠️ Failed to convert assistant audio to WebM")
                            except Exception as e:
                                print(f"🔴 Error saving assistant audio to S3: {e}")

                        # Clear assistant audio buffer
                        assistant_audio_buffer = []

                        await websocket.send_text("RESPONSE_COMPLETE")

                    elif event_type == "error":
                        error_msg = event.get("error", {}).get(
                            "message", "Unknown error"
                        )
                        print(f"🔴 OpenAI error: {error_msg}")
                        response_active = False
                        await websocket.send_text(f"ERROR: {error_msg}")

            except websockets.exceptions.ConnectionClosed:
                print("🔴 OpenAI WebSocket closed")
            except Exception as e:
                print(f"🔴 Error handling OpenAI responses: {e}")

        await asyncio.gather(
            handle_client_messages(),
            handle_openai_responses(),
            return_exceptions=True,
        )

    except Exception as e:
        print(f"💥 Error in langlish node: {e}")
        raise e
    finally:
        if openai_ws:
            await openai_ws.close()
            print("✅ OpenAI WebSocket closed")
    
    # Update state before returning
    state["completed"] = True
    state["openai_ws"] = openai_ws
    state["audio_buffer_size"] = audio_buffer_size
    state["response_active"] = response_active
    state["user_audio_buffer"] = user_audio_buffer
    state["assistant_audio_buffer"] = assistant_audio_buffer
    
    return state


@agent_realtime_router.websocket("/agent-streamline")
async def agent_streamline(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time audio streaming with OpenAI using LangGraph.

    This endpoint now uses LangGraph to orchestrate the conversation workflow
    while maintaining the same WebSocket interface with the frontend.

    Args:
        websocket: FastAPI WebSocket connection object

    Returns:
        None
    """
    print("🔌 WebSocket connection request received")
    await websocket.accept()
    print("✅ WebSocket connection accepted")

    # Generate unique session ID
    session_id = str(uuid.uuid4())
    print(f"🆔 Session ID: {session_id}")

    # Create the LangGraph workflow
    workflow = create_langlish_workflow()
    
    # Initialize the conversation state
    initial_state = ConversationState(
        websocket=websocket,
        session_id=session_id,
        openai_ws=None,
        audio_buffer_size=0,
        response_active=False,
        user_audio_buffer=[],
        assistant_audio_buffer=[],
        completed=False,
        user_transcript="",
        dictionary_word="",
        needs_dictionary=False
    )
    
    try:
        # Execute the workflow
        print("🚀 Starting LangGraph workflow...")
        final_state = await workflow.ainvoke(initial_state)
        print("✅ LangGraph workflow completed")
        
    except Exception as e:
        print(f"💥 Error in LangGraph workflow: {e}")
        try:
            await websocket.send_text(f"ERROR: {str(e)}")
        except Exception:
            pass
    finally:
        print("🧹 Cleaning up...")
        print("🏁 Streamline session ended")
