import pyaudio
import numpy as np
import sys

pa = pyaudio.PyAudio()

print("Input devices:")
for i in range(pa.get_device_count()):
    d = pa.get_device_info_by_index(i)
    if d["maxInputChannels"] > 0:
        name = d["name"]
        ch = d["maxInputChannels"]
        print(f"  [{i}] {name}  ch={ch}")

print()
print("Recording 5 seconds via PyAudio device 1 — SPEAK NOW...")
stream = pa.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    input_device_index=1,
    frames_per_buffer=512,
)

peak = 0
for _ in range(156):
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
pa.terminate()
print(f"\nMax int16 peak: {peak}  (need > 500 for speech to work)")
if peak < 10:
    print("RESULT: Mic returns silence — Windows volume/privacy issue")
elif peak < 500:
    print("RESULT: Mic is too quiet — increase volume/boost in Windows Sound settings")
else:
    print("RESULT: Mic is working! Audio captured successfully.")
