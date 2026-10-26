"""Align the exact report-companion script to free, local voice ASR."""
import difflib
import hashlib
import json
from pathlib import Path
import re

P=Path(__file__).resolve().parent
T=json.loads((P/'audio_timing.json').read_text())
asr_path=P/'assets/audio/raw/transcript.json'
asr=json.loads(asr_path.read_text())
expected=[dict(text=word,scene=s['id']) for s in T['scenes'] for word in s['text'].split()]
norm=lambda x:re.sub(r'[^a-z0-9]','',x.lower())
matcher=difflib.SequenceMatcher(a=[norm(w['text']) for w in expected],
                              b=[norm(w['text']) for w in asr],autojunk=False)
changes=[]
for tag,i,j,k,l in matcher.get_opcodes():
    if tag=='equal':
        for u,v in zip(range(i,j),range(k,l)):
            expected[u].update(start=asr[v]['start'],end=asr[v]['end'],alignment='exact-ASR')
    else:
        changes.append(dict(tag=tag,script=' '.join(w['text'] for w in expected[i:j]),
                            asr=' '.join(w['text'] for w in asr[k:l])))
        if i==j:continue
        start=asr[k]['start'] if k<l else asr[max(0,k-1)]['end']
        end=asr[l-1]['end'] if k<l else (asr[l]['start'] if l<len(asr) else start+.25)
        span=max(.1,end-start)
        for v,u in enumerate(range(i,j)):
            expected[u].update(start=start+span*v/(j-i),end=start+span*(v+1)/(j-i),
                               alignment='script correction; interpolated over ASR span')

def stamp(t):
    n=round(t*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,ms=divmod(n,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

chunks=[];group=[]
for w in expected:
    if group and (group[-1]['scene']!=w['scene'] or len(group)>=6):
        chunks.append(group);group=[]
    group.append(w)
    if len(group)>=3 and w['text'].endswith(('.','?','!')):
        chunks.append(group);group=[]
if group:chunks.append(group)
lines=[];last_end=0
for i,g in enumerate(chunks):
    start=max(g[0]['start'],last_end)
    end=max(start+.15,g[-1]['end'])
    if i+1<len(chunks):end=min(end,chunks[i+1][0]['start'])
    assert 0<=start<end<=T['duration'],(i,start,end)
    lines += [str(i+1),stamp(start)+' --> '+stamp(end),' '.join(w['text'] for w in g),'']
    last_end=end
(P/'hospital_reserve_research_explainer.srt').write_text('\n'.join(lines))
audit=dict(engine='Free local Whisper small.en',paid_api_calls=0,word_count=len(expected),
           asr_word_count=len(asr),cues=len(chunks),script_corrections=changes,words=expected,
           asr_sha256=hashlib.sha256(asr_path.read_bytes()).hexdigest(),
           voice_track_sha256=hashlib.sha256((P/'assets/audio/raw/voice-combined.wav').read_bytes()).hexdigest())
(P/'incident_subtitle_alignment.json').write_text(json.dumps(audit,indent=2)+'\n')
(P/'qa/incident_voice_transcript.json').write_text(json.dumps(asr,indent=2)+'\n')
print(json.dumps(dict(cues=len(chunks),script_words=len(expected),asr_words=len(asr),corrections=changes),indent=2))
