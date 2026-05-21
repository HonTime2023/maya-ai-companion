import pyaudio
import numpy as np
import sys

pa = pyaudio.PyAudio()
d = pa.get_default_input_device_info()
print(f"Default input: [{d['index']}] {d['name']}")
print()

for dev_idx in [0, 1, 5]:
    print(f"Testing device {dev_idx} — SPEAK NOW — 4 seconds")
    try:
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=16000,
            input=True, input_device_index=dev_idx, frames_per_buffer=512
        )
        peak = 0
        for _ in range(125):
            data = stream.read(512, exception_on_overflow=False)
            arr = np.frombuffer(data, dtype=np.int16)
            p = int(np.max(np.abs(arr)))
            if p > peak:
                peak = p
            bar = "#" * min(p // 80, 50)
            sys.stdout.write(f"\r  peak={p:5d}  [{bar:<50}]  ")
            sys.stdout.flush()
        stream.stop_stream()
        stream.close()
        print(f"\nDevice {dev_idx} peak: {peak}")
    except Exception as e:
        print(f"\nDevice {dev_idx} error: {e}")
    print()

pa.terminate()
