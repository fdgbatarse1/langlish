import { Mic } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'

const socketUrl = 'ws://localhost:8000/streamline'

const App = () => {
  const [recording, setRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const { sendMessage, readyState } = useWebSocket(
    socketUrl,
    {
      onOpen: () => console.log('WebSocket connected'),
      onError: (error) => console.error('WebSocket error:', error),
      shouldReconnect: () => false
    },
    recording
  )

  useEffect(() => () => stopRecording(), [])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'
      })
      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size && readyState === ReadyState.OPEN) {
          event.data.arrayBuffer().then((buffer) => sendMessage(buffer))
        }
      }

      mediaRecorder.start(100)
      setRecording(true)
    } catch (error) {
      console.error('Error starting recording:', error)
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setRecording(false)
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center">
      <button
        onClick={recording ? stopRecording : startRecording}
        className="flex size-24 items-center justify-center rounded-full bg-blue-500 text-white transition-colors hover:bg-blue-600"
      >
        {recording ? <Mic className="text-red-500" /> : <Mic />}
      </button>
    </div>
  )
}

export default App
