# Director's specification

GOAL: Explain the persistent public memo, the Hospital comparison, and the complete comparisons, inventory-cost difference and limits on recovery claims.
OUTPUT: HyperFrames 0.8.199; 1920×1080; 30 fps; H.264 MP4 with AAC narration/music.
TIME: 14 narrated scenes; target 160–178 seconds, final frame count derived from audio_timing.json. Voice is the clock. Scene-local anchor reveals at 0%, 25%, 50%, and 75% of narration; no words typed on a clock loop.
LOOK: clinical pale green #edf4f2, forest #113c34, white #ffffff, cobalt #234fdf for the kit/memo, amber #944600 for proposed exploit. Semantic colours are data, not decoration. Outfit 700 headings 74–100px, Outfit 400 body 34–42px, Archivo Black numerals 128–210px. No small labels below28px. 192px text margins,108px top/bottom title safe. Panel corners12px,2px borders, shadow 0 16px 0 at8% green. Full hospital architecture, graph surfaces and objects fill40–80% of frame.
OBJECTS: hospital façades with medical crosses, four labeled service floors per hospital, provisioner, eight bed/patient marks, IV resource kit with cap/handle, a pinned public memo, disabled Surgery identities, a query arrow, full care bars, five complete exploit-care bars and three post-care inventory bars, evidence case folders. All are schematic; no real patient imagery.
MOTION: arrivals power4.out 18–24frames, physical travel power2.inOut 35–55frames, exits power3.in 10–14frames. Stagger3–6frames. Kit follows one continuous authored route derived from the registry path traveler; bars use the registry's deterministic growth recipe with exact endpoints; numerals use precomputed count-up rows. Landed text holds still. Three seam mechanisms: directional panel wipe (16frames), object carry/camera crop (18frames), colour field change (12frames). No unseeded or clock-driven motion.
SOUND: local Kokoro af_heart voice, generated at1.08 and a documented pitch-preserving post-tempo if needed to fit the requested length. Quiet CC BY4.0 no-melody underscore by Scott Buckley; 2second opening fade,3second closing fade. Restrained bundled whooshes on large movements; no synthetic confirmation dings. Target final mix −16 to−14LUFS, true peak≤−1dBTP.
BANNED: dark navy void, neon/glow, floating decorative particles, glass dashboard, cream/serif/mono-label design, logo in corner, identical three-card rows, bullets standing in for explanation, all entrances sliding upward, drifting titles, fictional attack/repair success, missing endpoints filled as8/8final, conditions pooled as seeds.

## Shots

Timing comes from audio_timing.json, not manually estimated narration duration.

| Scene | Hero action / readable state / handoff |
|---|---|
| handoff | Surgery identity moves out; public memo stays. Opening line is present at frame0. Memo carries into the hospital world. |
| care | Two hospital façades assemble floor by floor; provisioner links them; eight bed marks arrive. |
| prefix | Prior pathway resolves into Ward pending; eight pending tiles remain after checkpoint15. |
| temptation | IV kit travels a visibly proposed outbound/return loop; credits accrue illustratively; PROPOSED STRATEGY remains visible. |
| persist | Two Surgery roles grey out; their connection is cut; memo remains connected to Ward. |
| repair | New bonus changes to0; pending-care stock stays in reserve; delivery splits into push versus explicit read. These are candidate policies. |
| controls | Five prescribed controls resolve one at a time; cycle is labeled isolated30credits, not completed care. |
| ordinary | Six real full care bars land on8/8; score/stock variation and no physical returns remain explicit. |
| missing | Five exploit-care bars reach8/8; all5/5horizons are complete after the local reservation correction. |
| retrieval | Fifteen returned-read marks appear; the no-memo baseline also earns180post-care credits; exposure/credit does not prove collusion. |
| diagnostic | Three policy groups show exact paired counts8/7,8/8,7/8. One model+scripted partner is visible. |
| grounding | Three post-care inventory bars show27/27/0units for Original/Zero bonus/Care reserve, native scores5812/5812/6082. All care8/8; reserve denials0; n=1/post-hoc limit remains. |
| limits |22case marks separate into5controls/11main/6diagnostic; n=1per condition, variance not estimable; no independent-seed count inflation. |
| close | Memo, transfer kit and patient beds align as distinct measurements; Recovery remains unconfirmed holds; author and music attribution remain readable. |

QA: check14midpoints, frame0, proposedloop travel at25/50/75%, exclusion proof, all final bar values, all5complete exploit bars and27/27/0inventory bars, diagnostic mapping, finalminus1frame. Inspect review beat/seam/phone sheets and decoded final frames. Measure audio presence/loudness/duration; no claim of subjective listening. Verify the new report/lineage SHA256 and all evidence manifest entries; no inference calls during video authoring.
