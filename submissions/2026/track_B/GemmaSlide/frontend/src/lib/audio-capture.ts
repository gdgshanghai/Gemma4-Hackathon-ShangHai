const SAMPLE_RATE = 16000;

export type PcmChunkCallback = (int16Array: Int16Array) => void;

export class MicCapture {
  private _ctx: AudioContext | null = null;
  private _stream: MediaStream | null = null;
  private _workletNode: AudioWorkletNode | null = null;
  private _source: MediaStreamAudioSourceNode | null = null;
  private _onChunk: PcmChunkCallback | null = null;
  private _running = false;

  get running(): boolean {
    return this._running;
  }

  async start(onChunk: PcmChunkCallback): Promise<void> {
    if (this._running) return;
    this._onChunk = onChunk;

    this._stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: SAMPLE_RATE,
        channelCount: 1,
        echoCancellation: true,
      },
    });

    this._ctx = new AudioContext({ sampleRate: SAMPLE_RATE });

    // Load AudioWorklet processor from public/
    await this._ctx.audioWorklet.addModule("/pcm-capture-processor.js");

    this._source = this._ctx.createMediaStreamSource(this._stream);
    this._workletNode = new AudioWorkletNode(
      this._ctx,
      "pcm-capture-processor",
    );

    this._workletNode.port.onmessage = (event: MessageEvent) => {
      if (!this._running) return;
      const int16 = new Int16Array(event.data);
      this._onChunk?.(int16);
    };

    this._source.connect(this._workletNode);
    this._running = true;
  }

  stop(): void {
    this._running = false;
    this._workletNode?.port.close();
    this._workletNode?.disconnect();
    this._source?.disconnect();
    this._ctx?.close();
    this._stream?.getTracks().forEach((t) => t.stop());

    this._workletNode = null;
    this._source = null;
    this._ctx = null;
    this._stream = null;
    this._onChunk = null;
  }
}

/** Convert Int16Array PCM to base64 string for JSON transport. */
export function pcmToBase64(int16: Int16Array): string {
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
