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
    raw = RAW / f"{name}.wav"
    metadata_path = RAW / f"{name}.json"
    cached = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    reuse_unchanged = ("--reuse-unchanged" in sys.argv and src.exists() and src.read_text() == text
                       and raw.exists() and cached.get("_source_text_sha256") == hashlib.sha256(text.encode()).hexdigest()
                       and cached.get("_raw_wav_sha256") == hashlib.sha256(raw.read_bytes()).hexdigest())
    if "--reuse-raw" in sys.argv or reuse_unchanged:
        assert src.exists() and src.read_text() == text, f"Raw text changed: {name}"
        meta = json.loads((RAW / f"{name}.json").read_text())
        assert meta["speed"] == 1.08 and meta["voice"] == "af_heart"
    print(f"Preparing {name} locally", flush=True)
    if "--reuse-raw" not in sys.argv and not reuse_unchanged:
        request_text = RAW / f"{name}.request.txt"
        request_text.write_text(text)
        pending_audio = RAW / f"{name}.pending.wav"
        result = subprocess.run([
        "npx", "--yes", "hyperframes@0.8.199", "tts", "--text-file", str(request_text),
        "--voice", "af_heart", "--speed", "1.08", "--output", str(pending_audio), "--json",
        ], check=True, text=True, capture_output=True)
        metadata = json.loads(result.stdout)
        assert metadata["voice"] == "af_heart" and metadata["speed"] == 1.08
        pending_audio.replace(raw)
        metadata.update(outputPath=str(raw), _source_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        _raw_wav_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        src.write_text(text)
    dest = OUT / f"{name}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    "atempo=1.14,loudnorm=I=-16:TP=-1:LRA=11", "-ar", "48000", "-ac", "1",
                    str(dest)], check=True)
    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
        "default=nw=1:nk=1", str(dest)], text=True))
    # A short opening lead and final hold per scene. All boundaries are frame aligned.
    frames = round((duration + 0.7) * 30)
    record = {**line, "start": cursor / 30, "frames": frames,
              "duration": frames / 30, "voice_start": cursor / 30 + 0.2,
              "voice_duration": duration, "voice": "af_heart", "speed": 1.08, "post_atempo": 1.14,
              "path": str(dest.relative_to(ROOT)),
              "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
              "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    records.append(record)
    cursor += frames
    print(f"{name}: {duration:.2f}s voice; {frames/30:.2f}s scene", flush=True)
payload = {"provider": "local Kokoro-82M via HyperFrames 0.8.199",
           "paid_api_calls": 0, "api_cost_usd": 0,
           "fps": 30, "duration": cursor / 30, "frames": cursor, "scenes": records}
(ROOT / "audio_timing.json").write_text(json.dumps(payload, indent=2) + "\n")
assert 120 <= payload["duration"] <= 180, payload["duration"]
print(f"Total duration: {payload['duration']:.2f}s", flush=True)
