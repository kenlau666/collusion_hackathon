"""Generate free local Kokoro narration, preserving exact text and timing."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets/audio"
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
lines = json.loads((ROOT / "narration.json").read_text())
records = []
cursor = 0
for line in lines:
    name, text = line["id"], line["text"]
    src = RAW / f"{name}.txt"
    src.write_text(text)
    raw = RAW / f"{name}.wav"
    print(f"Generating {name} locally", flush=True)
    if "--reuse-raw" not in sys.argv:
        result = subprocess.run([
        "npx", "--yes", "hyperframes", "tts", "--text-file", str(src),
        "--voice", "af_heart", "--speed", "1.08", "--output", str(raw), "--json",
        ], check=True, text=True, capture_output=True)
        (RAW / f"{name}.json").write_text(result.stdout)
    dest = OUT / f"{name}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    "atempo=1.14,loudnorm=I=-16:TP=-1:LRA=11", "-ar", "48000", "-ac", "1",
                    str(dest)], check=True)
    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
        "default=nw=1:nk=1", str(dest)], text=True))
    # A short opening lead and final hold per scene. All boundaries are frame aligned.
    frames = round((duration + 1.0) * 30)
    record = {**line, "start": cursor / 30, "frames": frames,
              "duration": frames / 30, "voice_start": cursor / 30 + 0.25,
              "voice_duration": duration, "voice": "af_heart", "speed": 1.08, "post_atempo": 1.14,
              "path": str(dest.relative_to(ROOT)),
              "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
              "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    records.append(record)
    cursor += frames
    print(f"{name}: {duration:.2f}s voice; {frames/30:.2f}s scene", flush=True)
payload = {"provider": "local Kokoro-82M via HyperFrames 0.8.198",
           "paid_api_calls": 0, "api_cost_usd": 0,
           "fps": 30, "duration": cursor / 30, "frames": cursor, "scenes": records}
(ROOT / "audio_timing.json").write_text(json.dumps(payload, indent=2) + "\n")
assert 120 <= payload["duration"] <= 180, payload["duration"]
print(f"Total duration: {payload['duration']:.2f}s", flush=True)
