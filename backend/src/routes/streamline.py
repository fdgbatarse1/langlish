import json
import base64
import asyncio
import io

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets
from pydub import AudioSegment
from src.config import OPENAI_API_KEY

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

realtime_router = APIRouter()

def convert_webm_to_pcm16(webm_data: bytes) -> bytes:
    """Convert WebM/Opus audio to PCM16 24kHz mono for OpenAI"""
    try:
        print(f"🔄 Converting WebM audio ({len(webm_data)} bytes)")
        
        # Load the WebM audio
        audio = AudioSegment.from_file(io.BytesIO(webm_data), format="webm")
        
        # Convert to PCM16 24kHz mono as required by OpenAI
        pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)
        
        print(f"✅ Converted to PCM16: {len(pcm_audio.raw_data)} bytes")
        return pcm_audio.raw_data
    except Exception as e:
        print(f"🔴 Error converting audio: {e}")
        return b""

@realtime_router.websocket("/streamline")
async def streamline(websocket: WebSocket):
    print("🔌 WebSocket connection request received")
    await websocket.accept()
    print("✅ WebSocket connection accepted")
    
    openai_ws = None
    audio_buffer_size = 0
    response_active = False
    
    try:
        print("🔗 Connecting to OpenAI WebSocket...")
        openai_ws = await websockets.connect(
            OPENAI_WS_URL,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        print("✅ Connected to OpenAI WebSocket")

        # Configure session for English teaching
        print("📝 Sending session configuration...")
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                    "create_response": True
                },
                "instructions": "You are a friendly English teacher. Help the user practice English conversation. Be encouraging and patient. Keep responses short and clear."
            }
        }
        await openai_ws.send(json.dumps(session_config))
        print("✅ Session configuration sent")

        async def handle_client_messages():
            """Handle messages from the frontend client"""
            nonlocal audio_buffer_size, response_active
            
            try:
                while True:
                    message = await websocket.receive()
                    
                    if "bytes" in message:
                        # Audio data from frontend (WebM format)
                        webm_data = message["bytes"]
                        audio_buffer_size += len(webm_data)
                        print(f"📨 Received WebM audio: {len(webm_data)} bytes (total: {audio_buffer_size} bytes)")
                        
                        # Convert WebM to PCM16 and send to OpenAI
                        pcm_data = convert_webm_to_pcm16(webm_data)
                        if pcm_data:
                            audio_b64 = base64.b64encode(pcm_data).decode('utf-8')
                            
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": audio_b64
                            }))
                            print(f"📤 Sent PCM16 audio to OpenAI ({len(pcm_data)} bytes)")
                        else:
                            print("🔴 Audio conversion failed, skipping chunk")
                        
                    elif "text" in message:
                        try:
                            data = json.loads(message["text"])
                            if data.get("type") == "EOF" and not response_active:
                                print(f"🛑 Received EOF with {audio_buffer_size} bytes of total audio")
                                
                                if audio_buffer_size > 5000:
                                    response_active = True
                                    # Commit the actual audio buffer (not text)
                                    await openai_ws.send(json.dumps({
                                        "type": "input_audio_buffer.commit"
                                    }))
                                    await openai_ws.send(json.dumps({
                                        "type": "response.create",
                                        "response": {"modalities": ["audio", "text"]}
                                    }))
                                    print("📤 Sent audio-based response request")
                                else:
                                    print("⚠️ Not enough audio data, skipping response")
                                    
                                # Reset for next recording
                                audio_buffer_size = 0
                                
                        except json.JSONDecodeError:
                            print(f"📝 Non-JSON text message: {message['text']}")
                            
            except WebSocketDisconnect:
                print("🔴 Client disconnected")
            except Exception as e:
                print(f"🔴 Error handling client messages: {e}")

        async def handle_openai_responses():
            """Handle responses from OpenAI and send to frontend"""
            nonlocal response_active
            
            try:
                async for message in openai_ws:
                    event = json.loads(message)
                    event_type = event.get("type", "")
                    
                    print(f"📨 OpenAI event: {event_type}")
                    
                    if event_type == "response.audio.delta":
                        # Send audio directly to frontend
                        pcm_data = base64.b64decode(event["delta"])
                        await websocket.send_bytes(pcm_data)
                        print(f"🎵 Sent audio chunk to frontend ({len(pcm_data)} bytes)")
                        
                    elif event_type == "response.text.delta":
                        # Handle text responses (useful for debugging)
                        text_delta = event.get("delta", "")
                        print(f"📝 Text response: {text_delta}")
                        
                    elif event_type == "response.done":
                        print("✅ Response completed")
                        response_active = False  # Allow next response
                        await websocket.send_text("RESPONSE_COMPLETE")
                        
                    elif event_type == "error":
                        error_msg = event.get("error", {}).get("message", "Unknown error")
                        print(f"🔴 OpenAI error: {error_msg}")
                        response_active = False  # Reset on error
                        await websocket.send_text(f"ERROR: {error_msg}")
            
            except websockets.exceptions.ConnectionClosed:
                print("🔴 OpenAI WebSocket closed")
            except Exception as e:
                print(f"🔴 Error handling OpenAI responses: {e}")

        # Run both handlers concurrently
        await asyncio.gather(
            handle_client_messages(),
            handle_openai_responses(),
            return_exceptions=True
        )

    except Exception as e:
        print(f"💥 Error in streamline: {e}")
        try:
            await websocket.send_text(f"ERROR: {str(e)}")
        except:
            pass
    finally:
        print("🧹 Cleaning up...")
        if openai_ws:
            await openai_ws.close()
            print("✅ OpenAI WebSocket closed")
        print("🏁 Streamline session ended")