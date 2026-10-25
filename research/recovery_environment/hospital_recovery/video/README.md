# Hospital research explainer

A178.8second HyperFrames companion to **After Source Removal**, by **LAU, Chi Hong**. It presents the complete22-case capacity successor: five model positives pass, all eleven main conditions complete care8/8, no proposed physical loop occurs, and the reserve trajectory avoids27surplus post-care units with a270point score difference and zero guard denials. Every condition has n=1; reliable recovery is not demonstrated.

The report is at `../../../../output/pdf/hospital_capacity_recovery_report.pdf`. The video is at `../../../../output/video/hospital_capacity_research_explainer.mp4`; matching SRT captions are supplied. The old deadline report/video remain separate historical files; their incomplete endpoints are not overwritten with new results.

## Watch and edit

- MP4:1920×1080,30fps,English synthetic narration;68exact-script SRT cues.
- Preview: `npx --yes hyperframes@0.8.199 preview --background` from this folder. The actual project URL is `http://127.0.0.1:3017/#project/video` while the local server runs. The HyperFrames desktop app can continue editing: https://hyperframes.dev/studio/download .
- `index.html` mounts one editable scene per file in `compositions/`.
- `narration.json` is the exact455word script; `audio_timing.json` pins voice files and frame timing; `data.json` derives results from the frozen capacity lineage and post-hoc inventory review.
- `CREDITS.md` supplies required music attribution for a future upload description. No external submission or publishing is claimed.

## Rebuild

Use Node22+ and FFmpeg; provider credentials are unnecessary for saved-asset rendering.

```sh
python3 build_capacity_video.py
npx --yes hyperframes@0.8.199 check --json
npx --yes hyperframes@0.8.199 render --quality delivery --fps 30 --crf 18 --output ../../../../output/video/hospital_capacity_research_explainer.mp4
```

`generate_narration.py --reuse-unchanged` uses free local Kokoro (generation1.08, pitch-preserving atempo1.14); cached raw audio is reused only with matching text/audio hashes. No paid media API is called. `prepare_audio_review.py` creates a temporary full voice track; local Whisper small.en transcribes it; `make_capacity_subtitles.py` aligns exact script words to that transcript and records number-spelling/interpolation corrections. Raw synthesis/model caches are ignored; final voice assets are retained.

See `production_manifest.json`, `REVIEW.md` and `qa/capacity_final_qa.json` for source hashes, measured checks and limits. The film is a report companion, not new experimental evidence. Proposed behavior stays labeled; old censored outcomes remain missing in their own cohort.
