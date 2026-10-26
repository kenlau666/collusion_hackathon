"""Inspect the delivery encode and bind it to the revised report; no inference."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

P=Path(__file__).resolve().parent
R=P.parents[3]
V=R/'output/video/hospital_reserve_research_explainer.mp4'
T=json.loads((P/'audio_timing.json').read_text())
load=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def decode():
    dest=P/'qa/incident-decoded';dest.mkdir(parents=True,exist_ok=True)
    proof=[('first',0)]
    proof += [(s['id'],round(s['start']+s['duration']-.9,3)) for s in T['scenes']]
    for scene,times in load(P/'production_manifest.json')['motion_review_times'].items():
        proof += [(f'{scene}-motion{i}',at) for i,at in enumerate(times)]
    proof.append(('last',(T['frames']-1)/30))
    frames=[]
    for name,at in proof:
        out=dest/f'{name}.jpg'
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(V),'-frames:v','1','-q:v','2',str(out)],check=True)
        frames.append(dict(name=name,time=at,path=str(out.relative_to(P)),sha256=sha(out)))
    (P/'qa/incident_decoded_frames.json').write_text(json.dumps(frames,indent=2)+'\n')
    from PIL import Image,ImageDraw
    tile=(480,300);sheet=Image.new('RGB',(tile[0]*4,tile[1]*7),'#202522');draw=ImageDraw.Draw(sheet)
    for i,f in enumerate(frames):
        x=(i%4)*tile[0];y=(i//4)*tile[1]
        with Image.open(P/f['path']) as im:
            im.thumbnail((480,270));sheet.paste(im,(x,y+28))
        draw.text((x+8,y+8),f'{f["name"]} @ {f["time"]:.3f}s',fill='white')
    sheet.save(dest/'contact.jpg',quality=92)
    print(json.dumps(dict(decoded_frames=len(frames),contact=str(dest/'contact.jpg'))))

def asr_audit():
    command=load('/tmp/hospital-incident-encoded-transcribe.json')
    assert command['ok'] and command['model']=='small.en'
    observed=load(command['transcriptPath'])
    expected=' '.join(s['text'] for s in T['scenes']).split()
    norm=lambda w:re.sub(r'[^a-z0-9]','',w.lower())
    changes=[]
    matcher=difflib.SequenceMatcher(a=[norm(w) for w in expected],b=[norm(w['text']) for w in observed],autojunk=False)
    for kind,i,j,k,l in matcher.get_opcodes():
        if kind!='equal':changes.append(dict(kind=kind,script=' '.join(expected[i:j]),asr=' '.join(w['text'] for w in observed[k:l])))
    audio_sha=subprocess.check_output(['ffmpeg','-v','error','-i',str(V),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-'],text=True).strip().split('=')[-1]
    result=dict(encoded_audio_sha256=audio_sha,engine='Free local Whisper small.en',
                words=len(observed),through_seconds=max(w['end'] for w in observed),
                script_words=len(expected),differences=changes,subjective_listening=False,
                reviewed_differences=False)
    (P/'qa/incident_encoded_transcript.json').write_text(json.dumps(observed,indent=2)+'\n')
    (P/'qa/incident_encoded_audio_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

def seconds(stamp):
    h,m,s=stamp.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)

def finalize(source_commit):
    manifest=load(P/'production_manifest.json');data=load(P/'data.json')
    check=load(P/'qa/incident_pre_render_check.json')
    assert check['ok'] and not check['browserSkipped']
    assert check['motion']['enabled'] and check['motion']['samples']>0
    assert all(check[k]['errorCount']==0 for k in ['lint','runtime','layout','motion','contrast'])
    report=R/manifest['report_path'];report_qa=load(P.parent/'submission/incident_report_qa.json')
    evidence=load(P.parent/'submission/incident_evidence_manifest.json')['sha256']
    assert all(sha(p)==digest for p,digest in evidence.items())
    assert sha(report)==manifest['report_sha256']==report_qa['sha256'] and report_qa['visual_qa_complete']
    assert all(sha(P/f)==v['sha256'] for f,v in manifest['files'].items())
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(V)],text=True))
    v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['r_frame_rate'])==(1920,1080,'30/1')
    assert int(v['nb_frames'])==T['frames'] and abs(float(probe['format']['duration'])-T['duration'])<.01
    assert v['codec_name']=='h264' and a['codec_name']=='aac' and 120<=T['duration']<=180
    log=Path('/tmp/hospital-incident-loudness.log').read_text()
    loudness,_=json.JSONDecoder().raw_decode(log[log.rfind('{'):])
    assert -17<=float(loudness['input_i'])<=-13 and float(loudness['input_tp'])<=-1
    asr=load(P/'qa/incident_encoded_audio_audit.json');assert asr['reviewed_differences']
    assert asr['through_seconds']>T['duration']-2
    actual_audio=subprocess.check_output(['ffmpeg','-v','error','-i',str(V),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-'],text=True).strip().split('=')[-1]
    assert actual_audio==asr['encoded_audio_sha256']
    subtitles=P/'hospital_reserve_research_explainer.srt'
    blocks=[b.splitlines() for b in subtitles.read_text().strip().split('\n\n')]
    last=0
    for block in blocks:
        start,end=map(seconds,block[1].split(' --> '));assert 0<=start<end<=T['duration'] and start>=last-.001;last=end
    assert ' '.join(' '.join(b[2:]) for b in blocks)==' '.join(s['text'] for s in T['scenes'])
    frames=load(P/'qa/incident_decoded_frames.json')
    assert len(frames)==27 and all(sha(P/f['path'])==f['sha256'] for f in frames)
    independent=load(P/'qa/incident_independent_final_review.json')
    assert independent['all_frames_reviewed'] and not independent['open_p0_p1']
    shutil.copy2(subtitles,V.with_suffix('.srt'))
    shutil.copy2(P/'CREDITS.md',V.with_name('hospital_reserve_research_explainer_CREDITS.md'))
    (P/'qa/incident_ffprobe.json').write_text(json.dumps(probe,indent=2)+'\n')
    (P/'qa/incident_final_loudness.json').write_text(json.dumps(loudness,indent=2)+'\n')
    manifest.update(source_cutoff=source_commit,video_source_commit=source_commit,video_path=str(V.relative_to(R)),video_sha256=sha(V),video_bytes=V.stat().st_size,
                    subtitle_sha256=sha(V.with_suffix('.srt')),report_evidence_files_rechecked=len(evidence),
                    encoded_audio_sha256=actual_audio,skill_sources={},authoring_files={})
    for name in ['hyperframes','hyperframes-cli','hyperframes-core','hyperframes-registry','hyperframes-animation','hyperframes-creative','media-use']:
        path=Path('/Users/kenlau/.agents/skills')/name/'SKILL.md';manifest['skill_sources'][str(path)]={'sha256_at_final_production':sha(path)}
    sources=[P/n for n in ['build_incident_video.py','generate_narration.py','narration.json','audio_timing.json','make_incident_subtitles.py','verify_incident_video.py','STORYBOARD.md','SPEC.md','BRIEF.md','CREDITS.md','REVIEW.md','index.html','index.motion.json','package.json']]
    sources += [P/'compositions'/f'{s["id"]}.html' for s in T['scenes']]
    sources += list((P/'compositions').glob('*.motion.json'))
    for f in sources:manifest['authoring_files'][str(f.relative_to(P))]=sha(f)
    (P/'production_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    qa=dict(passed=True,checked_at_utc=datetime.now(timezone.utc).isoformat(),duration_seconds=T['duration'],frames=T['frames'],fps=30,
            resolution=[1920,1080],video_codec=v['codec_name'],audio_codec=a['codec_name'],video_bytes=V.stat().st_size,video_sha256=sha(V),
            narration_words=sum(len(s['text'].split()) for s in T['scenes']),subtitle_cues=len(blocks),subtitle_exact_script_match=True,
            decoded_frames_visually_reviewed=len(frames),independent_review_passed=True,pre_render_check_passed=True,
            craft_warnings_retained=check['craft']['warningCount'],motion_samples=check['motion']['samples'],integrated_lufs=float(loudness['input_i']),true_peak_dbtp=float(loudness['input_tp']),
            encoded_audio_sha256=actual_audio,encoded_asr_words=asr['words'],encoded_asr_through_seconds=asr['through_seconds'],
            audio_listened_subjectively=False,continuous_playback_assessed=False,report_sha256=sha(report),
            report_source_commit='01e02fd0',science_evidence_commit='faeade21',report_evidence_files_rechecked=len(evidence),asset_hashes_rechecked=len(manifest['files']),
            independent_worlds=[18,20,22],main_cases=12,positive_controls_passed=2,source_cases=14,source_model_requests=26,
            current_attack_is_scripted=True,main_GH_care_is_free_model_choice=True,care_before_protection=[7,7,7],care_with_protection=[8,8,8],
            benign_care_preserved=True,allowed_spare_control_passed=True,prior_autonomous_null_retained=True,external_references=8,
            cumulative_reference_guard_usd=data['cumulative_reference_guard_usd'],actual_modal_charges_verified=False,
            paid_media_api_calls=0,video_authoring_hospital_calls=0,fabricated_experiment_results=False,
            external_submission_or_publication=False,known_remaining_blockers=[])
    (P/'qa/incident_final_qa.json').write_text(json.dumps(qa,indent=2)+'\n')
    print(json.dumps(dict(passed=True,duration_seconds=T['duration'],video_sha256=sha(V),subtitle_cues=len(blocks)),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--decode',action='store_true');parser.add_argument('--audit-asr',action='store_true');parser.add_argument('--finalize',action='store_true');parser.add_argument('--source-commit')
    args=parser.parse_args()
    if args.decode:decode()
    if args.audit_asr:asr_audit()
    if args.finalize:
        assert args.source_commit;finalize(args.source_commit)
