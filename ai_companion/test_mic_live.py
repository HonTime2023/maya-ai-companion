"""Real-time mic level meter — watch the bar respond as you speak. Press Ctrl+C to stop."""
import sounddevice as sd
import numpy as np
import sys

DEVICE = 1
CHANNELS = 1
SR = 16000

print(f"Real-time mic meter (device={DEVICE}, {CHANNELS}ch, {SR}Hz)")
print("Speak into your microphone. The bar should move when you talk.")
print("If it stays flat, increase mic volume in Windows Sound Settings.")
print("Press Ctrl+C to stop.\n")

try:
    with sd.InputStream(device=DEVICE, channels=CHANNELS, samplerate=SR, blocksize=512, dtype="float32") as stream:
        while True:
            data, _ = stream.read(512)
            rms = float(np.sqrt(np.mean(data ** 2)))
            peak = float(np.max(np.abs(data)))
            bar_len = int(peak * 400)
            bar = "#" * min(bar_len, 60)
            sys.stdout.write(f"\r  peak={peak:.5f}  [{bar:<60}]  {'AUDIO!' if peak > 0.01 else '(silence)'}  ")
            sys.stdout.flush()
except KeyboardInterrupt:
    print("\nDone.")
except Exception as e:
    print(f"Error: {e}")
