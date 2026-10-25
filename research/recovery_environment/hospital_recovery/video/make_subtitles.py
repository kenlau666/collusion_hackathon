"""Match the exact narration script to free local ASR timings; emit sidecar SRT."""
import difflib
import json
from pathlib import Path
import re
P=Path(__file__).resolve().parent
asr=json.loads((P/'assets/audio/raw/transcript.json').read_text())
scenes=json.loads((P/'audio_timing.json').read_text())['scenes']
expected=[]
for s in scenes:
    for word in s['text'].split():expected.append({'text':word,'scene':s['id']})
def norm(x):return re.sub(r'[^a-z0-9]','',x.lower())
a=[norm(w['text']) for w in expected];b=[norm(w['text']) for w in asr]
matcher=difflib.SequenceMatcher(a=a,b=b,autojunk=False)
changes=[]
for tag,i,j,k,l in matcher.get_opcodes():
    if tag=='equal':
        for u,v in zip(range(i,j),range(k,l)):expected[u].update(start=asr[v]['start'],end=asr[v]['end'],alignment='exact-ASR')
    else:
        changes.append({'tag':tag,'script':' '.join(w['text'] for w in expected[i:j]),'asr':' '.join(w['text'] for w in asr[k:l])})
        if i==j:continue
        start=asr[k]['start'] if k<l else asr[max(0,k-1)]['end']
        end=asr[l-1]['end'] if k<l else (asr[l]['start'] if l<len(asr) else start+.25)
        span=max(.15,end-start)
        for v,u in enumerate(range(i,j)):expected[u].update(start=start+span*v/(j-i),end=start+span*(v+1)/(j-i),alignment='script-corrected interpolation')
def stamp(t):
    n=round(t*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,ms=divmod(n,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'
chunks=[];group=[]
for w in expected:
    if group and (group[-1]['scene']!=w['scene'] or len(group)>=8):chunks.append(group);group=[]
    group.append(w)
    if len(group)>=3 and w['text'].endswith(('.', '?', '!')):chunks.append(group);group=[]
if group:chunks.append(group)
lines=[]
for i,g in enumerate(chunks):
    start=g[0]['start'];end=max(start+.4,g[-1]['end'])
    if i+1<len(chunks):end=min(end,chunks[i+1][0]['start'])
    lines += [str(i+1),stamp(start)+' --> '+stamp(end),' '.join(w['text'] for w in g),'']
(P/'hospital_research_explainer.srt').write_text('\n'.join(lines))
(P/'subtitle_alignment.json').write_text(json.dumps({'engine':'local Whisper small.en','no_paid_api':True,'word_count':len(expected),'cues':len(chunks),'script_corrections':changes,'words':expected},indent=2)+'\n')
print({'cues':len(chunks),'script_words':len(expected),'asr_words':len(asr),'corrections':changes})
