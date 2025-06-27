import json
import base64
import asyncio
import uuid
from typing import Dict, Any, List
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets
import aiohttp
from src.config import OPENAI_API_KEY
from src.services.s3_service import s3_service
from src.utils.audio import convert_webm_to_pcm16, convert_pcm16_to_webm
import mlflow

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# LangGraph imports
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict


OPENAI_WS_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
)

agent_realtime_router = APIRouter()

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


agent_streamline_instructions = mlflow.load_prompt("prompts:/agent-streamline-instructions/1")
agent_streamline_get_dictionary_definition_description = mlflow.load_prompt(
    "prompts:/agent-streamline-get-dictionary-definition-description/1"
)


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
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=3)
            ) as response:
                print(f"📡 Dictionary API response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("📥 Raw API response: {json.dumps(data, indent=2)}")
                    if data and len(data) > 0:
                        entry = data[0]
                        # Extract key information
                        meanings = entry.get("meanings", [])
                        phonetics = entry.get("phonetics", [])

                        # Get first definition and example
                        definition = ""
                        example = ""
                        if meanings:
                            # Each meaning has multiple definitions
                            for meaning in meanings:
                                definitions = meaning.get("definitions", [])
                                if (
                                    definitions and not definition
                                ):  # Get the first available definition
                                    definition = definitions[0].get("definition", "")
                                    example = definitions[0].get("example", "")
                                    break  # Stop after finding the first definition

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
                            "audio_url": audio_url,
                        }
                    else:
                        # No data returned even though status is 200
                        print(f"⚠️ No data returned for word: {word}")
                        return {
                            "found": False,
                            "word": word,
                            "error": "No data returned",
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

    # Add text buffers for S3 conversation saving
    user_text_buffer: List[str] = []
    assistant_text_buffer: List[str] = []

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
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True,
                },
                "instructions": agent_streamline_instructions.template,
                "tools": [
                    {
                        "type": "function",
                        "name": "get_dictionary_definition",
                        "description": agent_streamline_get_dictionary_definition_description.template,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "word": {
                                    "type": "string",
                                    "description": "The English word to look up (e.g., 'computer', 'desk', 'happiness')",
                                }
                            },
                            "required": ["word"],
                        },
                    }
                ],
                "tool_choice": "auto",
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
            nonlocal \
                response_active, \
                assistant_audio_buffer, \
                user_text_buffer, \
                assistant_text_buffer

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

                    elif event_type == "response.audio_transcript.delta":
                        # Log what the assistant is saying and store for S3
                        transcript_delta = event.get("delta", "")
                        print(f"🗣️ Assistant saying: {transcript_delta}")
                        if transcript_delta:
                            assistant_text_buffer.append(transcript_delta)

                    elif event_type == "response.audio_transcript.done":
                        # Log the complete transcript of what the assistant said
                        full_transcript = event.get("transcript", "")
                        print(f"🗣️ Assistant complete response: {full_transcript}")

                    elif event_type == "response.output_item.added":
                        # Log when a new output item is added
                        item = event.get("item", {})
                        print(
                            f"📋 Output item added: type={item.get('type')}, status={item.get('status')}"
                        )
                        if item.get("type") == "function_call":
                            print(f"🔧 Function call detected: {item.get('name')}")

                    elif event_type == "response.function_call_arguments.delta":
                        # Log streaming function arguments
                        delta = event.get("delta", "")
                        print(f"🔧 Function args delta: {delta}")

                    elif event_type == "response.function_call_arguments.done":
                        # Function call complete, execute it
                        call_id = event.get("call_id")
                        name = event.get("name")
                        arguments = event.get("arguments", "{}")

                        print(f"🔧 Function call: {name} with args: {arguments}")

                        if name == "get_dictionary_definition":
                            try:
                                args = json.loads(arguments)
                                word = args.get("word", "")

                                if word:
                                    print(f"📚 Looking up word: {word}")
                                    definition_data = await fetch_dictionary_definition(
                                        word
                                    )

                                    # Log the actual API response
                                    print("📊 Dictionary API returned:")
                                    print(f"   Found: {definition_data.get('found')}")
                                    print(f"   Word: {definition_data.get('word')}")
                                    print(
                                        f"   Definition: {definition_data.get('definition', 'N/A')}"
                                    )
                                    print(
                                        f"   Example: {definition_data.get('example', 'N/A')}"
                                    )
                                    print(
                                        f"   Audio URL: {definition_data.get('audio_url', 'N/A')}"
                                    )

                                    # Prepare the output to send to OpenAI
                                    output_data = {
                                        "found": definition_data["found"],
                                        "word": definition_data["word"],
                                        "definition": definition_data.get(
                                            "definition", ""
                                        ),
                                        "example": definition_data.get("example", ""),
                                        "audio_url": definition_data.get(
                                            "audio_url", ""
                                        ),
                                    }

                                    print(
                                        f"📤 Sending to OpenAI: {json.dumps(output_data, indent=2)}"
                                    )

                                    # Send function result back
                                    function_result = {
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": call_id,
                                            "output": json.dumps(output_data),
                                        },
                                    }

                                    await openai_ws.send(json.dumps(function_result))
                                    print("📤 Sent dictionary result to OpenAI")

                                    # Request response after function result
                                    await openai_ws.send(
                                        json.dumps({"type": "response.create"})
                                    )
                                    print("📤 Requested response generation")

                            except Exception as e:
                                print(f"🔴 Error handling function call: {e}")
                                # Send error result
                                error_result = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": json.dumps(
                                            {
                                                "error": f"Failed to look up word: {str(e)}"
                                            }
                                        ),
                                    },
                                }
                                await openai_ws.send(json.dumps(error_result))
                                await openai_ws.send(
                                    json.dumps({"type": "response.create"})
                                )

                    elif event_type == "response.output_item.done":
                        # Log output item completion but don't handle function calls here
                        # They're already handled in response.function_call_arguments.done
                        item = event.get("item", {})
                        print(
                            f"📋 Output item completed: type={item.get('type')}, status={item.get('status')}"
                        )

                    elif event_type == "conversation.item.created":
                        # Log conversation items for debugging
                        item = event.get("item", {})
                        print(
                            f"💬 Conversation item created: type={item.get('type')}, role={item.get('role', 'N/A')}"
                        )
                        if item.get("type") == "function_call":
                            print(
                                f"   Function: {item.get('name')}, Call ID: {item.get('call_id')}"
                            )
                            print(f"   Arguments: {item.get('arguments')}")
                        elif item.get("type") == "function_call_output":
                            print("   ✅ Function output acknowledged by OpenAI")
                            print(f"   Call ID: {item.get('call_id')}")
                            # Try to parse and display the output
                            try:
                                output = json.loads(item.get("output", "{}"))
                                print(f"   Output data: {json.dumps(output, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"   Raw output: {item.get('output')}")
                        elif (
                            item.get("type") == "message"
                            and item.get("role") == "assistant"
                        ):
                            # Assistant is generating a response
                            content = item.get("content", [])
                            if content:
                                print(
                                    f"   🤖 Assistant starting response with {len(content)} content parts"
                                )

                    elif (
                        event_type
                        == "conversation.item.input_audio_transcription.completed"
                    ):
                        # Handle user transcript and store for S3
                        transcript = event.get("transcript", "")
                        print(f"📝 User said: {transcript}")
                        if transcript:
                            user_text_buffer.append(transcript)

                    elif event_type == "response.done":
                        print("✅ Response completed")
                        response_active = False

                        # Save conversation to S3 - THIS WAS MISSING IN CODE 2
                        assistant_responses = {
                            "session_id": session_id,
                            "user": " ".join(user_text_buffer),
                            "assistant": " ".join(assistant_text_buffer),
                        }

                        print("📝 Full conversation:")
                        print(
                            json.dumps(
                                assistant_responses, indent=2, ensure_ascii=False
                            )
                        )

                        if s3_service:
                            await asyncio.to_thread(
                                s3_service.upload_text_agent_streamline,
                                json.dumps(
                                    assistant_responses, ensure_ascii=False, indent=2
                                ),
                                f"{session_id}_conversation.json",
                                "application/json",
                                {"session_id": session_id, "type": "conversation_log"},
                            )
                        # Clear text buffers
                        assistant_text_buffer = []
                        user_text_buffer = []

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
        needs_dictionary=False,
    )

    try:
        # Execute the workflow
        print("🚀 Starting LangGraph workflow...")
        await workflow.ainvoke(initial_state)
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
