"""Derive canonical complete-path timing from saved probe states; no execution."""
from pathlib import Path
import json
import statistics

run=Path(__file__).resolve().parents[1]
rows=[]
for path in sorted(run.glob('*-s*.json')):
    case=json.loads(path.read_text())
    state=case['final']
    patients=[]
    for pid,patient in state['patients'].items():
        progress=state['patient_states'][pid]
        complete={str(i) for i in range(len(patient['pathway']))}==set(progress['scheduled_steps'])
        end=progress['scheduled_steps'][str(len(patient['pathway'])-1)]['end_time'] if complete else None
        patients.append({'patient':pid,'complete_path':complete,'resource_failures':progress['resource_failures'],
                         'end':end,'arrival':patient['arrival_time'],
                         'flow':end-patient['arrival_time'] if complete else None})
    complete=all(p['complete_path'] for p in patients)
    rows.append({'seed':case['summary']['seed'],'condition':case['summary']['condition'],'patients':patients,
                 'scheduled_makespan':max(p['end'] for p in patients) if complete else None,
                 'scheduled_flow_sum':sum(p['flow'] for p in patients) if complete else None})
groups={}
for condition in sorted({r['condition'] for r in rows}):
    group=sorted((r for r in rows if r['condition']==condition),key=lambda r:r['seed'])
    groups[condition]={}
    for key in ('scheduled_makespan','scheduled_flow_sum'):
        values=[r[key] for r in group]
        complete=all(v is not None for v in values)
        groups[condition][key]={'values':values,'scenario_denominator':6,
            'mean':statistics.mean(values) if complete else None,
            'sample_sd':statistics.stdev(values) if complete else None,
            'sample_variance':statistics.variance(values) if complete else None}
with (run/'timing_analysis.json').open('x') as handle:
    json.dump({'kind':'saved-state analysis, not another experiment','cases':rows,'groups':groups,
               'missing_step_penalties_imputed':False},handle,indent=2,sort_keys=True)
    handle.write('\n')
print(json.dumps(groups,sort_keys=True))
