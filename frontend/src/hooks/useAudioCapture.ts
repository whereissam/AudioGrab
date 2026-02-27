import { useState, useRef, useCallback, useEffect } from 'react'

export interface AudioCaptureOptions {
  /** Interval in milliseconds between audio chunks (default: 250) */
  chunkInterval?: number
  /** Echo cancellation (default: true) */
  echoCancellation?: boolean
  /** Noise suppression (default: true) */
  noiseSuppression?: boolean
  /** Auto gain control (default: true) */
  autoGainControl?: boolean
}

export interface AudioCaptureState {
  isCapturing: boolean
  isSupported: boolean
  error: string | null
  audioLevel: number
}

export function useAudioCapture(options: AudioCaptureOptions = {}) {
  const {
    chunkInterval = 250,
    echoCancellation = true,
    noiseSuppression = true,
    autoGainControl = true,
  } = options

  const [state, setState] = useState<AudioCaptureState>({
    isCapturing: false,
    isSupported: typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia,
    error: null,
    audioLevel: 0,
  })

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const isCapturingRef = useRef(false)

  // Clean up resources
  const cleanup = useCallback(() => {
    isCapturingRef.current = false
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
      mediaRecorderRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    analyserRef.current = null
  }, [])

  // Update audio level visualization
  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current) return

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)

    // Calculate average level
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length
    const normalizedLevel = Math.min(average / 128, 1) // Normalize to 0-1

    setState(prev => ({ ...prev, audioLevel: normalizedLevel }))

    if (isCapturingRef.current) {
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel)
    }
  }, [])

  // Start capturing audio
  const startCapture = useCallback(async (onChunk: (blob: Blob) => void) => {
    if (!state.isSupported) {
      setState(prev => ({
        ...prev,
        error: 'Audio capture is not supported in this browser',
      }))
      return false
    }

    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation,
          noiseSuppression,
          autoGainControl,
          sampleRate: 16000,
        },
      })

      streamRef.current = stream

      // Set up audio analysis for level visualization
      const audioContext = new AudioContext()
      audioContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser

      // Determine best MIME type
      let mimeType = 'audio/webm;codecs=opus'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm'
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = 'audio/mp4'
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = '' // Let browser choose
          }
        }
      }

      // Create MediaRecorder
      const recorder = new MediaRecorder(stream, {
        mimeType: mimeType || undefined,
      })

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          onChunk(event.data)
        }
      }

      recorder.onerror = (event) => {
        console.error('MediaRecorder error:', event)
        setState(prev => ({
          ...prev,
          error: 'Recording error occurred',
          isCapturing: false,
        }))
        cleanup()
      }

      recorder.onstop = () => {
        setState(prev => ({ ...prev, isCapturing: false, audioLevel: 0 }))
      }

      mediaRecorderRef.current = recorder

      // Start recording with specified chunk interval
      recorder.start(chunkInterval)

      isCapturingRef.current = true
      setState(prev => ({
        ...prev,
        isCapturing: true,
        error: null,
      }))

      // Start audio level visualization
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel)

      return true
    } catch (error) {
      console.error('Failed to start audio capture:', error)

      let errorMessage = 'Failed to access microphone'
      if (error instanceof DOMException) {
        if (error.name === 'NotAllowedError') {
          errorMessage = 'Microphone permission denied. Please allow microphone access.'
        } else if (error.name === 'NotFoundError') {
          errorMessage = 'No microphone found. Please connect a microphone.'
        } else if (error.name === 'NotReadableError') {
          errorMessage = 'Microphone is in use by another application.'
        }
      }

      setState(prev => ({
        ...prev,
        error: errorMessage,
        isCapturing: false,
      }))

      cleanup()
      return false
    }
  }, [state.isSupported, chunkInterval, echoCancellation, noiseSuppression, autoGainControl, cleanup, updateAudioLevel])

  // Stop capturing audio
  const stopCapture = useCallback(() => {
    cleanup()
    setState(prev => ({
      ...prev,
      isCapturing: false,
      audioLevel: 0,
    }))
  }, [cleanup])

  // Clean up on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  return {
    ...state,
    startCapture,
    stopCapture,
  }
}

// Check if browser supports audio capture
export function isAudioCaptureSupported(): boolean {
  return typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
}
