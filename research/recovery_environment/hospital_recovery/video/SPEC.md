# Director's specification

GOAL: Explain the persistent public memo, the Hospital comparison, and why incomplete exploit endpoints prevent a recovery claim.
OUTPUT: HyperFrames 0.8.198; 1920×1080; 30 fps; H.264 MP4 with AAC narration/music.
TIME: 14 narrated scenes; target 160–178 seconds, final frame count derived from audio_timing.json. Voice is the clock. Scene-local anchor reveals at 0%, 25%, 50%, and 75% of narration; no words typed on a clock loop.
LOOK: clinical pale green #edf4f2, forest #113c34, white #ffffff, cobalt #234fdf for the kit/memo, amber #944600 for missingness/proposed exploit. Semantic colours are data, not decoration. Outfit 700 headings 74–100px, Outfit 400 body 34–42px, Archivo Black numerals 128–210px. No small labels below28px. 192px text margins,108px top/bottom title safe. Panel corners12px,2px borders, shadow 0 16px 0 at8% green. Full hospital architecture, graph surfaces and objects fill40–80% of frame.
OBJECTS: hospital façades with medical crosses, four labeled service floors per hospital, provisioner, eight bed/patient marks, IV resource kit with cap/handle, a pinned public memo, disabled Surgery identities, a query arrow, full care bars, truncated exploit traces, evidence case folders. All are schematic; no real patient imagery.
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
| temptation | IV kit travels a visibly proposed outbound/return loop; credits accrue illustratively; proposed/not observed remains visible. |
| persist | Two Surgery roles grey out; their connection is cut; memo remains connected to Ward. |
| repair | New bonus changes to0; pending-care stock stays in reserve; delivery splits into push versus explicit read. These are candidate policies. |
| controls | Five prescribed controls resolve one at a time; cycle is labeled isolated30credits, not completed care. |
| ordinary | Six real full care bars land on8/8; credit0 and no physical returns appear after the care evidence. |
| missing | Five exploit continuations stop with endpoint?; last observed8/8 stays distinct from unknown final. Lines are schematic, not elapsed-time estimates. |
| retrieval | Nine returned-read marks appear; separate post-care one-way donations resolve to180credits; no loop/harm inference. |
| diagnostic | Three policy groups show exact paired counts7/8,8/8,7/7. One model+scripted partner is visible. |
| grounding | Query budget marks and self-transfer route appear; Pain donation/return stays0; untriggered mechanism stamp lands. |
| limits |22case marks separate into5controls/11main/6diagnostic; n=1per condition, variance not estimable; no independent-seed count inflation. |
| close | Memo, transfer kit and patient beds align as distinct measurements; Recovery remains unconfirmed holds; author and music attribution remain readable. |

QA: check14midpoints, frame0, proposedloop travel at25/50/75%, exclusion proof, all final bar values, missing endpoint glyphs, diagnostic mapping, finalminus1frame. Inspect review beat/seam/phone sheets and decoded final frames. Measure audio presence/loudness/duration; no claim of subjective listening. Verify report/lineage SHA256 unchanged, no inference calls.
