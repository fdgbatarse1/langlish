import sounddevice as sd
from scipy.io.wavfile import write
import requests

fs = 16000
filename = "my_recording.wav"
recording = None

print("Press Enter to START recording...")
input()
print("Recording... Press Enter to STOP recording.")


recording = sd.rec(int(60 * fs), samplerate=fs, channels=1, dtype='int16')

input()  #Wait for Enter key to stop
sd.stop()

recorded_frames = sd.get_stream().read_available if hasattr(sd.get_stream(), "read_available") else len(recording)

write(filename, fs, recording)
print(f"✅ Recording saved to {filename}")

# Upload
with open(filename, "rb") as f:
    response = requests.post("http://localhost:8000/upload-audio/", files={"file": (filename, f, "audio/wav")})
    print("Upload Response:", response.json())
