# Hospital research explainer

A177.6second HyperFrames companion to **After Source Removal**, by **LAU, Chi Hong**.

The report is at `../../../../output/pdf/hospital_deadline_recovery_report.pdf`. The final video is at `../../../../output/video/hospital_research_explainer.mp4`; matching SRT captions are supplied. Experimental findings remain in the closed lineage, not in the illustrative motion graphics.

## Watch and edit

- MP4:1920×1080,30fps,English narration.
- Studio: `npx --yes hyperframes@0.8.198 preview --background` from this folder. The server URL includes `#project/video`.
- The editable composition is `index.html` plus one scene per HTML file in `compositions/`.
- `narration.json` is the exact script; `audio_timing.json` pins voice files and frame timing; `data.json` derives figures from the closed22case lineage.
- `CREDITS.md` includes the required music attribution for a future upload description. No publishing has occurred.

## Rebuild

Use Node22+ and FFmpeg. No provider credentials are needed to render the saved assets.

```sh
python3 build_video.py
npx --yes hyperframes@0.8.198 check --json
npx --yes hyperframes@0.8.198 render --quality delivery --fps 30 --crf 18 --output ../../../../output/video/hospital_research_explainer.mp4
```


`generate_narration.py` uses the free local Kokoro engine (generation speed1.08, pitch-preserving atempo1.14) and never calls a paid media API. It is unnecessary for rerendering the saved voice files. `prepare_audio_review.py` creates a temporary combined voice track; `make_subtitles.py` aligns the script to its local Whisper transcript. Raw synthesis and model caches are ignored; final voice assets are retained.

See `production_manifest.json`, `REVIEW.md` and `qa/final_qa.json` for source hashes, measured checks and verification limits. A report companion is not new experimental evidence; proposed behavior stays labeled, and censored outcomes stay missing.
