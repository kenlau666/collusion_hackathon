# Keeping Care Supplied — research video

A143.6second HyperFrames companion to the revised **Keeping Care Supplied: A Reserve Guard Against Resource-Diversion Incidents** report, by **LAU, Chi Hong**. The faster cut uses372spoken words, shorter pauses and0.35second scene transitions while preserving the prior voice speed. Sixteen animated scenes follow the last required kit through the unprotected incident and a matched reserve replay.

The latest study uses three constructed worlds18/20/22. Attack-off care is[7,7,7]; attack-on and both benign arms are[8,8,8]. Actual debit denial precedes free-model GHcare3/3, benign care is preserved, and both fresh instructed controls pass2/2, including an allowed spare donation. The malicious transfer and late peer are researcher scripts. This is prevention of a known incident, not autonomous collusion, goal repair or post-harm restoration. Earlier autonomous harmful-memo nulls remain explicit. All eight external references follow the revised report's verification audit.

## Watch and edit

- Current MP4: `output/video/hospital_reserve_research_explainer.mp4` from the repository root;1920×1080/30fps, English free local Kokoro narration. Matching75cue SRT and a dedicated credits file sit alongside it.
- Current report: `output/pdf/hospital_reserve_incident_report.pdf`, revision commit `01e02fd0`. Scientific evidence cutoff `faeade21`.
- Editable preview: `npx --yes hyperframes@0.8.199 preview --background --port 3017` from this folder. While running, use `http://localhost:3017/#project/video`. The **Edit with Framey** button opens the HyperFrames desktop app: https://hyperframes.dev/studio/download .
- `index.html` mounts the16active scene files; `narration.json` contains the exact script; `audio_timing.json` pins372words and4308frames; `data.json` derives the results from the frozen analysis. `production_manifest.json` pins assets, report, verified references and production sources.
- Historical capacity/deadline MP4s and their QA retain their original cutoffs. Their editable source is recoverable from Git; inactive older build scripts are not current entrypoints.

## Rebuild

Use Node22+, FFmpeg and Python with the report's ReportLab/pypdf dependencies. Saved-asset rendering needs no provider credentials.

```sh
python3 build_incident_video.py
npx --yes hyperframes@0.8.199 check --json
npx --yes hyperframes@0.8.199 render --quality delivery --fps 30 --crf 18 --output ../../../../output/video/hospital_reserve_research_explainer.mp4
```

`generate_narration.py --reuse-unchanged` uses free local Kokoro at generation1.08and pitch-preserving atempo1.14. New text requires local synthesis; exact raw text/audio hashes gate reuse. `prepare_audio_review.py` builds a temporary combined voice track; local Whisper small.en supplies word timings; `make_incident_subtitles.py` preserves the exact narration in the SRT and records ASR corrections. `verify_incident_video.py` decodes the actual final MP4, audits encoded voice ASR and verifies media/report/evidence hashes. Model/synthesis caches remain ignored.

Read `CREDITS.md`, `REVIEW.md` and `qa/incident_final_qa.json` for attribution, measured checks and limits. No paid media API, new Hospital inference or external submission is performed by video authoring. Audio is measured/transcribed, not subjectively listened to; continuous playback is not claimed.
