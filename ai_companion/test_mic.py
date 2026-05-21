import sounddevice as sd
import numpy as np

print("=== Input Audio Devices ===")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"  [{i}] {d['name']} — {d['max_input_channels']}ch, sr={d['default_samplerate']}")

print()
print("=== Testing device=1 with 4 channels for 3 seconds (SPEAK NOW!) ===")
max_vals = []
last_data = None
try:
    with sd.InputStream(device=1, channels=4, samplerate=16000, blocksize=512, dtype="float32") as stream:
        for _ in range(47):
            data, _ = stream.read(512)
            last_data = data
            max_vals.append(float(np.max(np.abs(data))))
    overall_max = max(max_vals)
    print(f"  4ch: overall_max={overall_max:.6f}  any_nonzero={'YES' if overall_max > 0 else 'NO'}")
    if last_data is not None:
        for c in range(4):
            ch_max = float(np.max(np.abs(last_data[:, c])))
            print(f"    channel {c} last-frame max: {ch_max:.6f}")
except Exception as e:
    print(f"  4ch FAILED: {e}")

print()
print("=== Testing device=1 with 1 channel ===")
try:
    with sd.InputStream(device=1, channels=1, samplerate=16000, blocksize=512, dtype="float32") as stream:
        vals = []
        for _ in range(47):
            data, _ = stream.read(512)
            vals.append(float(np.max(np.abs(data))))
    print(f"  1ch: max={max(vals):.6f}  any_nonzero={'YES' if max(vals) > 0 else 'NO'}")
except Exception as e:
    print(f"  1ch FAILED: {e}")

print()
print("=== Testing default input device ===")
try:
    default_dev = sd.default.device[0]
    print(f"  Default input device: {default_dev} ({sd.query_devices(default_dev)['name']})")
    with sd.InputStream(channels=1, samplerate=16000, blocksize=512, dtype="float32") as stream:
        vals = []
        for _ in range(47):
            data, _ = stream.read(512)
            vals.append(float(np.max(np.abs(data))))
    print(f"  default: max={max(vals):.6f}  any_nonzero={'YES' if max(vals) > 0 else 'NO'}")
except Exception as e:
    print(f"  default FAILED: {e}")
