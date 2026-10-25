# Production review

## Creative decisions

Selected the hospital handoff narrative, with the memo as the persistent object and the kit as a proposed action. The evidence-detective desk and first-person kit alternatives remain in STORYLINES.md. Clinical green and cobalt, hospital architecture, purposeful resource travel and measured charts replace a slide-by-slide abstract. The report's inconclusive recovery result is the ending.

## Verified before render

- HyperFrames0.8.198: lint/runtime/layout/contrast all pass,29seek samples; no errors or layout/contrast warnings. Local fonts and GSAP are frozen in assets with license notices.
- All14scene midpoints, both beat sheets, both360px phone sheets and26seam strips reviewed. An independent reviewer found the patient-icon stack and overlapping titles; both are fixed. All eight beds now occupy one horizontal row, and outgoing headings fade before incoming headings appear. Overlapping body reveals during a half-second wipe are intentional.
- Late-state proof frames verify controls, all diagnostic values7/8,8/8,7/7, missing final endpoints versus last-observed8/8, returned memo reads9, post-care180credits, no-op self-transfers and the closing caveat. The proposed IV loop remains labeled proposed/not observed.
- Root duration177.6seconds,5328frames at30fps. Local Whisper small.en transcribed the complete voice track through176.92seconds. The69cue SRT preserves the exact458word script, correcting ASR punctuation/number spellings and two substitutions. These are audio alignment operations, not experimental inference.
- Final report SHA2562311ff993432a60aaef6d47071843227f28e6d497f41eb0be7842fc55e39c551 and closed lineage SHA256a93f60d13f8e4d96de6ae1c835f67fd003b1c807eed937e02a898e16b4a2a687 remain unchanged. No new Hospital requests.

## Warnings retained on purpose

Six dead-stretch warnings cover3.26–5.04second explanatory holds while narration explains a finished diagram or result. Landed type remains still. The weakest shot is the candidate-policy frame: more physical stock movement could teach reserve enforcement, but no actual reserve denial was observed, so the film avoids inventing one. A more compact next version could split policy and delivery into separate shots.

One line_unread warning for THE MAIN COMPARISON reports0.78seconds. Pixel proof at29.5seconds shows the header still present more than5seconds after entry; it remains readable across the scene and is hidden only for the seam. This warning is inconsistent with the inspected pixels; it is not waived by hiding a defect.

Keyframes' static parser cannot resolve the registry-adapted onUpdate path coordinates. A focused shot and actual temporal frames are used instead; final encoded travel must be inspected before delivery. No claim of a parsed MotionPath assertion is made.

## Audio and final file

Narration is free local synthetic Kokoro speech, with a quiet licensed instrumental and restrained whooshes. Audio will be measured for presence, loudness, true peak and completion after render. The producer cannot hear the audio in this tool workflow; subjective voice/music quality is not claimed as listened to. Decoded final-frame and audio results are recorded in qa/final_qa.json after export.
