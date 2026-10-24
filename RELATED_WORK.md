# Prior work and contribution gate — verification recovery after repair

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Current scope:** the next experiment must use a project already bundled in this repository. The external verification-repair proposal below is parked. Its literature findings remain reference material; its distinction and novelty score do not establish a contribution for an unselected repository-based study. No new novelty claim is made here.

## Historical external proposal review

**Previously proposed approach:** [repair-first verification diagnostic](RESEARCH.md) using the existing full-history SALT-NLP/agent-collusion architecture. Cleanup is retired. **Novelty is not established; current judgment 6/10.** The proposal is a possible empirical boundary study, not a new recovery algorithm, new memory mechanism, or newly invented causal evaluation method.

## Closest sources, exact versions and checked overlap

| Primary source | What is already covered | What our proposal would still need to establish |
| --- | --- | --- |
| [Emergent Collusion in Long-Horizon LLM Agent Interaction, 2609.24967v2](https://arxiv.org/html/2609.24967v2), Sep 26, §4.1.2/§4.2, B.2/B.3, F | Peer interventions, memory length/scope, reward/feedback ablations, and unrestricted communication from the start. Full histories/reflections are genuinely replayed. Appendix F warns that mutual acceptance can be compliant when the required evidence can be transmitted. | A matched post-violation repair comparison, with actual evidence delivery and incorrect-work acceptance distinguished from useful correct verification. A from-start ablation or another deletion result is insufficient. |
| [When Harnesses Lose the Signal, 2610.00372v1](https://arxiv.org/html/2610.00372v1), Sep 30, §3 | Same-state recovery/no-recovery contrasts, rescue versus harm, timing, and a learned recovery router in ALFWorld. | Do not claim paired recovery or preservation measurement as new. Our additional phenomenon would need to concern inherited verification behavior after an operational conflict is repaired, with a consequential residual effect. |
| [Rollback the World, Keep the Reflection, 2609.18304v3](https://arxiv.org/html/2609.18304v3), Sep 22, §4.4/§4.5/§5.3 | Joint choices over restoration and retained knowledge; structured reflection excludes stale branch-local claims and preserves useful experience. | Retaining some history while clearing other state is not a new principle. Verify a distinct peer-verification failure and use ordinary repair/full reset as serious baselines. |
| [Testing Interchangeability in LLM Agent Teams, 2609.05279v1](https://arxiv.org/html/2609.05279v1), Sep 4, §3/§4.4 | Actual task/partner notebooks, role-matched swaps, placebo roster disruption, clearing/amnesia and coordination-cost recovery. | Replacing a teammate or measuring a reset cost is insufficient novelty. The present proposal uses native episode history, not an added two-part notebook. |
| [Colosseum, 2602.15198v2](https://arxiv.org/html/2602.15198v2), May 27, §5.8/limitations | Objective task regret plus communication/action distinctions; recommends auditing channels and checking claims against shared state. Its described evaluation omits long-horizon memory/delayed outcomes. | It is a useful outcome-grounded alternative, but its local runner is not a verified persistent-history recovery implementation. We do not infer such a system from its paper. |
| [Model Organisms of Collusion: Corrective Transfer in Untrusted Monitors, 2610.30582v1](https://arxiv.org/html/2610.30582v1), Oct 22, abstract/§2.1/§2.7–2.8 | Corrective monitor-weight training, transfer from caught to uncaught misconduct, fixed review cases, benign controls and capability costs. | Distinct intervention/construct: our proposal removes supplied history under fixed weights and repairs current evidence access. Fixed-case review and measuring correction costs are already established. This new paper further limits broad claims about being the first to study collusion correction. |

Exact source URLs, versions and downloaded HTML hashes are in [sources.json](research/recovery_environment/replacement_screen/20261024/sources.json) and [additional_sources.json](research/recovery_environment/replacement_screen/20261024/additional_sources.json). Source-described findings are not independently reproduced by opening papers. The native helper tests and saved-trace regrading establish only their declared software/data facts.

Earlier strong overlaps remain relevant: [FLP v3](https://arxiv.org/html/2605.01758v3#S5.SS4) already removes recent history/album entries and evaluates benign retention; [SafeFlow v3](https://arxiv.org/html/2506.07564v3#A3.SS2) describes logged dependency-aware containment/rollback; [Self-Propagating Misalignment v1](https://arxiv.org/html/2610.04083v1) uses authored memory/files to influence a successor. Their pinned cache manifests are preserved under [novelty sources](research/novelty_directions/sources/manifest.json) and [the earlier construct review](research/recovery_environment/construct_audits/20261024T124951Z/literature_manifest.json). These are different threats/settings, not direct replications of our proposed task.

## Precise candidate distinction and its limit

The candidate empirical question is whether **a history formed under an infeasible verification channel changes verification after the current case again contains the required evidence**, and whether removing that history improves invalid-work rejection without degrading valid-work acceptance. The causal contrast must be within the same current case and shared prefix; published constrained/unrestricted trajectories do not provide it.

The checked sections of the closest architecture paper examine memory and communication interventions from the start or benign warm-up followed by constraint, rather than the proposed broken-to-repaired transition after recorded violations. That is a bounded distinction from those sections, not proof of absence across all literature or a sufficient contribution. A measurable, practically important residual effect beyond ordinary repair remains unknown. If complete evidence alone is adequate, report that rather than inventing an additional defense.

The public [full dataset](https://huggingface.co/datasets/SALT-NLP/agent-collusion) improves audit feasibility: original agent-visible messages, authoritative logs, artifacts and judgments can be checked. Its [pinned trace manifest](research/recovery_environment/replacement_screen/20261024/trace_sources.json) identifies the twelve inspected files. The website's reduced viewer bundles cannot substitute for complete contexts. Published data are historical evidence, not a newly passing prospective control.

## Remaining novelty checks and stopping

A primary search extract for [From Prompts to Conventions: A Study of Multi-Agent LLM Consensus](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6429193) describes hysteresis under mid-run objective reversals. Full retrieval returned 403 and no exact-version/hash audit was possible. This is an unresolved overlap lead. We therefore do not claim a new general principle of convention persistence, hysteresis or response to objective reversal. The blocked source is recorded, not silently treated as cleared.

Focused searches also checked repair/post-onset terms and the latest corrective-transfer paper. This is not an exhaustive systematic review. A novel benchmark combination or an unrun factorial design does not warrant an 8/10 demonstrated-novelty score. Before a main study, the contribution must survive the strongest simple baseline and a focused overlap review of the actual observed result. Without new behavioral evidence, additional design prose currently cannot close that gate.

Applied [Orchestra Research Idea Brainstorming v1.0.0 at commit 773a52944ba4747a18bd4ae9ade53fff041adcbc](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), using problem-first, failure-analysis and simplicity. The twelve-candidate record and iteration decisions are maintained in RESEARCH.md rather than a duplicate planning document.

## Retired reviews

The prior Cleanup-specific overlap table/reviews are in [Git at 4580fdf3](https://github.com/kenlau666/collusion_hackathon/blob/4580fdf3/RELATED_WORK.md). Its data, source hashes and null feasibility result remain unchanged. The auction enforcement, earlier memory probe and verified-fact gateway remain historical/parked; this replacement does not revive them as new defenses.
