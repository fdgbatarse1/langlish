import { Mic } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import useWebSocket, { ReadyState } from 'react-use-websocket'

const socketUrl = 'ws://localhost:8000/streamline'

const App = () => {
  const [recording, setRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder>()
  const audioContextRef = useRef<AudioContext>()
  const audioQueueRef = useRef<ArrayBuffer[]>([])
  const isPlayingRef = useRef(false)

  const { sendMessage, readyState, sendJsonMessage } = useWebSocket(socketUrl, {
    onOpen: () => {
      console.log('🚀 WebSocket connected')
    },
    onMessage: async (event) => {
      // Handle audio data
      if (event.data instanceof Blob) {
        console.log('🎵 Received audio:', event.data.size, 'bytes')
        const arrayBuffer = await event.data.arrayBuffer()

        // Add to queue instead of playing immediately
        audioQueueRef.current.push(arrayBuffer)

        // Start playing if not already playing
        if (!isPlayingRef.current) {
          playNextAudioChunk()
        }
      }
      // Handle text messages
      else if (typeof event.data === 'string') {
        console.log('📝 Received:', event.data)
      }
    },
    onError: (error) => console.error('🔥 WebSocket error:', error),
    shouldReconnect: () => true
  })

  // Play audio chunks one by one
  const playNextAudioChunk = async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false
      console.log('🎵 All audio finished')
      return
    }

    const arrayBuffer = audioQueueRef.current.shift()!
    isPlayingRef.current = true

    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext()
      }

      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume()
      }

      const pcm16Data = new Int16Array(arrayBuffer)
      const audioBuffer = audioContextRef.current.createBuffer(
        1,
        pcm16Data.length,
        24000
      )
      const channelData = audioBuffer.getChannelData(0)

      // Convert PCM16 to Float32
      for (let i = 0; i < pcm16Data.length; i++) {
        channelData[i] = pcm16Data[i] / (pcm16Data[i] < 0 ? 0x8000 : 0x7fff)
      }

      const source = audioContextRef.current.createBufferSource()
      source.buffer = audioBuffer
      source.connect(audioContextRef.current.destination)

      // IMPORTANT: Wait for this chunk to finish before playing next
      source.onended = () => {
        console.log('🎵 Chunk finished, playing next...')
        playNextAudioChunk() // Play next chunk only after this one ends
      }

      source.start()
      console.log('🎵 Playing chunk')
    } catch (error) {
      console.error('🔴 Audio error:', error)
      // On error, try next chunk
      playNextAudioChunk()
    }
  }

  const startRecording = async () => {
    try {
      setRecording(true)
      // Clear any pending audio when starting new recording
      audioQueueRef.current = []
      isPlayingRef.current = false

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })

      const audioChunks: Blob[] = []

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      mediaRecorderRef.current.onstop = async () => {
        if (audioChunks.length > 0) {
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
          const arrayBuffer = await audioBlob.arrayBuffer()
          sendMessage(arrayBuffer)
          sendJsonMessage({ type: 'EOF' })
        }
      }

      mediaRecorderRef.current.start()
    } catch (error) {
      console.error('🔥 Recording error:', error)
      setRecording(false)
    }
  }

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream
        .getTracks()
        .forEach((track) => track.stop())
      mediaRecorderRef.current = undefined
      setRecording(false)
    }
  }, [recording])

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop()
        mediaRecorderRef.current.stream
          .getTracks()
          .forEach((track) => track.stop())
      }
    }
  }, [])

  return (
    <div className="flex h-screen w-screen items-center justify-center">
      <button
        onClick={recording ? stopRecording : startRecording}
        disabled={readyState !== ReadyState.OPEN}
        className={`flex size-24 items-center justify-center rounded-full text-white transition-colors ${
          recording
            ? 'bg-red-500 hover:bg-red-600'
            : 'bg-blue-500 hover:bg-blue-600'
        } ${
          readyState !== ReadyState.OPEN ? 'cursor-not-allowed opacity-50' : ''
        }`}
      >
        <Mic className={recording ? 'animate-pulse' : ''} />
      </button>
    </div>
  )
}

export default App
