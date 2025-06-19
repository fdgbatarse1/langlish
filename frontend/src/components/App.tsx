import { Mic } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'

const socketUrl = 'ws://localhost:8000/streamline'

const App = () => {
  const [recording, setRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder>()

  const { sendMessage, readyState, getWebSocket, sendJsonMessage } =
    useWebSocket(
      socketUrl,
      {
        onOpen: () => {
          console.log('🚀 WebSocket connected')
        },
        onMessage: (evt) => {
          console.log('📡 WebSocket message:', evt.data)
        },
        onError: (error) => console.error('🔥 WebSocket error:', error),
        shouldReconnect: () => false
      },
      recording
    )

  const startRecording = async () => {
    try {
      setRecording(true)

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size && readyState === ReadyState.OPEN) {
          event.data.arrayBuffer().then((buffer) => sendMessage(buffer))
        }
      }

      mediaRecorderRef.current.start(100)
    } catch (error) {
      console.error('🔥 Error starting recording:', error)
    }
  }

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current?.stream.getTracks().forEach((t) => t.stop())
    mediaRecorderRef.current = undefined
    sendJsonMessage({
      type: 'EOF'
    })
    getWebSocket()?.close()
    setRecording(false)
  }, [sendJsonMessage, getWebSocket])

  useEffect(() => {
    console.log('🔍 useEffect')
    return () => stopRecording()
  }, [stopRecording])

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
