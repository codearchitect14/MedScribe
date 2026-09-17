// Converts the microphone's Float32 audio blocks into 16-bit signed PCM and
// posts each block to the main thread, matching the raw PCM16 mono format
// the backend's live transcription WebSocket expects (see
// docs/live-transcription.md). Runs on the audio rendering thread, so it
// must stay allocation-light per block.
class PcmWorkletProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    const channel = input && input[0]
    if (!channel || channel.length === 0) {
      return true
    }

    const pcm16 = new Int16Array(channel.length)
    for (let i = 0; i < channel.length; i++) {
      const sample = Math.max(-1, Math.min(1, channel[i]))
      pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }

    this.port.postMessage(pcm16.buffer, [pcm16.buffer])
    return true
  }
}

registerProcessor("pcm-worklet-processor", PcmWorkletProcessor)
