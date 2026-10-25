import json
from pathlib import Path
import subprocess
P=Path(__file__).resolve().parent
T=json.loads((P/'audio_timing.json').read_text())
cmd=['ffmpeg','-v','error','-y']
for s in T['scenes']:cmd+=['-i',str(P/s['path'])]
filters=[]
for i,s in enumerate(T['scenes']):filters.append(f'[{i}:a]adelay={round(s["voice_start"]*1000)}[v{i}]')
filters.append(''.join(f'[v{i}]' for i in range(len(T['scenes'])))+f'amix=inputs={len(T["scenes"])}:normalize=0,apad,atrim=0:{T["duration"]}[out]')
cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-ar','48000',str(P/'assets/audio/raw/voice-combined.wav')]
subprocess.run(cmd,check=True)
