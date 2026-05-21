import sounddevice as sd
print("\n=== AUDIO DEVICES ===\n")
devices = sd.query_devices()
for i, d in enumerate(devices):
    print(f"{i}: {d['name']}")
    print(f"   Input channels: {d['max_input_channels']}")
    print()

print(f"Default input device: {sd.default.device[0]}")
print(f"Default output device: {sd.default.device[1]}")
