"""Decode the actual delivery MP4 at semantic proof times for visual review."""
from pathlib import Path
import json
import subprocess
P=Path(__file__).resolve().parent
T=json.loads((P/'audio_timing.json').read_text())
video=P/'../../../../output/video/hospital_research_explainer.mp4'
qa=P/'qa/decoded'
qa.mkdir(parents=True,exist_ok=True)
proof=[('first',0)]
proof += [(s['id'],round(s['start']+s['duration']-.8,3)) for s in T['scenes']]
proof += [(f'kit-{i}',at) for i,at in enumerate([36.9,38.7,40.5,42.1])]
proof += [('last',177.566)]
for name,at in proof:
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(video),'-frames:v','1','-q:v','2',str(qa/f'{name}.jpg')],check=True)
(P/'qa/decoded_frames.json').write_text(json.dumps([{'name':name,'time':at,'path':f'qa/decoded/{name}.jpg'} for name,at in proof],indent=2)+'\n')
print('Decoded',len(proof),'proof frames')
