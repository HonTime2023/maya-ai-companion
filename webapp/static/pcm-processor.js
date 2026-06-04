/**
 * pcm-processor.js — AudioWorklet for capturing mic as Int16 PCM (16 kHz).
 * Loaded by AudioContext.audioWorklet.addModule('/pcm-processor.js').
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
    this._len = 0;
    // Send chunks of ~80ms (128 frames × ~10 = 1280 frames at 16kHz)
    this._chunkSize = 1280;
  }

  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;

    // convert Float32 → Int16
    const pcm = new Int16Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      const s = Math.max(-1, Math.min(1, ch[i]));
      pcm[i]  = s < 0 ? s * 32768 : s * 32767;
    }

    this._buf.push(pcm);
    this._len += pcm.length;

    // flush when we have enough samples
    while (this._len >= this._chunkSize) {
      const out = new Int16Array(this._chunkSize);
      let pos = 0;
      while (pos < this._chunkSize && this._buf.length > 0) {
        const piece = this._buf[0];
        const need  = this._chunkSize - pos;
        if (piece.length <= need) {
          out.set(piece, pos);
          pos += piece.length;
          this._len -= piece.length;
          this._buf.shift();
        } else {
          out.set(piece.subarray(0, need), pos);
          this._buf[0] = piece.subarray(need);
          this._len -= need;
          pos = this._chunkSize;
        }
      }
      // transfer ownership so no copy
      this.port.postMessage(out.buffer, [out.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
