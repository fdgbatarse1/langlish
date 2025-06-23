import io

from pydub import AudioSegment


def convert_webm_to_pcm16(webm_data: bytes) -> bytes:
    """
    Convert WebM/Opus audio to PCM16 24kHz mono for OpenAI.

    Args:
        webm_data: Raw WebM audio data as bytes

    Returns:
        bytes: Converted PCM16 audio data, or empty bytes if conversion fails
    """
    try:
        print(f"🔄 Converting WebM audio ({len(webm_data)} bytes)")

        audio = AudioSegment.from_file(io.BytesIO(webm_data), format="webm")

        pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)

        print(f"✅ Converted to PCM16: {len(pcm_audio.raw_data)} bytes")
        return pcm_audio.raw_data
    except Exception as e:
        print(f"🔴 Error converting audio: {e}")
        return b""


def convert_pcm16_to_webm(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """
    Convert PCM16 audio to WebM format.

    Args:
        pcm_data: Raw PCM16 audio data as bytes
        sample_rate: Sample rate of the PCM audio (default: 24000)

    Returns:
        bytes: Converted WebM audio data, or empty bytes if conversion fails
    """
    try:
        print(f"🔄 Converting PCM16 audio ({len(pcm_data)} bytes) to WebM")

        # Create AudioSegment from raw PCM data
        audio = AudioSegment(
            pcm_data,
            sample_width=2,  # 16-bit
            frame_rate=sample_rate,
            channels=1,  # mono
        )

        # Export to WebM format in memory
        buffer = io.BytesIO()
        audio.export(buffer, format="webm", codec="libopus", bitrate="64k")
        webm_data = buffer.getvalue()

        print(f"✅ Converted to WebM: {len(webm_data)} bytes")
        return webm_data
    except Exception as e:
        print(f"🔴 Error converting PCM to WebM: {e}")
        return b""
