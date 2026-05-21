import sounddevice as sd

apis = sd.query_hostapis()
devices = sd.query_devices()

print("Input devices with API info:")
for i, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        api = apis[d["hostapi"]]["name"]
        name = d["name"]
        ch = d["max_input_channels"]
        sr = d["default_samplerate"]
        print(f"  [{i}] {name} | {api} | ch={ch} | sr={sr}")
