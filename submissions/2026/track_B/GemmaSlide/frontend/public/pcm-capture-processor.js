// AudioWorkletProcessor: captures raw PCM Int16 from microphone
// Runs in a dedicated audio thread, no main-thread blocking.
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs, _outputs, _params) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channel = input[0];
    if (!channel) return true;

    // Float32 [-1, 1] → Int16
    const int16 = new Int16Array(channel.length);
    for (let i = 0; i < channel.length; i++) {
      const s = Math.max(-1, Math.min(1, channel[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true;
  }
}

registerProcessor("pcm-capture-processor", PcmCaptureProcessor);
