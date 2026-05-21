import pyaudio, struct, math

pa = pyaudio.PyAudio()

# Step 1: quick scan — find which devices return non-zero audio
print("=== Scanning all input devices for signal (0.5s each) ===")
print("(Keep quiet during scan, then speak during the LONG TEST)\n")
candidates = []
for i in range(pa.get_device_count()):
    d = pa.get_device_info_by_index(i)
    if d["maxInputChannels"] < 1:
        continue
    try:
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=16000,
            input=True, input_device_index=i, frames_per_buffer=512
        )
        peak = 0
        for _ in range(16):  # ~0.5s
            data = stream.read(512, exception_on_overflow=False)
            samples = struct.unpack("<512h", data)
            rms = math.sqrt(sum(s * s for s in samples) / 512)
            if rms > peak:
                peak = rms
        stream.close()
        status = "SILENT" if peak < 5 else f"signal rms={peak:.1f}"
        print(f"  [{i:2d}] {d['name'][:45]:45s}  {status}")
        if peak >= 5:
            candidates.append((i, d["name"], peak))
    except Exception as e:
        print(f"  [{i:2d}] {d['name'][:45]:45s}  FAILED: {e}")

print()
if not candidates:
    print("WARNING: No device returned signal during quiet scan.")
    print("Will test promising devices with 8 seconds — SPEAK DURING THE TEST.\n")
    # Try the most common ones
    candidates = [(idx, pa.get_device_info_by_index(idx)["name"], 0)
                  for idx in [0, 1, 9, 13, 14]
                  if pa.get_device_info_by_index(idx)["maxInputChannels"] >= 1]

# Step 2: long test on each candidate — user must speak
print("=== LONG TEST (8 seconds each) — SPEAK NOW AND KEEP TALKING ===\n")
best_device = None
best_rms = 0
for dev_idx, dev_name, _ in candidates:
    print(f"  Testing [{dev_idx}] {dev_name[:50]} ...")
    try:
        stream = pa.open(
            format=pyaudio.paInt16, channels=1, rate=16000,
            input=True, input_device_index=dev_idx, frames_per_buffer=512
        )
        peak = 0
        for frame in range(250):  # 8 seconds
            data = stream.read(512, exception_on_overflow=False)
            samples = struct.unpack("<512h", data)
            rms = math.sqrt(sum(s * s for s in samples) / 512)
            if rms > peak:
                peak = rms
            if frame % 50 == 0:
                bar = "#" * min(40, int(rms / 30))
                print(f"    {frame/31:.1f}s  rms={rms:6.1f}  {bar}")
        stream.close()
        print(f"  -> Peak: {peak:.1f}  {'WORKS!' if peak > 100 else 'quiet/silent'}\n")
        if peak > best_rms:
            best_rms = peak
            best_device = dev_idx
    except Exception as e:
        print(f"  -> FAILED: {e}\n")

pa.terminate()
print("=" * 60)
if best_device is not None and best_rms > 100:
    print(f"BEST DEVICE: [{best_device}]  peak rms={best_rms:.1f}")
    print(f"\nIn voice_agent_deepgram.py, change:")
    print(f"  MIC_DEVICE = {best_device}")
else:
    print(f"No device had clear speech signal (best rms={best_rms:.1f}).")
    print("Try speaking louder, or check mic permissions in Windows Settings.")
