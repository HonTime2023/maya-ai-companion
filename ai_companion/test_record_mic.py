import sounddevice as sd
import numpy as np
import wave, struct

print("Default input device:", sd.default.device)
print()
print("=== Sounddevice Input Devices ===")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"  [{i}] {d['name']}  ch={d['max_input_channels']}  sr={d['default_samplerate']}")

print()
print("Recording 5s from DEFAULT device — SPEAK NOW...")
try:
    rec = sd.rec(int(16000 * 5), samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    rms = float(np.sqrt(np.mean(rec.astype(np.float32) ** 2)))
    print(f"Default device RMS: {rms:.1f}")
    # Save to WAV
    with wave.open("C:/Users/Dell/Downloads/AI_Companion/test_default_mic.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(rec.tobytes())
    print("Saved: test_default_mic.wav")
except Exception as e:
    print(f"Default FAILED: {e}")

print()
print("Recording 5s from device 5 — SPEAK NOW...")
try:
    rec5 = sd.rec(int(16000 * 5), samplerate=16000, channels=1, dtype="int16", device=5)
    sd.wait()
    rms5 = float(np.sqrt(np.mean(rec5.astype(np.float32) ** 2)))
    print(f"Device 5 RMS: {rms5:.1f}")
    with wave.open("C:/Users/Dell/Downloads/AI_Companion/test_device5_mic.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(rec5.tobytes())
    print("Saved: test_device5_mic.wav")
except Exception as e:
    print(f"Device 5 FAILED: {e}")
