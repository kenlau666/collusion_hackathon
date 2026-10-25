"""Reconcile delivery artifacts against pinned evidence and measured media."""
import hashlib
import json
from pathlib import Path
import re
import shutil

P=Path(__file__).resolve().parent
R=P.parents[3]
video=R/'output/video/hospital_research_explainer.mp4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
T=json.loads((P/'audio_timing.json').read_text())
probe=json.loads(Path('/tmp/hospital-video-ffprobe.json').read_text())
v=next(s for s in probe['streams'] if s['codec_type']=='video')
a=next(s for s in probe['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'],v['nb_frames'])==(1920,1080,'30/1','5328')
assert abs(float(probe['format']['duration'])-177.6)<.01 and a['codec_name']=='aac'
log=Path('/tmp/hospital-video-final-loudness.log').read_text()
loudness,_=json.JSONDecoder().raw_decode(log[log.rfind('{'):])
assert -16<=float(loudness['input_i'])<=-14
assert float(loudness['input_tp'])<=-1
check=json.loads((P/'qa/pre_render_check.json').read_text());assert check['ok'] and not check['browserSkipped']
assert all(check[k]['errorCount']==0 for k in ['lint','runtime','layout','contrast'])
source=P/'../20261025/deadline_pilot_lineage_001/analysis.json'
assert sha(source)=='a93f60d13f8e4d96de6ae1c835f67fd003b1c807eed937e02a898e16b4a2a687'
report=R/'output/pdf/hospital_deadline_recovery_report.pdf'
assert sha(report)=='2311ff993432a60aaef6d47071843227f28e6d497f41eb0be7842fc55e39c551'
reportmanifest=json.loads((P/'../submission/deadline_evidence_manifest.json').read_text())
assert len(reportmanifest['evidence_sha256'])==55
assert all(sha(Path(p))==s for p,s in reportmanifest['evidence_sha256'].items())
# Check the actual SRT, not just the planned word count.
srt=(P/'hospital_research_explainer.srt').read_text()
blocks=[b.splitlines() for b in srt.strip().split('\n\n')]
def sec(stamp):
 h,m,s=stamp.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
last=0
for b in blocks:
 start,end=map(sec,b[1].split(' --> '));assert 0<=start<end<=177.6 and start>=last-.001;last=end
captiontext=' '.join(' '.join(b[2:]) for b in blocks)
assert captiontext==' '.join(s['text'] for s in T['scenes'])
shutil.copy2(P/'hospital_research_explainer.srt',video.with_suffix('.srt'))
shutil.copy2(P/'CREDITS.md',video.parent/'CREDITS.md')
shutil.copy2('/tmp/hospital-video-ffprobe.json',P/'qa/ffprobe.json')
shutil.copy2('/tmp/hospital-video-audio.json',P/'qa/audio_analysis.json')
shutil.copy2('/tmp/hospital-video-render.log',P/'qa/render.log')
(P/'qa/final_loudness.json').write_text(json.dumps(loudness,indent=2)+'\n')
manifest=json.loads((P/'production_manifest.json').read_text())
manifest.update(video_path='output/video/hospital_research_explainer.mp4',video_sha256=sha(video),video_bytes=video.stat().st_size,video_source_commit='e4010679',report_evidence_files_rechecked=55)
manifest['skill_sources']={}
for skill in ['hyperframes','hyperframes-cli','hyperframes-registry','media-use','hyperframes-core','hyperframes-animation','hyperframes-creative','hyperframes-keyframes']:
 f=Path('/Users/kenlau/.agents/skills')/skill/'SKILL.md'
 if f.exists():manifest['skill_sources'][str(f)]={'sha256_at_final_production':sha(f)}
(P/'production_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
qa={'passed':True,'duration_seconds':177.6,'frames':5328,'fps':30,'resolution':[1920,1080],
    'video_codec':v['codec_name'],'audio_codec':a['codec_name'],'video_bytes':video.stat().st_size,
    'video_sha256':sha(video),'narration_api_cost_usd':0,'paid_media_api_calls':0,
    'new_hospital_inference_calls':0,'report_evidence_files_rechecked':55,
    'report_sha256':sha(report),'lineage_sha256':sha(source),
    'author':'LAU, Chi Hong','affiliation':None,'decoded_frames_visually_reviewed':20,
    'opening_and_final_frames_verified':True,'kit_movement_verified_on_encoded_frames':True,
    'all_eight_patients_visible':True,'positive_controls_displayed':'5/5; isolated cycle is30credits, not8/8care',
    'missing_exploit_endpoints_preserved':5,'n_per_cell':1,'fabricated_experiment_results':False,
    'pre_render_check_passed':True,'craft_warnings_retained':check['craft']['warningCount'],
    'integrated_lufs':float(loudness['input_i']),'true_peak_dbtp':float(loudness['input_tp']),
    'audio_listened_subjectively':False,'audio_validation':'measured, with free local ASR of complete narration; not listened',
    'subtitle_cues':len(blocks),'subtitle_exact_script_match':True,'caption_timing':'local Whisper small.en + exact-script corrections/interpolation',
    'capture_mode':'screenshot','gpu':'hardware Apple M4 Pro / ANGLE Metal','render_seconds':139,
    'external_submission_or_publication':False,'known_remaining_blockers':[]}
(P/'qa/final_qa.json').write_text(json.dumps(qa,indent=2)+'\n')
print(json.dumps({k:qa[k] for k in ['passed','video_sha256','video_bytes','integrated_lufs','true_peak_dbtp','subtitle_cues']}))
