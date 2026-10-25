"""Verify actual exported media, exact captions and the frozen report hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
R = P.parents[3]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
load = lambda path: json.loads(Path(path).read_text())


def seconds(stamp):
    h, m, s = stamp.replace(',', '.').split(':')
    return int(h)*3600 + int(m)*60 + float(s)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--visual-review-complete', action='store_true', required=True)
    args = parser.parse_args()
    video = R / 'output/video/hospital_capacity_research_explainer.mp4'
    report = R / 'output/pdf/hospital_capacity_recovery_report.pdf'
    timing = load(P/'audio_timing.json')
    data = load(P/'data.json')
    probe = load('/tmp/hospital-capacity-video-ffprobe.json')
    v = next(s for s in probe['streams'] if s['codec_type']=='video')
    a = next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['r_frame_rate']) == (1920,1080,'30/1')
    assert int(v['nb_frames']) == timing['frames']
    assert abs(float(probe['format']['duration'])-timing['duration']) < .01
    assert 120 <= timing['duration'] <= 180 and a['codec_name']=='aac'
    log = Path('/tmp/hospital-capacity-video-final-loudness.log').read_text()
    loudness,_ = json.JSONDecoder().raw_decode(log[log.rfind('{'):])
    assert -17 <= float(loudness['input_i']) <= -13
    assert float(loudness['input_tp']) <= -1
    check = load(P/'qa/capacity_pre_render_check.json')
    assert check['ok'] and not check['browserSkipped']
    assert all(check[k]['errorCount']==0 for k in ['lint','runtime','layout','contrast'])
    source = P/'../20261025/capacity_successor_lineage_001/analysis.json'
    lineage = load(source)
    assert sha(source) == data['source_sha256']
    assert sha(source.with_name('qualitative_capacity_review.json')) == data['qualitative_source_sha256']
    assert lineage['mode']=='real_model_only' and not lineage['issues']
    encoded_audio_audit=load(P/'qa/capacity-corrections/encoded_audio_audit.json')
    final_audio_sha=Path('/tmp/hospital-capacity-final-encoded-audio.sha256').read_text().strip().split('=')[-1]
    assert final_audio_sha==encoded_audio_audit['encoded_audio_sha256']
    report_manifest = load(P/'../submission/capacity_evidence_manifest.json')['sha256']
    assert all(sha(path)==expected for path,expected in report_manifest.items())
    report_qa = load(P/'../submission/capacity_report_qa.json')
    assert report_qa['sha256']==sha(report) and report_qa['visual_qa_complete']
    subtitles = P/'hospital_capacity_research_explainer.srt'
    blocks = [b.splitlines() for b in subtitles.read_text().strip().split('\n\n')]
    last=0
    for block in blocks:
        start,end=map(seconds,block[1].split(' --> '))
        assert 0 <= start < end <= timing['duration'] and start >= last-.001
        last=end
    assert ' '.join(' '.join(b[2:]) for b in blocks)==' '.join(s['text'] for s in timing['scenes'])
    frames = load(P/'qa/capacity_decoded_frames.json')
    assert len(frames)==20 and all((P/f['path']).exists() for f in frames)
    shutil.copy2(subtitles,video.with_suffix('.srt'))
    shutil.copy2(P/'CREDITS.md',video.parent/'CREDITS.md')
    for source_file,target in [('/tmp/hospital-capacity-video-ffprobe.json','capacity_ffprobe.json'),
                               ('/tmp/hospital-capacity-video-audio.json','capacity_audio_analysis.json'),
                               ('/tmp/hospital-capacity-video-render.log','capacity_render.log')]:
        shutil.copy2(source_file,P/'qa'/target)
    (P/'qa/capacity_final_loudness.json').write_text(json.dumps(loudness,indent=2)+'\n')
    manifest = load(P/'production_manifest.json')
    assert all(sha(P/path) == expected['sha256'] for path,expected in manifest['files'].items())
    manifest.update(source_cutoff=args.source_commit,science_evidence_commit=report_qa['evidence_commit'],video_path=str(video.relative_to(R)),video_sha256=sha(video),
                    video_bytes=video.stat().st_size,video_source_commit=args.source_commit,
                    report_evidence_files_rechecked=len(report_manifest))
    manifest['skill_sources']={}
    for name in ['hyperframes','hyperframes-cli','hyperframes-registry','media-use']:
        path=Path('/Users/kenlau/.agents/skills')/name/'SKILL.md'
        manifest['skill_sources'][str(path)]={'sha256_at_final_production':sha(path)}
    manifest['authoring_files']={}
    for path in [P/'build_capacity_video.py',P/'generate_narration.py',P/'narration.json',
                 P/'make_capacity_subtitles.py',P/'finalize_capacity_delivery.py',
                 P/'extract_capacity_review.py',P/'STORYBOARD.md',P/'SPEC.md',P/'REVIEW.md']:
        manifest['authoring_files'][str(path.relative_to(P))]=sha(path)
    (P/'production_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    qa={'passed':True,'duration_seconds':timing['duration'],'frames':timing['frames'],'fps':30,
        'resolution':[1920,1080],'video_codec':v['codec_name'],'audio_codec':a['codec_name'],
        'video_bytes':video.stat().st_size,'video_sha256':sha(video),
        'narration_api_cost_usd':0,'paid_media_api_calls':0,'video_authoring_hospital_calls':0,
        'source_study_attempts':sum(r['outward_attempts'] for r in lineage['Results']['per_cell']),
        'source_horizons':sum(r['horizon_reached'] for r in lineage['Results']['per_cell']),
        'source_cases':22,'controls_passed':data['controls_passed'],
        'report_evidence_files_rechecked':len(report_manifest),'report_sha256':sha(report),
        'lineage_sha256':sha(source),'author':'LAU, Chi Hong','affiliation':None,
        'decoded_frames_visually_reviewed':len(frames),'opening_and_final_frames_verified':True,
        'kit_movement_verified_on_encoded_frames':True,'all_eight_patients_visible':True,
        'successor_missing_exploit_endpoints':data['missing_exploit_endpoints'],
        'historical_missing_exploit_endpoints_preserved':5,
        'cumulative_reference_guard_usd':lineage['accounting']['cumulative_reference_guard_usd'],
        'asset_hashes_rechecked':len(manifest['files']),
        'decoded_frame_sha256':{f['path']:sha(P/f['path']) for f in frames},
        'n_per_cell':1,'fabricated_experiment_results':False,'pre_render_check_passed':True,
        'craft_warnings_retained':check['craft']['warningCount'],
        'integrated_lufs':float(loudness['input_i']),'true_peak_dbtp':float(loudness['input_tp']),
        'audio_listened_subjectively':False,'continuous_playback_assessed':False,
        'audio_validation':'Complete free local ASR of the encoded audio and raw-voice caption alignment; measured levels, not listened',
        'encoded_audio_sha256':final_audio_sha,'encoded_asr_words':encoded_audio_audit['asr_words'],
        'encoded_asr_through_seconds':encoded_audio_audit['through_seconds'],
        'subtitle_cues':len(blocks),'subtitle_exact_script_match':True,
        'caption_timing':'local Whisper small.en with documented exact-script correction/interpolation',
        'external_submission_or_publication':False,'known_remaining_blockers':[]}
    (P/'qa/capacity_final_qa.json').write_text(json.dumps(qa,indent=2)+'\n')
    print(json.dumps({k:qa[k] for k in ['passed','duration_seconds','video_sha256','subtitle_cues']}))


if __name__=='__main__':
    main()
