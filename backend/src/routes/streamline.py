import json
import base64
import asyncio
import uuid
from typing import Dict, Any, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets
from src.config import OPENAI_API_KEY
from src.services.s3_service import s3_service
from src.utils.audio import convert_webm_to_pcm16, convert_pcm16_to_webm

from src.mlflow_config import setup_mlflow
from src.services.prompt_tracker import log_prompt_version

OPENAI_WS_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
)

realtime_router = APIRouter()


@realtime_router.websocket("/streamline")
async def streamline(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time audio streaming with OpenAI.

    Handles bidirectional audio streaming between client and OpenAI's real-time API,
    including audio conversion, session management, and response handling.

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

    openai_ws = None
    audio_buffer_size = 0
    response_active = False

    # Audio buffers for S3 storage
    user_audio_buffer: List[bytes] = []
    assistant_audio_buffer: List[bytes] = []

    # Text buffer for S3
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
                "instructions": (
                    "You are Langlish, a friendly and patient English learning "
                    "assistant. You help students improve their English through "
                    "conversation practice. Your role is to: help the user practice "
                    "english conversation, correct grammar mistakes gently, suggest "
                    "better vocabulary when appropriate, encourage the student, and "
                    "adapt to the student's level."
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
            nonlocal \
                audio_buffer_size, \
                response_active, \
                user_audio_buffer, \
                user_text_buffer

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
                        print(f"Received text message from client: {message['text']}")
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
                assistant_text_buffer, \
                user_text_buffer

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

                    elif event_type == "response.audio_transcript.delta":
                        text_delta = event.get("delta", "")
                        print(
                            f"Received assistant audio_transcript delta: {text_delta}"
                        )
                        if text_delta:
                            assistant_text_buffer.append(text_delta)
                            print(f"📝 Text response: {text_delta}")

                    elif (
                        event_type
                        == "conversation.item.input_audio_transcription.completed"
                    ):
                        # Handle user transcript - same as code 2
                        transcript = event.get("transcript", "")
                        print(f"📝 User said: {transcript}")
                        if transcript:
                            user_text_buffer.append(transcript)

                    elif (
                        event_type
                        == "conversation.item.input_audio_transcription.failed"
                    ):
                        # Handle transcription failures
                        error = event.get("error", {})
                        print(f"🔴 User transcription failed: {error}")

                    elif event_type == "input_audio_buffer.speech_started":
                        # User started speaking
                        print("🎤 User started speaking")

                    elif event_type == "input_audio_buffer.speech_stopped":
                        # User stopped speaking
                        print("🎤 User stopped speaking")

                    elif event_type == "conversation.item.created":
                        # Log conversation items for debugging
                        item = event.get("item", {})
                        item_type = item.get("type", "")
                        print(f"💬 Conversation item created: type={item_type}")

                        # Check if this is a user message with transcript
                        if item_type == "message" and item.get("role") == "user":
                            content = item.get("content", [])
                            for content_part in content:
                                if (
                                    content_part.get("type") == "input_audio"
                                    and "transcript" in content_part
                                ):
                                    transcript = content_part["transcript"]
                                    print(f"📝 User said (from content): {transcript}")
                                    if transcript:
                                        user_text_buffer.append(transcript)

                    elif event_type == "response.done":
                        print("✅ Response completed")
                        response_active = False

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
                                s3_service.upload_text_streamline,
                                json.dumps(
                                    assistant_responses, ensure_ascii=False, indent=2
                                ),
                                f"{session_id}_conversation.json",
                                "application/json",
                                {"session_id": session_id, "type": "conversation_log"},
                            )
                        # clear
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
        print(f"💥 Error in streamline: {e}")
        try:
            await websocket.send_text(f"ERROR: {str(e)}")
        except Exception:
            pass
    finally:
        print("🧹 Cleaning up...")
        if openai_ws:
            await openai_ws.close()
            print("✅ OpenAI WebSocket closed")
        print("🏁 Streamline session ended")
