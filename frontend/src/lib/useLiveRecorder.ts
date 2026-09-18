import { useCallback, useEffect, useRef, useState } from "react"
import { API_BASE_URL } from "./config"
import { getAccessToken } from "./authStore"

export type LiveMessage =
  | { type: "queued" }
  | { type: "ready" }
  | { type: "partial"; seq: number; text: string }
  | { type: "final"; seq: number; text: string }
  | { type: "stopped"; raw_transcript: string }
  | { type: "error"; detail: string }

export type LiveRecorderStatus =
  | "idle"
  | "connecting"
  | "queued"
  | "recording"
  | "paused"
  | "stopping"
  | "stopped"
  | "error"

const LIVE_SAMPLE_RATE = 16000

function describeCaptureError(err: unknown): string {
  if (err instanceof DOMException) {
    if (err.name === "NotAllowedError") {
      return "Microphone access was denied. Allow microphone access for this site and try again."
    }
    if (err.name === "NotFoundError") {
      return "No microphone was found on this device."
    }
    if (err.name === "NotReadableError") {
      return "The microphone is already in use by another application."
    }
  }
  if (err instanceof Error && err.message) {
    return `Could not start audio capture: ${err.message}`
  }
  return "Could not start audio capture."
}

export function useLiveRecorder(encounterId: string | null) {
  const [status, setStatus] = useState<LiveRecorderStatus>("idle")
  const [partialText, setPartialText] = useState("")
  const [finalSegments, setFinalSegments] = useState<string[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [finalTranscript, setFinalTranscript] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const cleanupAudio = useCallback(() => {
    workletNodeRef.current?.disconnect()
    workletNodeRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {})
    }
    audioContextRef.current = null
  }, [])

  const start = useCallback(async () => {
    if (!encounterId) return
    setStatus("connecting")
    setErrorMessage(null)
    setPartialText("")
    setFinalSegments([])
    setFinalTranscript(null)

    const token = getAccessToken()
    // API_BASE_URL is normally empty (same-origin, proxied - see
    // vite.config.ts), so build the WebSocket URL from the page's own
    // origin rather than assuming API_BASE_URL is an absolute http(s) URL.
    const wsBase = API_BASE_URL
      ? API_BASE_URL.replace(/^http/, "ws")
      : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`
    const ws = new WebSocket(`${wsBase}/ws/encounters/${encounterId}/live-transcribe?token=${token ?? ""}`)
    wsRef.current = ws

    ws.onmessage = async (event) => {
      const message: LiveMessage = JSON.parse(event.data)
      if (message.type === "queued") {
        setStatus("queued")
      } else if (message.type === "ready") {
        setStatus("recording")
        try {
          await startCapture(ws)
        } catch (err) {
          // getUserMedia (permission denied, no microphone, insecure
          // context) or audioWorklet.addModule can reject here. Previously
          // this was unhandled: the status was already set to "recording"
          // above, so the UI stayed on "Listening..." forever with no
          // error and no way to know capture never actually started.
          setStatus("error")
          setErrorMessage(describeCaptureError(err))
          cleanupAudio()
          ws.close()
        }
      } else if (message.type === "partial") {
        setPartialText(message.text)
      } else if (message.type === "final") {
        setFinalSegments((prev) => [...prev, message.text])
        setPartialText("")
      } else if (message.type === "stopped") {
        setFinalTranscript(message.raw_transcript)
        setStatus("stopped")
        cleanupAudio()
        ws.close()
      } else if (message.type === "error") {
        setErrorMessage(message.detail)
      }
    }

    ws.onerror = () => {
      setStatus("error")
      setErrorMessage("Connection to the live transcription server was lost.")
      cleanupAudio()
    }

    async function startCapture(socket: WebSocket) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const audioContext = new AudioContext({ sampleRate: LIVE_SAMPLE_RATE })
      audioContextRef.current = audioContext
      await audioContext.audioWorklet.addModule("/pcm-worklet.js")

      const source = audioContext.createMediaStreamSource(stream)
      const worklet = new AudioWorkletNode(audioContext, "pcm-worklet-processor")
      workletNodeRef.current = worklet

      worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(e.data)
        }
      }

      source.connect(worklet)
    }
  }, [encounterId, cleanupAudio])

  const stop = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setStatus("stopping")
      wsRef.current.send(JSON.stringify({ type: "stop" }))
    }
  }, [])

  const setPaused = useCallback((paused: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: paused ? "pause" : "resume" }))
      setStatus(paused ? "paused" : "recording")
    }
  }, [])

  useEffect(() => {
    return () => {
      cleanupAudio()
      wsRef.current?.close()
    }
  }, [cleanupAudio])

  return {
    status,
    partialText,
    finalSegments,
    finalTranscript,
    errorMessage,
    start,
    stop,
    setPaused,
  }
}
