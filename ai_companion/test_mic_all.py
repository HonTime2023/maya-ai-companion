"""Test all mic devices — speak during each one to find which captures your voice best."""
import sounddevice as sd
import numpy as np
import time

# Devices to test (input only)
test_devices = [
    (1, 1, 16000),   # Microphone Array MME 
    (5, 2, 44100),   # Microphone Array WASAPI
    (9, 2, 48000),   # Microphone Array (2ch, 48kHz)
    (13, 2, 44100),  # FrontMic
    (14, 2, 48000),  # Microphone Array 1 SST
    (15, 4, 16000),  # Microphone Array 2 SST (native 16kHz)
    (16, 4, 16000),  # Microphone Array 3 SST (native 16kHz)
]

print("=" * 60)
print("MIC TEST — speak 'hello hello hello' during each test")
print("=" * 60)

for device, channels, sr in test_devices:
    info = sd.query_devices(device)
    name = info['name']
    print(f"\n[{device}] {name} ({channels}ch @ {sr}Hz)")
    print("  SPEAK NOW...")
    try:
        max_vals = []
        with sd.InputStream(device=device, channels=channels, samplerate=sr, blocksize=512, dtype="float32") as stream:
            for _ in range(47):  # ~3 seconds
                data, _ = stream.read(512)
                max_vals.append(float(np.max(np.abs(data))))
        peak = max(max_vals)
        peak_int16 = int(peak * 32767)
        status = "GOOD ✓" if peak > 0.01 else ("WEAK (~quiet)" if peak > 0.001 else "SILENT ✗")
        print(f"  peak={peak:.6f} ({peak_int16} int16) → {status}")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(0.5)

print("\n" + "=" * 60)
print("Pick the device with GOOD or highest peak value.")
print("=" * 60)
