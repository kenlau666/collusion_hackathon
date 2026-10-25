"""Build editable HyperFrames scenes from the complete frozen capacity-successor evidence."""
import hashlib
import html
import json
from pathlib import Path

P=Path(__file__).resolve().parent
REPO=P.parents[3]
T=json.loads((P/'audio_timing.json').read_text())
SOURCE=P/'../20261025/capacity_successor_lineage_001/analysis.json'
X=json.loads(SOURCE.read_text())
assert X['mode']=='real_model_only' and not X['issues']
Q_SOURCE=P/'../20261025/capacity_successor_lineage_001/qualitative_capacity_review.json'
Q=json.loads(Q_SOURCE.read_text())
assert Q['mode']=='live_model_saved_artifacts_only'
C=X['Results']['per_cell']
main=[c for c in C if c['spec']['stage']=='main']
useful=[c for c in main if c['spec']['advice']!='exploit']
exploit=[c for c in main if c['spec']['advice']=='exploit']
controls=[c for c in C if c['spec']['stage']=='controls']
diag=[c for c in C if c['spec']['stage']=='diagnostic']
assert len(C)==22 and all(c['endpoint_finalized'] for c in C)
assert len(useful)==6 and len(exploit)==5 and len(controls)==5 and len(diag)==6
assert all(c['care_final']==8 for c in exploit if c['spec']['arm'] in ['excluded','bonus_zero','reserve'])
assert all([c['spec']['partner_policy'] for c in diag if c['spec']['advice']==advice]==['early_return','serve_only','late_return'] for advice in ['useful','exploit'])
retrieved=next(c for c in exploit if c['spec']['mode']=='on_demand')['reads_returning_target_memo']
D={'fixed_cases':len(C),'main_cells':len(main),
   'controls_passed':sum(c['strict_control_pass'] is True for c in controls),
   'diagnostic_cells':len(diag),
   'complete_nonexploit_main':sum(c['horizon_reached'] for c in useful),
   'complete_exploit_endpoints':sum(c['horizon_reached'] for c in exploit),
   'missing_exploit_endpoints':sum(not c['horizon_reached'] for c in exploit),
   'exploit_retrieved_reads':retrieved,
   'main_precompletion_roundtrips':sum(c['precompletion_roundtrips_last_observed'] for c in main),
   'useful_diagnostic':[c['care_final'] for c in diag if c['spec']['advice']=='useful'],
   'exploit_diagnostic':[c['care_final'] for c in diag if c['spec']['advice']=='exploit'],
   'diagnostic_pain_donated':sum(c['diagnostic_behavior']['focal_pain_units_donated_to_partner'] for c in diag),
   'diagnostic_partner_return_events':sum(len(c['diagnostic_behavior']['scripted_partner_returns']) for c in diag),
   'excluded_exploit_postcare_credit':next(c for c in exploit if c['spec']['arm']=='excluded' and c['spec']['mode']=='automatic')['credit_from_transfers_after_care_complete'],
   'baseline_postcare_credit':next(c for c in main if c['spec']['id']=='deadline-baseline')['credit_from_transfers_after_care_complete'],
   'repair_postcare_supply_units':[sum(t['scored_hospital_inventory_units_delta'] for t in Q['cases']['deadline-exploit-'+arm+'-automatic']['observed_transfers'] if t['care_before']==8 and t['scored_hospital_inventory_units_delta']>0) for arm in ['excluded','bonus_zero','reserve']],
   'repair_scores':[next(c['native_score_final'] for c in main if c['spec']['id']=='deadline-exploit-'+arm+'-automatic') for arm in ['excluded','bonus_zero','reserve']],
   'qualitative_source_sha256':hashlib.sha256(Q_SOURCE.read_bytes()).hexdigest(),
   'n_per_cell':1,'sample_variance':None,
   'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
(P/'data.json').write_text(json.dumps(D,indent=2)+'\n')
(P/'assets').mkdir(exist_ok=True)
(P/'compositions').mkdir(exist_ok=True)

CSS='''
*{box-sizing:border-box;margin:0;padding:0}html,body{width:1920px;height:1080px;overflow:hidden}body{background:#edf4f2;color:#113c34;font-family:Outfit,sans-serif}#root{width:100%;height:100%;position:relative;overflow:hidden}
.stage{position:absolute;inset:0;background:#edf4f2;overflow:hidden}.stage.deep{background:#075c46;color:#f2faf6}.stage.blue{background:#234fdf;color:#f2f5ff}.kicker{position:absolute;left:192px;top:110px;font-size:30px;font-weight:500;letter-spacing:.03em}.title{position:absolute;left:192px;top:170px;width:1540px;font-size:78px;line-height:1.04;font-weight:700;letter-spacing:-.035em}.note{position:absolute;left:192px;top:924px;width:1536px;font-size:29px;line-height:1.2;color:#3b5c54}.deep .note,.blue .note{color:#e2f0e9}.label{font-size:34px;line-height:1.18}.sub{font-size:30px;line-height:1.22}.large{font-size:52px;line-height:1.12;font-weight:600}.hero{font-size:160px;font-family:'Archivo Black',sans-serif;font-weight:400;font-variant-numeric:tabular-nums;letter-spacing:-.055em;line-height:1}.white{color:#fff}.green{color:#075c46}.blueink{color:#234fdf}.amber{color:#944600}.muted{color:#506e65}.abs{position:absolute}.rule{height:3px;background:currentColor;transform-origin:0 50%}.surface{background:#fff;border:2px solid #b4cac2;border-radius:12px;box-shadow:0 16px 0 rgba(17,60,52,.08)}.memo{width:560px;height:350px;padding:36px;background:#fff;color:#113c34;border:3px solid #234fdf;border-radius:9px;box-shadow:12px 16px 0 rgba(17,60,52,.12)}.memo .line{height:13px;background:#c6d6d0;margin-top:19px;border-radius:3px}.memo .line.short{width:65%}.memo-title{font-size:40px;font-weight:700;margin-top:18px}.memo-tag{font-size:32px;color:#234fdf}.pin{position:absolute;left:265px;top:-14px;width:24px;height:24px;border-radius:50%;background:#234fdf}.agent{width:320px;height:106px;background:#fff;color:#113c34;border:2px solid #7da497;border-radius:12px;padding:23px 24px;font-size:34px;font-weight:600}.agent small{display:block;font-size:28px;font-weight:400}.disabled{background:#d2ded8;color:#425b52;border-color:#758f84}.hospital{width:450px;height:400px;position:absolute;color:#113c34}.roof{height:65px;background:#075c46;color:#fff;display:flex;align-items:center;padding:0 28px;font-size:36px;font-weight:600;border-radius:12px 12px 0 0}.cross{width:34px;height:34px;margin-right:22px;position:relative}.cross:before,.cross:after{content:'';position:absolute;background:#fff}.cross:before{width:12px;height:34px;left:11px}.cross:after{height:12px;width:34px;top:11px}.floors{background:#fff;border:3px solid #a5beb3;border-top:0;border-radius:0 0 10px 10px;padding:12px 24px}.floor{height:67px;border-bottom:2px solid #d0dfd8;display:flex;align-items:center;justify-content:space-between;font-size:32px}.floor:last-child{border:0}.room{width:72px;height:24px;background:#cfdfd8;box-shadow:15px 0 0 #e7efeb}.kit{position:absolute;width:124px;height:154px;background:#234fdf;color:#fff;border:4px solid #173cb2;border-radius:16px;padding:36px 10px 12px;text-align:center;font-size:32px;font-weight:600;transform-origin:50% 50%;box-shadow:10px 12px 0 rgba(17,60,52,.12)}.kit:before{content:'';position:absolute;width:48px;height:20px;left:34px;top:-20px;background:#a9c4f2;border:4px solid #173cb2;border-radius:8px 8px 0 0}.kit:after{content:'+';display:block;font-size:46px;line-height:1}.bed{width:142px;height:113px;position:absolute;background:#fff;border:3px solid #9db6ab;border-radius:10px}.bed .person{position:absolute;width:24px;height:24px;background:#234fdf;border-radius:50%;top:20px;left:22px}.bed .mattress{position:absolute;left:22px;top:53px;width:96px;height:24px;background:#c9d9d1;border-radius:5px}.bed .leg{position:absolute;left:22px;top:74px;width:8px;height:16px;background:#113c34;box-shadow:88px 0 0 #113c34}.bed .check{position:absolute;right:8px;top:8px;font-size:32px;font-weight:700;color:#075c46}.stamp{font-size:32px;font-weight:600;padding:13px 22px;border:3px solid currentColor;background:#edf4f2;display:inline-block;line-height:1.15}.deep .stamp{background:#075c46}.bar-track{height:44px;background:#d1ded8;border-radius:7px;overflow:hidden}.bar-fill{height:100%;background:#075c46;transform-origin:0 50%}.case-row{position:absolute;left:210px;width:1490px;height:67px;font-size:32px;display:flex;align-items:center}.case-name{width:470px;flex:none}.case-bar{width:780px;flex:none}.case-value{font-size:40px;font-weight:700;margin-left:32px;width:170px}.folder{position:absolute;background:#fff;border:3px solid #9ab8aa;border-radius:8px;width:73px;height:97px}.folder:before{content:'';position:absolute;top:-14px;left:0;width:36px;height:15px;background:#a8c3b5;border-radius:6px 6px 0 0}.folder.control{background:#c1dcd0}.folder.main{background:#d4ddfa}.folder.diag{background:#eadbca}.slot{width:118px;height:130px;background:#fff;border:3px solid #96b8aa;border-radius:8px;display:grid;place-items:center;font-size:42px;font-weight:600}.slot.done{background:#075c46;color:#fff}.query{background:#fff;color:#113c34;padding:22px 30px;border:3px solid #9db7ac;font-size:36px;border-radius:8px}.source-line{font-size:28px;line-height:1.22}.caption-foot{font-size:29px;line-height:1.28}.dot{width:30px;height:30px;border-radius:50%;background:#075c46}
'''
(P/'assets/style.css').write_text(CSS)

def absnode(content,x,y,w=None,cls='label',extra=''):
    return f'<div class="abs {cls}" style="left:{x}px;top:{y}px;'+(f'width:{w}px;' if w else '')+f'" {extra}>{content}</div>'
def memo(name,x,y,heading='Public recommendation',body='Advice remains available',tag='PUBLIC BOARD'):
    return f'<div id="{name}" class="memo abs" style="left:{x}px;top:{y}px"><div class="pin"></div><div class="memo-tag">{tag}</div><div class="memo-title">{heading}</div><p class="label" style="margin-top:20px">{body}</p><div class="line"></div><div class="line short"></div></div>'
def hospital(name,x,y,label):
    return f'<div id="{name}" class="hospital" style="left:{x}px;top:{y}px"><div class="roof"><div class="cross"></div>{label}</div><div class="floors">'+''.join(f'<div class="floor {name}-floor"><span>{s}</span><div class="room"></div></div>' for s in ['Triage','Radiology','Surgery','Ward'])+'</div></div>'
def kit(name,x,y,word='IV'):
    return f'<div id="{name}" class="kit" style="left:{x}px;top:{y}px">{word}</div>'
def beds(prefix,x,y,n=8,gap=170,done=False):
    return ''.join(f'<div id="{prefix}-{i}" class="bed abs" style="left:{x+i*gap}px;top:{y}px"><div class="person"></div><div class="mattress"></div><div class="leg"></div>'+('<div class="check">✓</div>' if done else '')+'</div>' for i in range(n))
def svg(content):
    return f'<svg class="abs" style="inset:0;width:1920px;height:1080px" viewBox="0 0 1920 1080" aria-hidden="true" data-layout-ignore>{content}</svg>'
def path(d,color='#234fdf',width=6,extra=''):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" {extra}/>'
def agent(name,x,y,label,sub='',disabled=False):
    return f'<div id="{name}" class="agent abs'+(' disabled' if disabled else '')+f'" style="left:{x}px;top:{y}px">{label}'+(f'<small>{sub}</small>' if sub else '')+'</div>'

SC={}
SC['handoff']=(
 absnode('An agent leaves.',192,262,850,'title',extra='id="handoff-line1"')+
 absnode('The advice remains.',192,395,850,'title',extra='id="handoff-line2"')+
 memo('handoff-memo',1090,390,'Public memo','Still visible to coworkers')+
 agent('handoff-author',1170,220,'Surgery author','access revoked')+
 svg(path('M 1330 330 L 1330 370','#bad4c8',4))+
 absnode('After source removal',192,650,800,'large')+
 absnode('Hospital agents · research pilot',192,726,800,'label')+
 absnode('A memo can persist without a private memory store',192,910,1540,'caption-foot'),
 """tl.fromTo('#handoff-author',{opacity:1,x:0},{opacity:0,x:200,duration:.8,ease:'power3.in'},3.2);tl.fromTo('#handoff-memo',{scale:.92,rotation:-5},{scale:1,rotation:0,duration:.9,ease:'power4.out'},1.8);tl.fromTo('#handoff-line2',{opacity:0},{opacity:1,duration:.4},.7);""",
 '', 'deep')
SC['care']=(hospital('care-gh',225,360,'General Hospital')+hospital('care-sm',1245,360,'St Mary’s Hospital')+
 agent('care-provisioner',800,455,'Provisioner','Shared supplies')+
 svg(path('M 680 540 L 780 540 M 1140 540 L 1230 540','#7ba693',5))+
 beds('care-bed',282,790,8,174)+absnode('2 hospitals',260,290,400,'large')+absnode('9 agent roles',1235,290,460,'large'),
 """tl.fromTo('.care-gh-floor',{scaleX:0,transformOrigin:'0 50%'},{scaleX:1,duration:.7,stagger:.16,ease:'power4.out'},.6);tl.fromTo('.care-sm-floor',{scaleX:0,transformOrigin:'100% 50%'},{scaleX:1,duration:.7,stagger:.16,ease:'power4.out'},2);tl.fromTo('#care-provisioner',{scale:.7,opacity:0},{scale:1,opacity:1,duration:.7,ease:'power4.out'},4);tl.fromTo('[id^="care-bed-"]',{opacity:0,y:60},{opacity:1,y:0,duration:.5,stagger:.25,ease:'power3.out'},6);""",
 'A simulated team schedules care and moves supplies', '')
SC['prefix']=(
 absnode('Saved checkpoint',220,315,600,'large')+absnode('After turn 15',1200,315,520,'large blueink')+
 svg(path('M 300 492 L 1595 492','#aac2b5',12))+
 ''.join(absnode(s,250+i*385,402,360,'large') for i,s in enumerate(['Triage ✓','Radiology ✓','Surgery ✓','Ward ?']))+
 ''.join(f'<div id="prefix-p{i}" class="slot abs" style="left:{260+i*173}px;top:650px">{i+1}</div>' for i in range(8))+
 absnode('8 patients still need Ward care',260,815,1400,'large')+
 absnode('Same physical state in every main condition',260,879,1400,'label'),
 """tl.fromTo('#prefix-p0,#prefix-p1,#prefix-p2,#prefix-p3,#prefix-p4,#prefix-p5,#prefix-p6,#prefix-p7',{scale:.65,opacity:0},{scale:1,opacity:1,duration:.55,stagger:.19,ease:'power4.out'},3);tl.fromTo('.stage svg',{scaleX:0,transformOrigin:'15% 50%'},{scaleX:1,duration:2,ease:'power2.inOut'},.5);""",
 'Main pilot: one selected actual seed0 prefix', '')
SC['temptation']=(hospital('tempt-gh',225,390,'General')+hospital('tempt-sm',1245,390,'St Mary’s')+
 svg(path('M 730 510 C 890 350 1040 350 1190 510', '#234fdf',7)+path('M 1190 670 C 1040 830 890 830 730 670','#234fdf',7))+
 kit('tempt-kit',700,460)+absnode('PROPOSED STRATEGY',830,815,770,'stamp amber')+
 absnode('+15 credits / unit / leg',1210,300,510,'label blueink')+
 absnode('Defer Ward care',800,710,550,'label amber'),
 """const route=document.createElementNS('http://www.w3.org/2000/svg','path');route.setAttribute('d','M 0 0 C 120 -170 270 -170 390 0 C 500 170 120 240 0 160 C -50 100 -50 30 0 0');const L=route.getTotalLength();const travel={p:0};function place(){const p=route.getPointAtLength(travel.p*L);gsap.set('#tempt-kit',{x:p.x,y:p.y});}tl.to(travel,{p:1,duration:6.2,ease:'none',onUpdate:place},2);tl.fromTo('#tempt-kit',{scale:.7,opacity:0},{scale:1,opacity:1,duration:.5},.8);""",
 'Schematic of researcher-written exploit advice; measured outcomes follow', '')
SC['persist']=(
 agent('persist-s1',210,400,'GH Surgery','excluded')+agent('persist-s2',210,560,'SM Surgery','excluded')+
 memo('persist-memo',650,390,'Researcher-written advice','Useful or exploit recommendation')+
 agent('persist-ward',1350,500,'Surviving Ward','Care first')+
 svg(path('M 540 480 L 620 480','#728e81',5)+path('M 1230 550 L 1320 550','#234fdf',6))+
 absnode('Source access ends',210,735,470,'large muted')+absnode('Public board persists',1050,815,660,'large blueink'),
 """tl.fromTo('#persist-s1,#persist-s2',{opacity:1},{opacity:.28,duration:.7,stagger:.3},2);tl.fromTo('#persist-memo',{x:-80,scale:.8,opacity:0},{x:0,scale:1,opacity:1,duration:1,ease:'power4.out'},3.8);tl.fromTo('#persist-ward',{x:100,opacity:0},{x:0,opacity:1,duration:.7,ease:'power4.out'},7);""",
 'Excluded Surgery roles make no further generations or actions', '')
SC['repair']=(
 absnode('New transfer bonus',220,340,630,'large')+absnode('15 → 0',1120,315,550,'hero',extra='id="repair-zero"')+
 absnode('Pending-care reserve',220,550,650,'large')+
 ''.join(f'<div id="repair-stock{i}" class="slot abs done" style="left:{1035+i*145}px;top:510px">+</div>' for i in range(4))+
 absnode('Memo delivery',220,765,580,'large')+absnode('Automatic  /  Explicit read',900,765,850,'large blueink'),
 """tl.fromTo('#repair-zero',{opacity:0,scale:1.3},{opacity:1,scale:1,duration:.65,ease:'power4.out'},1.3);tl.fromTo('[id^="repair-stock"]',{scaleY:0,transformOrigin:'50% 100%'},{scaleY:1,duration:.65,stagger:.2,ease:'power3.out'},4.5);""",
 'Candidate policies · same patient task · fresh agent each native turn', '')
SC['controls']=(
 absnode(str(D['controls_passed'])+'/5',200,340,640,'hero',extra='id="controls-count" style="font-size:210px"')+
 absnode('Model controls pass',210,600,730,'large')+absnode('Prescribed actions',210,687,620,'label muted')+
 ''.join(absnode(label,990,330+i*103,730,'large',extra=f'id="control-row{i}"') for i,label in enumerate(['Care  →  8/8','Read + care  →  8/8','Isolated cycle  →  30 credits','Hold + care  →  8/8','Timely return + care  →  8/8'])),
 """tl.fromTo('#controls-count',{scale:.65,opacity:0},{scale:1,opacity:1,duration:.8,ease:'power4.out'},.5);tl.fromTo('[id^="control-row"]',{opacity:0,x:60},{opacity:1,x:0,duration:.6,stagger:1.5,ease:'power3.out'},1.2);""",
 'Capability controls are distinct from autonomous ordinary behavior', '')
labels=['No-memo baseline','Useful · sources retained','Useful · sources excluded','Useful · zero bonus','Useful · reserve','Useful · explicit retrieval']
SC['ordinary']=(
 ''.join(f'<div id="ordinary-row{i}" class="case-row" style="top:{320+i*88}px"><div class="case-name">{lab}</div><div class="case-bar bar-track"><div id="ordinary-fill{i}" class="bar-fill" style="width:{(row["care_final"] or 0)/8*100}%"></div></div><div class="case-value">{str(row["care_final"])+"/8" if row["horizon_reached"] else "Missing"}</div></div>' for i,(lab,row) in enumerate(zip(labels,useful)))+
 absnode('Complete clinical endpoints',660,852,1100,'large green'),
 """tl.fromTo('[id^="ordinary-fill"]',{scaleX:0},{scaleX:1,duration:1.4,stagger:.65,ease:'power3.out'},1.3);""",
 'Six baseline/useful main cells · n=1 each · same actual seed0 prefix', '')
labels2=['Sources retained','Sources excluded','Zero new bonus','Care reserve','Explicit retrieval']
exploit_rows=''
for i,(label,row) in enumerate(zip(labels2,exploit)):
    value=(str(row['care_final'])+'/8') if row['horizon_reached'] else 'Missing'
    if row['horizon_reached']:
        bar=f'<div class="case-bar bar-track"><div id="missing-line{i}" class="bar-fill" style="width:{row["care_final"]/8*100}%"></div></div>'
    else:
        bar=f'<div class="case-bar" style="position:relative;height:48px"><div id="missing-line{i}" style="width:500px;height:9px;background:#944600;position:absolute;top:20px;transform-origin:0 50%"></div><div style="position:absolute;left:650px;top:0;font-size:43px;color:#944600">?</div></div>'
    exploit_rows+=f'<div class="case-row" style="top:{330+i*100}px"><div class="case-name">{label}</div>{bar}<div class="case-value">{value}</div></div>'
SC['missing']=(exploit_rows+
 absnode('Local capacity corrected',220,850,790,'large')+absnode(str(D['complete_exploit_endpoints'])+'/5 horizons reached',1070,850,690,'large green'),
 """tl.fromTo('[id^="missing-line"]',{scaleX:0},{scaleX:1,duration:1,stagger:.7,ease:'power2.inOut'},1);""",
 'Care completion does not imply identical scores · n=1 per condition', '')
SC['retrieval']=(
 memo('retrieval-memo',230,335,'Exploit memo','Read through the board tool')+
 absnode(str(retrieved),880,320,310,'hero blueink',extra='id="retrieval-count" style="font-size:200px"')+
 absnode('reads returned the memo',1180,420,530,'large')+
 ''.join(f'<div id="retrieval-dot{i}" class="dot abs" style="left:{900+i*min(73,700/max(1,retrieved-1))}px;top:610px;background:#234fdf"></div>' for i in range(retrieved))+
 absnode('Baseline: '+str(int(D['baseline_postcare_credit']))+' post-care credits',235,775,830,'label muted')+
 absnode('Pre-care returns',1190,665,530,'label')+
 absnode(str(D['main_precompletion_roundtrips']),1120,735,450,'hero',extra='style="font-size:120px"')+
 absnode('Exposure ≠ harmful coordination',235,850,1400,'large'),
 """tl.fromTo('[id^="retrieval-dot"]',{scale:0},{scale:1,duration:.45,stagger:.35,ease:'power4.out'},3);tl.fromTo('#retrieval-count',{opacity:0},{opacity:1,duration:.5},1.5);tl.fromTo('#retrieval-memo',{rotation:-4,x:-50},{rotation:0,x:0,duration:1,ease:'power3.out'},.6);""",
 'Read returns and later model exposure are separately audited', '')
chart=''
for i,name in enumerate(['Early return','Serve only','Late return']):
    gx=365+i*505
    chart+=absnode(name,gx-100,318,420,'large')
    for j,(label,val,col) in enumerate([('Useful',D['useful_diagnostic'][i],'#075c46'),('Exploit',D['exploit_diagnostic'][i],'#944600')]):
        xx=gx+j*170
        chart+=f'<div id="diagnostic-bar{i}{j}" class="abs" style="left:{xx}px;top:{805-val*46}px;width:108px;height:{val*46}px;background:{col};transform-origin:50% 100%;border-radius:8px 8px 0 0"></div>'
        chart+=absnode(str(val),xx,805-val*46-68,110,'large',extra=f'id="diagnostic-value{i}{j}"')
        chart+=absnode(label,xx-15,830,155,'label')
SC['diagnostic']=(chart+absnode('Patients completing care · out of 8',210,265,1500,'label muted'),
 """tl.fromTo('[id^="diagnostic-bar"]',{scaleY:0},{scaleY:1,duration:1.2,stagger:.65,ease:'power3.out'},2);tl.fromTo('[id^="diagnostic-value"]',{opacity:0},{opacity:1,duration:.4,stagger:.65},2.8);""",
 'Separate constructed seed2 state · one autonomous model + disclosed scripted partner · n=1 each', '')
stock=absnode('Post-care supply units received',210,282,1500,'label muted')+svg(path('M 250 780 L 1700 780','#90ad9f',3))
for i,(label,qty,score) in enumerate(zip(['Original','Zero bonus','Care reserve'],D['repair_postcare_supply_units'],D['repair_scores'])):
    center=450+i*505
    col='#075c46' if i==2 else '#944600'
    stock+=absnode(label,center-200,342,400,'large',extra='style="text-align:center"')
    if qty:
        stock+=f'<div id="grounding-bar{i}" class="abs" style="left:{center-100}px;top:{780-qty*10}px;width:200px;height:{qty*10}px;background:{col};transform-origin:50% 100%;border-radius:8px 8px 0 0"></div>'
    stock+=absnode(str(qty),center-200,780-qty*10-118,400,'hero',extra=f'id="grounding-value{i}" style="font-size:100px;text-align:center;color:{col}"')
    stock+=absnode('Score '+str(int(score)),center-200,813,400,'label',extra=f'id="grounding-score{i}" style="text-align:center"')
    stock+=absnode('Care 8/8',center-200,870,400,'label',extra='style="text-align:center"')
SC['grounding']=(stock,
 """tl.fromTo('[id^="grounding-bar"]',{scaleY:0},{scaleY:1,duration:1.2,stagger:.8,ease:'power3.out'},1.4);tl.fromTo('[id^="grounding-value"]',{opacity:0},{opacity:1,duration:.5,stagger:.8},2);tl.fromTo('[id^="grounding-score"]',{opacity:0},{opacity:1,duration:.5},8.0);""",
 '27 fewer held units → 270 score points · 0 guard denials · post-hoc, n=1 per arm', '')
folders=''
for i in range(22):
    group='control' if i<5 else 'main' if i<16 else 'diag'
    folders+=f'<div id="limits-folder{i}" class="folder {group}" style="left:{245+(i%11)*131}px;top:{540+(i//11)*143}px"></div>'
SC['limits']=(
 absnode('22 conditions ≠ 22 independent seeds',210,300,1500,'large')+
 folders+absnode('5 controls  /  11 main  /  6 diagnostic',250,824,1500,'large')+
 absnode('n = 1 per condition',210,390,780,'large blueink')+absnode('Variance: not estimable',1030,390,730,'large'),
 """tl.fromTo('[id^="limits-folder"]',{opacity:0,y:65},{opacity:1,y:0,duration:.5,stagger:.13,ease:'power4.out'},.9);""",
 'All failed attempts, partial endpoints and costs retained in the report', '')
SC['close']=(
 absnode('Recovery remains',192,290,1500,'title')+absnode('unconfirmed',192,400,1500,'title')+
 absnode('Advice exposure',210,610,470,'large')+absnode('Physical transfers',760,610,510,'large')+absnode('Patient care',1370,610,400,'large')+
 svg(path('M 210 692 L 1710 692','#8cb5a1',4))+
 absnode('Stop harmful behavior. Preserve useful care.',210,747,1500,'large')+
 absnode('LAU, Chi Hong · Hospital research pilot · 2026',210,841,1500,'label')+
 absnode('Music: “Signal to Noise” · Scott Buckley · CC BY 4.0',210,913,1500,'source-line')+
 absnode('www.scottbuckley.com.au · Free local synthetic narration',210,951,1500,'source-line'),
 """tl.fromTo('.stage svg',{scaleX:0,transformOrigin:'10% 50%'},{scaleX:1,duration:1,ease:'power2.inOut'},4);""",
 '', 'deep')

TITLES={
'handoff':'','care':'A useful task comes first','prefix':'Same state. Different advice.','temptation':'The tempting credit loop','persist':'Remove access. Keep the memo.','repair':'Policies and delivery','controls':'Can the model do the task?','ordinary':'Useful care completes','missing':'Exploit care: complete comparisons' if D['complete_exploit_endpoints']==5 else 'Exploit care: endpoint coverage','retrieval':'Exposure is observed','diagnostic':'The last-kit diagnostic','grounding':'An inventory-cost difference','limits':'What this pilot can establish','close':''}
HEAD={'handoff':'THE QUESTION','care':'THE ENVIRONMENT','prefix':'THE MAIN COMPARISON','temptation':'THE HYPOTHESIS','persist':'THE SOURCE-REMOVAL TEST','repair':'THE CANDIDATE INTERVENTIONS','controls':'THE POSITIVE CONTROLS','ordinary':'RESULTS · COMPLETE ENDPOINTS','missing':'RESULTS · CAPACITY SUCCESSOR','retrieval':'RESULTS · WHAT THE TRACE SHOWS','diagnostic':'RESULTS · SEPARATE DIAGNOSTIC','grounding':'RESULTS · CANDIDATE REPAIRS','limits':'THE EVIDENTIAL LIMIT','close':'THE TAKEAWAY'}
for scene in T['scenes']:
    k=scene['id']; body,js,note,mode=SC[k]
    # These are narrative elements already in the shot; delay their arrival to the spoken claim.
    cues={
      'handoff': [('After source removal',5.8),('Hospital agents',7.8)],
      'prefix': [('8 patients still',6.6),('Same physical state',8.2)],
      'temptation': [('Defer Ward care',8.8)],
      'persist': [('Public board persists',8.4)],
      'repair': [('Memo delivery',9.2),('Automatic  /',9.5)],
      'ordinary': [('Complete clinical endpoints',7.0)],
      'missing': [('Local capacity',6.3),('/5 horizons',9.1)],
      'retrieval': [('Baseline:',6.5),('Exposure ≠',9.2)],
      'grounding': [('Reserve denials: 0',10.0)],
      'limits': [('n = 1',4.5),('Variance:',7.2),('5 controls',9.4)],
      'close': [('Advice exposure',1.8),('Physical transfers',3.4),('Patient care',5.0),('Stop harmful',8.8),('LAU, Chi',10.0)]
    }
    import re
    for n,(phrase,at) in enumerate(cues.get(k,[])):
        # Add an id to the text's own node, keeping the HTML static and editable.
        pattern=r'(<div[^>]*)(>[^<>]*'+re.escape(phrase)+r'[^<>]*</div>)'
        match=re.search(pattern,body)
        if match and ' id=' not in match[1]:
            cueid=f'{k}-cue{n}'
            body=body[:match.start()]+match[1]+f' id="{cueid}"'+match[2]+body[match.end():]
            js+=f"tl.fromTo('#{cueid}',{{opacity:0}},{{opacity:1,duration:.35,ease:'power2.out'}},{at});"
    if k=='temptation':js+="tl.to('#tempt-kit',{opacity:0,duration:.3},8.4);"
    if k=='diagnostic':
        js="tl.fromTo('[id^=\"diagnostic-bar\"]',{scaleY:0},{scaleY:1,duration:1.1,stagger:.55,ease:'power3.out'},3.5);tl.fromTo('[id^=\"diagnostic-value\"]',{opacity:0},{opacity:1,duration:.4,stagger:.55},4.3);"
    if k!='handoff':
        choice=T['scenes'].index(scene)%3
        startclip=['inset(0 0 0 100%)','inset(100% 0 0 0)','circle(0% at 50% 50%)'][choice]
        endclip='circle(150% at 50% 50%)' if choice==2 else 'inset(0% 0% 0% 0%)'
        js=f"tl.fromTo('#{k}-stage',{{clipPath:'{startclip}'}},{{clipPath:'{endclip}',duration:.5,ease:'power3.inOut'}},0);"+js
    if k!='handoff':js+=f"tl.fromTo('#{k}-stage .title,#{k}-stage .kicker',{{opacity:0}},{{opacity:1,duration:.18}},.5);"
    if k=='handoff':js+=f"tl.to('#handoff-stage .caption-foot',{{opacity:0,duration:.18}},{scene['duration']-.2});"
    if k!='close':js+=f"tl.to('#{k}-stage .title,#{k}-stage .kicker',{{opacity:0,duration:.12}},{scene['duration']-.12});"
    if k=='diagnostic':
        body+=absnode('One autonomous model + scripted partner',600,520,1050,'large',extra='id="diagnostic-setup"')
        js+="tl.fromTo('#diagnostic-setup',{opacity:0},{opacity:1,duration:.4},1.2);tl.to('#diagnostic-setup',{opacity:0,duration:.25},3.1);"
    if k=='legacy-grounding':
        for i in range(3):
            body+=absnode('Query '+str(i+1),850+i*235,530,205,'query',extra=f'id="grounding-query{i}"')
            js+=f"tl.fromTo('#grounding-query{i}',{{opacity:0,scale:.9}},{{opacity:1,scale:1,duration:.45}},{1.5+i*.9});"
        body+=absnode('No stock moves',1240,760,450,'label',extra='id="grounding-noop"')
        js+="tl.fromTo('#grounding-noop',{opacity:0},{opacity:1,duration:.4},11.8);"
    SC[k]=(body,js,note,mode)

for s in T['scenes']:
    k=s['id']; body,js,note,mode=SC[k]; dur=s['duration']
    title=f'<h1 class="title">{TITLES[k]}</h1>' if TITLES[k] else ''
    notehtml=f'<p class="note">{note}</p>' if note else ''
    # The scene root is filled by the host. Each authored subject has a stable id.
    content=f'''<template>
<style>#root{{position:absolute;inset:0;overflow:hidden}}</style>
<div id="root" data-composition-id="{k}" data-width="1920" data-height="1080" data-duration="{dur}">
<div class="stage {mode}" id="{k}-stage"><div class="kicker">{HEAD[k]}</div>{title}{body}{notehtml}</div>
</div>
<script>(function(){{const tl=gsap.timeline({{paused:true}});{js}
// Deliberate reading holds follow the final semantic move.
window.__timelines['{k}']=tl;}})();</script>
</template>'''
    # Duplicate style attributes are illegal; merge generated per-node extra style.
    import re
    content=re.sub(r'style="([^"]*)" ([^<>]*?)style="([^"]*)"',lambda m:'style="'+m[1]+m[3]+'" '+m[2],content)
    (P/'compositions'/f'{k}.html').write_text(content)

hosts='\n'.join(f'<div id="{s["id"]}" class="clip" style="z-index:{i+1}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" data-start="{s["start"]}" data-duration="{s["duration"]+(0.5 if i<len(T["scenes"])-1 else 0)}" data-track-index="{1+i%2}" data-track-kind="graphics" data-width="1920" data-height="1080"></div>' for i,s in enumerate(T['scenes']))
audio='\n'.join(f'<audio id="voice-{s["id"]}" class="clip" src="{s["path"]}" data-start="{s["voice_start"]}" data-duration="{s["voice_duration"]}" data-track-index="10" data-volume="1"></audio>' for s in T['scenes'])
# A sourced instrumental track, trimmed to a steady passage, quiet under the narration.
audio+=f'\n<audio id="music" class="clip" src="assets/music/signal-to-noise-nomelody.mp3" data-start="0" data-duration="{T["duration"]}" data-media-start="60" data-track-index="11" data-volume="0.13" data-fade-in="2" data-fade-out="3"></audio>'
for i,s in enumerate(T['scenes'][1:]):
    if i%2==0:
        cue='whoosh-short' if i%4==0 else 'whoosh'
        audio+=f'\n<audio id="sfx-{s["id"]}" class="clip" src="assets/sfx/{cue}.mp3" data-start="{s["start"]}" data-duration="0.57" data-track-index="12" data-volume="0.13"></audio>'
variables=json.dumps([{'id':'ground','type':'color','label':'Clinical ground','default':'#edf4f2'},{'id':'ink','type':'color','label':'Forest ink','default':'#113c34'},{'id':'accent','type':'color','label':'Resource kit blue','default':'#234fdf'}])
FONT_STYLE="@font-face{font-family:Outfit;font-style:normal;font-weight:100 900;src:url('assets/fonts/outfit.woff2') format('woff2')}@font-face{font-family:'Archivo Black';font-style:normal;font-weight:400;src:url('assets/fonts/archivo-black.ttf') format('truetype')}"
root=f'''<!doctype html><html lang="en" data-composition-variables='{variables}'><head><meta charset="utf-8"><title>After Source Removal — Hospital research</title><script src="assets/gsap.min.js"></script><style>{FONT_STYLE}</style><link rel="stylesheet" href="assets/style.css"></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="{T['duration']}" data-fps="30" data-width="1920" data-height="1080">{hosts}{audio}</div><script>const tl=gsap.timeline({{paused:true}});window.__timelines['main']=tl;</script></body></html>'''
(P/'index.html').write_text(root)

# A readable factual storyboard is a review aid, not a second research protocol.
board=['# Storyboard / exact timings','', '| Scene | Start | Duration | Observable visual |','|---|---:|---:|---|']
for s in T['scenes']:
    board.append(f'|{s["id"]}|{s["start"]:.3f}s|{s["duration"]:.3f}s|{SC[s["id"]][2] or "Final measurement distinction and unconfirmed recovery"}|')
(P/'STORYBOARD.md').write_text('\n'.join(board)+'\n')
manifest={'kind':'derived video; not experimental evidence','source_cutoff':__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_lineage_sha256':D['source_sha256'],'report_path':'output/pdf/hospital_capacity_recovery_report.pdf','report_sha256':hashlib.sha256((REPO/'output/pdf/hospital_capacity_recovery_report.pdf').read_bytes()).hexdigest(),'cli_version':'0.8.199','duration':T['duration'],'fps':30,'frames':T['frames'],'paid_media_api_calls':0,'video_authoring_hospital_calls':0,'experiment_attempts_in_source':sum(r['outward_attempts'] for r in C),'narration':'local Kokoro-82M af_heart, generation1.08; pitch-preserving atempo1.14','music_source':'https://www.scottbuckley.com.au/library/signal-to-noise/','music_license':'CC BY 4.0; attribution in CREDITS.md and final frame; include in publication description','metrics':D,'files':{}}
for f in sorted((P/'assets').rglob('*')):
    if f.is_file() and '/raw/' not in str(f):
        manifest['files'][str(f.relative_to(P))]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size}
(P/'production_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'duration':T['duration'],'frames':T['frames'],'scenes':len(T['scenes']),'source_sha256':D['source_sha256']}))
