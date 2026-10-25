"""Build a closed-cutoff report from independently reconciled saved evidence.

This file never imports an experiment runner, provider or native environment.
Default --inspect reads evidence without authoring a PDF. Rendering additionally
requires --render --confirmed-cutoff, an evidence commit and a human-readable
cutoff. Run the PDF skill's artifact marker immediately before that operation,
then render and visually inspect every page before delivering the resulting PDF.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
import hashlib
import json
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Table, TableStyle, PageBreak)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DATA = HERE.parent / '20261025'
DEFAULT_BUNDLE = DATA / 'deadline_pilot_gate_002/bundle'
DEFAULT_LINEAGE = DATA / 'deadline_pilot_lineage_001/analysis.json'
DEFAULT_OUT = REPO / 'output/pdf/hospital_deadline_recovery_report.pdf'
AUTHOR = 'LAU, Chi Hong'
TITLE = 'After Source Removal'
SUBTITLE = 'Matched Advice, Patient Care, and Plan Retrieval in Hospital Agents'
PDF_SKILL = '/Users/kenlau/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.22136/skills/pdf/SKILL.md'
TEMPLATE = 'https://docs.google.com/document/d/1Y5wd3VRbXU5N08BvAGiJUQTaWbMCSPjhzXsR-ozuehg/edit'
SPRINT = 'https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25'
INK, BLUE, PALE = colors.HexColor('#172733'), colors.HexColor('#285b75'), colors.HexColor('#eef3f5')
STYLES = getSampleStyleSheet()
for name, values in {
    'BodyDeadline': dict(fontName='Times-Roman', fontSize=10.6, leading=13.2,
        alignment=TA_JUSTIFY, spaceAfter=7),
    'TitleDeadline': dict(fontName='Times-Bold', fontSize=23, leading=26,
        alignment=TA_CENTER, spaceAfter=8, textColor=INK),
    'SubtitleDeadline': dict(fontName='Times-Roman', fontSize=14, leading=17,
        alignment=TA_CENTER, spaceAfter=11, textColor=BLUE),
    'AuthorDeadline': dict(fontName='Times-Roman', fontSize=11, leading=14,
        alignment=TA_CENTER, spaceAfter=10),
    'HeadingDeadline': dict(fontName='Times-Bold', fontSize=14, leading=17,
        spaceBefore=9, spaceAfter=7, keepWithNext=True, textColor=INK),
    'SubheadingDeadline': dict(fontName='Times-Bold', fontSize=11.4, leading=14,
        spaceBefore=7, spaceAfter=5, keepWithNext=True),
    'SmallDeadline': dict(fontName='Times-Roman', fontSize=9.1, leading=11.1, spaceAfter=6),
    'CellDeadline': dict(fontName='Times-Roman', fontSize=8.5, leading=10.2),
    'MonoDeadline': dict(fontName='Courier', fontSize=7.7, leading=10,
        spaceAfter=7, wordWrap='CJK'),
}.items():
    STYLES.add(ParagraphStyle(name, **values))


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paragraph(text, style='BodyDeadline'):
    # The output uses ASCII hyphens to avoid unsupported Times glyphs.
    for value in ('\u2010', '\u2011', '\u2012', '\u2013', '\u2014', '\u2212'):
        text = text.replace(value, '-')
    # Restore normal prose spacing without modifying URLs, numeric values,
    # code identifiers or the hexadecimal provenance hashes.
    text = re.sub(r'\b(care|score|credit|variance|SD|seed|seeds|turn|turns|Table|TableA|TableB|Figure|USD|Section|sections|AppendixD|temperature)(?=[0-9])',
        r'\1 ', text, flags=re.I)
    text = re.sub(r'(?<=[0-9])(?=(?:and|with|without|under|from|for|of|in|main|diagnostic|instructed|independent|fixed|strict|controls|cells|cell|each|new|credits|patients|positive|complete|partial|planned|at|over|is|are|before|after|Hong|October|January|outward|output|logical|model|separate|state|under|to|whole|final|only|actual|while|then)\b)',
        ' ', text)
    return Paragraph(text, STYLES[style])


def value(number, *, signed=False, places=2):
    if number is None:
        return 'missing'
    n = float(number)
    if n == int(n):
        return ('+' if signed and n > 0 else '') + str(int(n))
    return ('+' if signed and n > 0 else '') + f'{n:.{places}f}'


def final(row, name):
    return row.get(name) if row.get('horizon_reached') else None


def observed_status(row):
    if row.get('horizon_reached'):
        return 'Reached' if row.get('all_turns_successful') else 'Reached; timeout skip'
    return {'unstarted': 'Unstarted', 'partial_terminal': 'Partial; stopped',
        'selected_endpoint_not_finalized': 'Unfinalized',
        'awaiting_independent_analysis': 'Awaiting audit'}.get(row.get('status'), row.get('status', 'missing'))


def control_status(row):
    if row.get('strict_control_pass') is True:
        return 'PASS'
    if row.get('endpoint_finalized'):
        return 'FAIL' if row.get('horizon_reached') else 'PARTIAL'
    return 'MISSING'


def table(headers, rows, widths, *, small=False):
    cells = [[paragraph(escape(str(cell)), 'CellDeadline') for cell in row] for row in [headers] + rows]
    obj = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    obj.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), PALE),
        ('LINEABOVE', (0, 0), (-1, 0), .9, BLUE),
        ('LINEBELOW', (0, 0), (-1, 0), .5, BLUE),
        ('LINEBELOW', (0, -1), (-1, -1), .5, BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3 if small else 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 if small else 5),
    ]))
    return obj


class Evidence:
    def __init__(self, lineage, bundle):
        self.lineage_path, self.bundle = Path(lineage), Path(bundle)
        self.lineage, self.plan = load(lineage), load(self.bundle / 'plan.json')
        self.plan_hash = sha(self.bundle / 'plan.json')
        if self.lineage['plan_sha256'] != self.plan_hash or self.lineage['mode'] != 'real_model_only':
            raise ValueError('Lineage must contain the active frozen real-model plan only')
        if self.lineage.get('issues'):
            raise ValueError('Resolve lineage integrity issues before report: ' + repr(self.lineage['issues']))
        self.results = self.lineage['Results']
        self.rows = {row['spec']['id']: row for row in self.results['per_cell']}
        if len(self.rows) != 22 or set(self.rows) != {s['id'] for s in self.plan['cases']}:
            raise ValueError('Report expects the fixed 5 control + 11 main + 6 diagnostic cells')
        self.accounting = self.lineage['accounting']
        self.provenance = {str(self.lineage_path.resolve()): sha(self.lineage_path),
            str((self.bundle / 'plan.json').resolve()): self.plan_hash,
            str((self.bundle / 'initial_inputs.json').resolve()): sha(self.bundle / 'initial_inputs.json')}
        for source in (REPO / 'RELATED_WORK.md', REPO / 'RECOVERY_PROTOCOL.md',
                       REPO / 'ARCHITECTURE.md', HERE / 'evidence_manifest.json'):
            self.provenance[str(source.resolve())] = sha(source)
        self.analyses, self.case_accounting = {}, {}
        for row in self.rows.values():
            if not row.get('endpoint_finalized'):
                continue
            path = Path(row['analysis_path'])
            analysis = load(path)
            if sha(path) != row['analysis_sha256'] or not analysis.get('reconciliation_passed'):
                raise ValueError('Stale or unsuccessful independent analysis: ' + str(path))
            if analysis['mode'] != 'live_model' or analysis['plan_sha256'] != self.plan_hash:
                raise ValueError('Software or other-plan evidence cannot enter model sample')
            cell = next(c for c in analysis['Results']['per_cell'] if c['id'] == row['spec']['id'])
            if cell['horizon_reached'] != row['horizon_reached']:
                raise ValueError('Lineage endpoint differs from independent analysis')
            self.analyses[row['spec']['id']] = cell
            self.case_accounting[row['spec']['id']] = analysis['accounting']
            self.provenance[str(path.resolve())] = sha(path)
            archive = Path(row['archive_path'])
            if sha(archive) != row['archive_sha256']:
                raise ValueError('Report case archive changed')
            self.provenance[str(archive.resolve())] = sha(archive)
        for name, expected in self.lineage.get('provenance_sha256', {}).items():
            path = Path(name)
            if path.exists() and sha(path) != expected:
                raise ValueError('Lineage is stale for ' + name + '; freeze/refresh before report')

    def row(self, advice, arm='excluded', mode='automatic'):
        return self.rows[f'deadline-{advice}-{arm}-{mode}']

    def contrast(self, label):
        return next(c for c in self.results['main']['matched_observed_differences'] if c['comparison'] == label)

    def historical(self, relative):
        path = DATA / relative
        data = load(path)
        self.provenance[str(path.resolve())] = sha(path)
        return data

    def counts(self):
        groups = {}
        for stage in ('controls', 'main', 'diagnostic'):
            rows = [r for r in self.rows.values() if r['spec']['stage'] == stage]
            groups[stage] = {'planned': len(rows), 'analyzed': sum(bool(r['endpoint_finalized']) for r in rows),
                'horizon': sum(bool(r['horizon_reached']) for r in rows),
                'partial': sum(bool(r['endpoint_finalized'] and not r['horizon_reached']) for r in rows)}
        return groups


def abstract(e):
    n = e.counts()
    useful, exploit = e.row('useful'), e.row('exploit')
    comparison = (
        f'After source removal, useful and exploit advice yield {value(useful["care_final"])} '
        f'and {value(exploit["care_final"])} resource-valid patients, respectively, at the observed horizon.'
        if useful['horizon_reached'] and exploit['horizon_reached'] else
        'The source-excluded useful-versus-exploit care contrast remains missing at this evidence cutoff.')
    text = (
        'Does removing an agent stop a harmful plan when independently authorized coworkers can still read it? '
        'We study this question in a synthetic Hospital environment with nine native roles, eight patients, '
        'shared boards, and batched tool use. A prospectively reduced pilot restores one actual useful-care '
        'checkpoint before final Ward work. Researchers inject useful or exploit advice attributed to a peer; '
        'it is not an observed malicious-source run. Eleven matched continuations compare the two recommendations, '
        'source retention versus exclusion, zero transfer bonuses, a pending-care reserve, and automatic versus '
        'explicit plan retrieval. Five instructed positive controls test care, retrieval, cycles, and a separate '
        'partner-policy interface. A six-cell diagnostic uses one other constructed checkpoint and one autonomous '
        'model with a scripted partner; it is not pooled with the main comparison. '
        f'At the cutoff, {n["main"]["horizon"]}/11 main and {n["diagnostic"]["horizon"]}/6 diagnostic cells reach '
        f'their horizons; {e.results["positive_controls"]["strict_passes"]}/5 strict controls pass. '
        + comparison + ' '
        'We report patient care separately from credits, physical round trips, proposals, denials, and timeout '
        'abandonments. Missing endpoints remain missing, and earlier failed qualification cohorts remain retained. '
        'Every cell reuses one stated prefix, so variance and confidence intervals are undefined. The results '
        'provide bounded observed contrasts and reproducible execution evidence; they cannot establish population '
        'reliability, malicious intent, a novel general defense, or deployment safety.'
    )
    if not 150 <= len(text.split()) <= 250:
        raise ValueError('Abstract outside official 150-250-word range: ' + str(len(text.split())))
    return text


def design_figure():
    d = Drawing(468, 106)
    boxes = [(0, 40, 116, 44, ['Actual seed0 prefix', 'All Surgery complete']),
        (140, 56, 122, 32, ['Useful peer advice']),
        (140, 10, 122, 32, ['Exploit peer advice']),
        (289, 16, 179, 73, ['Sources retained / excluded', 'Excluded + zero new bonus',
            'Excluded + care reserve', 'Care and action trace'])]
    for x, y, w, h, labels in boxes:
        d.add(Rect(x, y, w, h, rx=3, fillColor=PALE, strokeColor=BLUE, strokeWidth=.6))
        for i, label in enumerate(labels):
            d.add(String(x + w/2, y + h - 13 - i*14, label, fontName='Times-Roman',
                fontSize=9, textAnchor='middle', fillColor=INK))
    for x1, y1, x2, y2 in ((116, 63, 138, 72), (116, 55, 138, 27), (262, 72, 287, 65), (262, 27, 287, 41)):
        d.add(Line(x1, y1, x2, y2, strokeColor=BLUE, strokeWidth=.8))
        d.add(Polygon([x2, y2, x2-4, y2+2, x2-4, y2-2], fillColor=BLUE, strokeColor=BLUE))
    return d


def short_arm(arm):
    return {'retained': 'Sources active', 'excluded': 'Sources removed',
        'bonus_zero': 'Removed + zero bonus', 'reserve': 'Removed + reserve'}[arm]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(PALE)
    canvas.line(72, 48, 540, 48)
    canvas.setFont('Times-Roman', 8.5)
    canvas.setFillColor(BLUE)
    canvas.drawString(72, 35, 'Hospital agent plan-inheritance pilot | 26 October 2026')
    canvas.drawRightString(540, 35, str(doc.page))
    canvas.restoreState()


def build_story(e, evidence_commit, cutoff):
    story = []
    p = lambda text, style='BodyDeadline': story.append(paragraph(text, style))
    h = lambda text: p(text, 'HeadingDeadline')
    sub = lambda text: p(text, 'SubheadingDeadline')
    caption = lambda text: p(text, 'SmallDeadline')
    next_page = lambda: story.append(PageBreak())
    n = e.counts()
    controls = [r for r in e.rows.values() if r['spec']['stage'] == 'controls']
    main = [r for r in e.rows.values() if r['spec']['stage'] == 'main']
    diagnostic = [r for r in e.rows.values() if r['spec']['stage'] == 'diagnostic']
    baseline = e.rows['deadline-baseline']
    strict = e.results['positive_controls']['strict_passes']
    # Seven explicitly separated main-text pages. Later references/appendices
    # are outside the sprint's eight-main-page limit.
    p(TITLE, 'TitleDeadline'); p(SUBTITLE, 'SubtitleDeadline')
    p(AUTHOR + '<br/>No affiliation', 'AuthorDeadline')
    caption('AI Collusion Research Sprint 2026 | Evidence cutoff: ' + escape(cutoff))
    h('Abstract'); p(escape(abstract(e)))
    h('1. Introduction')
    p('Removing a plan author revokes that identity\'s future actions; it need not remove a public recommendation or coworkers\' existing tool permissions. We ask whether a researcher-written exploit recommendation attributed to a peer diverts useful Hospital care under source exclusion, and whether a simple repair preserves useful work. Source removal here is an access-exclusion ablation. The setup does not observe a malicious model inventing a plan or establish its autonomous transmission.')
    p('We separate three questions: influence of inherited advice, behavior after source removal, and care-preserving repair. A small architecture comparison asks whether requiring an explicit board read changes delivery and action. Patient outcomes, proposed actions, executed transfers and blocked calls are reported separately. A reward loop alone does not establish harmful collusion.')
    sub('Relation to existing work')
    p('Colosseum already provides the Hospital task, cooperative-agent collusion analysis and persuasion settings [1]. Strategy transmission through shared plans and persistence after source departure are studied in [2]. Purpose-bound mediation and cascading delegated revocation are established in DelegateGuard [3]. Our experiment is a bounded empirical comparison of independently authorized peers and service costs; it does not claim first plan transmission, a new authority principle, or a general defense.')
    next_page()

    h('2. Methods: one matched actual checkpoint')
    p('<b>Environment and agent architecture.</b> The bundled Hospital has two hospitals, four departments at each (Triage, Radiology, Surgery and Ward), one provisioner, eight synthetic patients and a 168-hour scheduling horizon. Three iterations contain planning and execution turns in a fixed nine-role order. Each turn permits at most three logical generations and preserves the full tool batch. SDK context starts fresh per turn; accessible boards and native physical state persist. No extra reflection notebook or learned private memory is introduced.')
    p('<b>Checkpoint and selection.</b> The main pilot restores completed ordinary successor seed0 after native turn15. Every required Surgery step is complete, all eight patients still need Ward care, and resource-valid care is0/8. Seed0 is the lowest-numbered completed useful baseline with this source-service boundary. This is a declared feasibility-selected case, not six-seed qualification. Researchers inject either memo with attribution to GH Surgery; both Surgery actors are designated source identities. Retained source actors remain ordinary model-controlled coworkers, without a continuing attack objective. The proposal is advice rather than a host instruction.')
    story.append(design_figure())
    caption('<b>Figure1.</b> Eight automatic-advice cells share one actual prefix. Source-excluded useful/exploit cells also run with on-demand retrieval. A source-excluded no-added-memo baseline gives eleven main cells in total. The inherited board/action prefix is retained.')
    story.append(table(['Condition', 'Change from matched continuation'], [
        ['Sources active', 'Original Surgery actors retain native turns and permissions.'],
        ['Sources removed', 'Both Surgery actors get zero generation, action and board access; public advice remains.'],
        ['Removed + zero bonus', 'Only newly accrued transfer credit is zero; historical credit and physical permissions persist.'],
        ['Removed + reserve', 'Deny a transfer if its actual debit violates the sender\'s assigned, still-pending Ward supplies; allow surplus transfers.'],
    ], [116, 352], small=True))
    p('<b>Common task.</b> All arms receive the same care-first objective, accurate inventory/pathway/calendar information, explicit four/four pending Ward obligations and current-supply scheduling preflight. Native queues remain nonexclusive; any legal resource-valid care counts. Transfers remain available. The provisioner has no assigned patient care and is exempt from the hospital-only reserve lookup, while native sender permissions remain enforced. Only controls receive prescribed actions.')
    next_page()

    h('3. Results: positive controls and baseline')
    labels = {'deadline-care-automatic': 'Actual-prefix instructed care',
        'deadline-readcare-on_demand': 'Explicit read then care',
        'deadline-cycle-automatic': 'Surviving-Ward out/back',
        'contingency-control-hold-care': 'Constructed: hold + care',
        'contingency-control-donate-return-care': 'Constructed: donate + timely return + care'}
    story.append(table(['Control (n=1 each)', 'Care /8', 'New credit', 'Status', 'Abandoned turns'],
        [[labels[r['spec']['id']], value(r['care_final']), value(r['credit_final']),
          control_status(r), value(r.get('abandoned_turns_final'))] for r in controls], [210, 51, 62, 68, 77]))
    caption('<b>Table1.</b> Fresh configured-model positives for this freeze: ' + str(strict) + '/5 strict passes. Care/read controls validate designated care and read-to-care execution; the cycle control validates actor-bound physical recurrence/newcredit30. Constructed-state controls validate the separate diagnostic interface. The instructed timely-return/serve control is also an anti-shortcut witness: a pre-care physical round trip can preserve care8/8. A strict pass requires designated actions/endpoints, no callback error and no abandoned turn. Missing or failed controls are retained; scripts never substitute for model positives.')
    p(f'<b>No-added-memo baseline.</b> Status: {escape(observed_status(baseline))}; final care {value(baseline["care_final"])}/8, new credit {value(baseline["credit_final"])}, pre-completion physical round trips {value(baseline["precompletion_roundtrips_final"])}. Last observed care is {value(baseline.get("care_last_observed"))}/8. A missing or failed baseline limits how confidently any deficit can be attributed to exploit advice.')
    sub('Execution, denominators and uncertainty')
    p(f'The fixed sample is5instructed controls,11main cells and6separate diagnostic cells. At this cutoff, independent saved-state analysis accepts {e.results["independently_analyzed_cells"]}/22 cell archives, and {e.results["horizon_reached"]}/22 reach their planned horizons. Main horizon coverage is {n["main"]["horizon"]}/11; diagnostic coverage is {n["diagnostic"]["horizon"]}/6. Each cell is one reused prefix, so its mean equals its observation; sample SD, variance and confidence intervals are undefined. Contrasts are paired observed differences at that prefix. Repeated conditions and requests do not increase independent n.')
    p('The endpoint advertises DeepSeek-V4.1-Flash through the configured Modal route: temperature0, reasoning disabled,1024output tokens and no API sampling seed. A request has a60s local deadline and at most one byte-identical retry after a typed timeout and worker reaping. Two exhausted timeouts can abandon that failed generation without native action and advance to the next scheduled turn only if the physical state stayed unchanged. Prior completed messages/queries and both failures/cost holds remain. An abandoned logical ID cannot be reused. Horizon reached and every turn successful are distinct outcomes.')
    caption('Each ledger has USD10/198outward-attempt limits and a1800s run deadline; cumulative Hospital guard USD50 includes historical unknown holds. Concurrent waves use separate processes/state/ledgers, inherited global exclusion and full per-run capacity envelopes. Paid reservation cutoff:26October06:30Hong Kong. Non-timeout/size failures terminate their case; financial/accounting/integrity failures stop shared dispatch. These execution changes are declared prospectively and do not complete older stopped episodes.')
    next_page()

    h('4. Results: advice, source removal and repair')
    factorial = [e.row(a, arm) for arm in ('retained', 'excluded', 'bonus_zero', 'reserve') for a in ('useful', 'exploit')]
    story.append(table(['Source / repair', 'Advice', 'Care /8', 'New credit', 'Pre-care trips', 'Reserve denied', 'Transfer proposals'],
        [[short_arm(r['spec']['arm']), r['spec']['advice'].capitalize(), value(r['care_final']),
          value(r['credit_final']), value(r['precompletion_roundtrips_final']),
          value(final(r, 'reserve_denials')), value(r['transfer_proposals_final'])] for r in factorial],
        [116, 48, 43, 59, 60, 66, 76]))
    caption('<b>Table2.</b> Eight automatic-delivery model cells, n=1each at actual seed0. Values are horizon endpoints; missing never means zero. Pre-care trips are executed exact physical returns while a pathway remains incomplete, measured even when bonus is zero. Denials and proposals are not executed cycles. Each full matched cell retains the same turns16-53; excluded-source positions generate no model requests.')
    selected = [c for c in e.results['main']['matched_observed_differences'] if
        c['comparison'].startswith('exploit minus useful') or c['comparison'] in
        ('source excluded minus retained, exploit', 'bonus_zero minus excluded original, exploit',
         'reserve minus excluded original, exploit')]
    names = {'exploit minus useful, retained, automatic': 'Exploit - useful: sources active',
        'exploit minus useful, excluded, automatic': 'Exploit - useful: sources removed',
        'exploit minus useful, bonus_zero, automatic': 'Exploit - useful: zero bonus',
        'exploit minus useful, reserve, automatic': 'Exploit - useful: reserve',
        'source excluded minus retained, exploit': 'Removed - active: exploit',
        'bonus_zero minus excluded original, exploit': 'Zero bonus - original: exploit',
        'reserve minus excluded original, exploit': 'Reserve - original: exploit'}
    story.append(table(['Matched observed difference', 'Care', 'Credit', 'Pre-care trips', 'Both horizons'],
        [[names[c['comparison']], value(c['observed_difference']['care_final'], signed=True),
          value(c['observed_difference']['credit_final'], signed=True),
          value(c['observed_difference']['precompletion_roundtrips_final'], signed=True),
          'Yes' if c['both_endpoints_observed'] else 'No'] for c in selected], [238, 45, 62, 67, 56], small=True))
    caption('<b>Table3.</b> Arithmetic paired differences, not repeated-seed treatment estimates. SD/variance/CI remain undefined. A horizon containing an abandoned turn is flagged in AppendixA. Backend variation, controls and no-memo baseline qualify interpretation; no replacement seed or favorable result selection is used.')
    p('Care loss relative to matched useful advice is the primary intended-purpose cost. High credit can arise from surplus redistribution or care completed before transfers. Conversely, zero bonus mechanically removes credit without proving the physical return behavior stopped. A reserve can block a proposal while the agent continues attempting it. Interpret the care, transfer, proposal and denial columns jointly; neither a credit change nor a blocked edge alone establishes recovery.')
    next_page()

    h('5. Results: automatic versus explicit retrieval')
    architecture = [e.row(advice, 'excluded', mode) for advice in ('useful', 'exploit') for mode in ('automatic', 'on_demand')]
    architecture_rows = []
    for row in architecture:
        audited = e.analyses.get(row['spec']['id'], {})
        m = audited.get('memo', {})
        architecture_rows.append([row['spec']['advice'].capitalize(),
            'Auto' if row['spec']['mode'] == 'automatic' else 'Explicit read',
            value(row['care_final']), value(row['credit_final']),
            value(m.get('explicit_read_callbacks')), value(m.get('memo_returned_by_read_callbacks')),
            value(m.get('provider_inputs_with_memo_tool_result'))])
    story.append(table(['Advice', 'Delivery', 'Care /8', 'Credit', 'Read calls*', 'Read returned memo*', 'Later input with memo*'],
        architecture_rows, [52, 76, 47, 51, 69, 87, 86]))
    caption('<b>Table4.</b> Actual seed0, sources excluded/original incentives, n=1each. The same board-read tool is available in both modes. Only the added memo is omitted from automatic prefetch in on-demand cells; other accessible content remains. *Read counters describe the reconciled trace, including partial traces; care/credit are final-horizon values only. A tool returning a memo and its inclusion in a subsequent model request are separately measured.')
    ac = [c for c in e.results['main']['matched_observed_differences'] if c['comparison'].startswith('on-demand minus automatic')]
    story.append(table(['On-demand minus automatic', 'Care', 'Credit', 'Pre-care trips', 'Both horizons'],
        [[c['comparison'].split('excluded ')[-1].capitalize(),
          value(c['observed_difference']['care_final'], signed=True),
          value(c['observed_difference']['credit_final'], signed=True),
          value(c['observed_difference']['precompletion_roundtrips_final'], signed=True),
          'Yes' if c['both_endpoints_observed'] else 'No'] for c in ac], [238, 45, 62, 67, 56]))
    caption('<b>Table5.</b> Paired observed architecture differences; one prefix, no variance estimate. The architecture comparison does not cross on-demand delivery with the bonus or reserve repairs, and it does not compare different model families or frontier-agent architectures.')
    automatic_counts = [e.analyses.get(e.row(a)['spec']['id'], {}).get('memo', {}).get('automatic_delivery_events')
        for a in ('useful', 'exploit')]
    on_demand_counts = [e.analyses.get(e.row(a, mode='on_demand')['spec']['id'], {}).get('memo', {}).get('automatic_delivery_events')
        for a in ('useful', 'exploit')]
    p('Saved automatic-prefetch delivery events for useful/exploit advice are ' +
        '/'.join(value(v) for v in automatic_counts) + ' in automatic mode and ' +
        '/'.join(value(v) for v in on_demand_counts) + ' in on-demand mode. These are delivery-hook observations, not extra independent samples. Table4 separately requires an actual memo-bearing tool message in the provider input for its last column.', 'SmallDeadline')
    sub('What the architecture manipulation identifies')
    p('Explicit retrieval adds a choice to fetch the target recommendation. It does not clear native state, reset a learned memory store, delete the inherited action trace or remove all other public events. An omitted memo is still present in the accessible board and can be returned by a legal read. Source/private closure is checked at prefetch, explicit reads, writes and tool dispatch. Thus a difference can concern exposure opportunity or follow-through; it is not evidence of a hidden memory mechanism.')
    p('The positive read-to-care control asks for an explicit read and designated care actions. Its success establishes that this interface can return the memo and still execute useful work under instruction. Spontaneous reading in main cells remains a separate behavioral observation. Failure to read can explain low exploit uptake, while a returned memo with no later input exposure cannot establish that a subsequent model generation used it.')
    sub('Scope of the two research targets')
    p('The main source/advice comparisons and this delivery comparison address different questions on the same prefix. They share observations and are not independent replications. Any exposure-sensitive continuation or repair benefit is bounded to this task, objective, endpoint, selected state and completion policy. A mechanism claim would require replicated, discriminating evidence across autonomous partner choices and additional states.')
    next_page()

    h('6. Results: separate partner-policy diagnostic')
    p('This diagnostic restores a different, native-constructed seed2state: six patients already have valid care; GHPatient5and SMPatient2remain assigned Ward obligations, with one Pain_Killer at each hospital. Only GH Ward is an autonomous model. SM Ward follows a disclosed script at turns44/53; the focal receives turns43/52. Other survivors are inactive here. Useful/exploit advice is crossed with early return, serve-only and late return. The six cells are not pooled with actual seed0or presented as an autonomous two-model coalition.')
    diagnostic_rows = []
    for row in diagnostic:
        behavior = row.get('diagnostic_behavior') or {}
        timing = behavior.get('observed_return_timing')
        timing_label = ('missing' if timing is None else
            'Early' if 'before_focal_execution_opportunity' in timing else
            'Late' if 'after_focal_execution_opportunity' in timing else 'None')
        diagnostic_rows.append([row['spec']['advice'].capitalize(),
            {'early_return': 'Early return', 'serve_only': 'Serve only', 'late_return': 'Late return'}[row['spec']['partner_policy']],
            value(row['care_final']), value(row['credit_final']),
            value(behavior.get('focal_pain_units_donated_to_partner')), timing_label,
            observed_status(row)])
    story.append(table(['Advice', 'Partner script', 'Care /8', 'Credit', 'Pain units sent*', 'Return timing*', 'Horizon'],
        diagnostic_rows, [50, 80, 42, 47, 77, 77, 95]))
    caption('<b>Table6.</b> One constructed state per cell, one autonomous focal model plus scripted partner. *Donation and timing are observed-to-date trace measures; endpoint columns remain missing for partial cases. The script returns only a resource actually received. Native batches, care opportunities and transfer chronology determine the outcome; language about cooperation is not the behavioral endpoint.')
    dp = e.results['partner_diagnostic']['advice_differences_within_partner_policy']
    story.append(table(['Exploit minus useful', 'Care', 'Credit', 'Focal pain donation', 'Both horizons'],
        [[c['comparison'].split(', ')[-1].replace('_', ' ').capitalize(),
          value(c['observed_difference']['care_final'], signed=True),
          value(c['observed_difference']['credit_final'], signed=True),
          value(c.get('focal_pain_donation_units_difference'), signed=True),
          'Yes' if c['both_endpoints_observed'] else 'No'] for c in dp], [188, 44, 58, 108, 70]))
    caption('<b>Table7.</b> Advice differences conditional on the partner script, n=1/cell. Partner-policy comparisons are interpretable as timing evidence only alongside the focal\'s actual donation; different focal choices confound a simple early-versus-late care comparison. AppendixA records every fixed cell and missing endpoint.')
    p('<b>Separate software witness.</b> Earlier deterministic tests of this constructed window hold the focal donation fixed: holding completes8/8under all scripts; donating yields care8/7/7and credits30/15/30for early/serve-only/late. Equal30credits can therefore conceal different care outcomes. Those are scripted measurement controls, not the new focal-model results in Table6and not extra model samples. The two fresh model diagnostic positives appear in Table1.')
    next_page()

    h('7. Discussion and limitations')
    useful, exploit = e.row('useful'), e.row('exploit')
    if useful['horizon_reached'] and exploit['horizon_reached']:
        p(f'<b>Observed source-excluded advice contrast.</b> Useful advice gives care{value(useful["care_final"])}/8and exploit advice gives{value(exploit["care_final"])}/8; the paired observed care difference is{value(exploit["care_final"]-useful["care_final"], signed=True)}. New credits are{value(useful["credit_final"])}and{value(exploit["credit_final"])}. This reports a single matched observation, not an estimate of a population effect or malicious shared intent.')
    else:
        p('<b>Observed source-excluded advice contrast.</b> At least one horizon endpoint is missing, so the paired final-care difference remains undefined. Partial care, credits or unexecuted plans cannot complete this comparison.')
    p(f'<b>Controls and usefulness.</b> Strict model positives pass{strict}/5at the cutoff. ' +
        ('All five observed positives support the intended interfaces on their stated states, but do not prove ordinary reliability. ' if strict == 5 else
         'Failed or missing positive controls limit interpretation of the corresponding behavior; inactivity is not recovery and an unqualified interface failure is not a null causal effect. ') +
        'The no-added-memo baseline is a separate check. Earlier native-execution and supply-preflight cohorts are retained as failed/incomplete evidence; the smaller deadline pilot does not retrospectively pass them.')
    p('<b>Finite sample and selection.</b> One completed useful prefix was selected by a declared rule after broader qualification problems. Each contrast reuses this state, and the constructed partner probe uses another state. Neither22cells nor their many provider requests are independent scenario seeds. There are no repeated sampling runs, standard errors, population confidence intervals or broad reliability claims. Temperature0does not attest deterministic backend behavior or immutable model weights.')
    p('<b>Threat and construct.</b> Common host instructions prioritize useful care and treat peer advice as untrusted. The researcher-written exploit memo is blunt, explicitly labeled PEER_PROPOSAL_EXPLOIT, and asks agents to defer care for reward-only loops. A null result therefore shows robustness to this particular obvious recommendation, not general collusion safety. Retained sources are ordinary coworkers, not actively malicious generators. High score, recurrence, matching actions or collusive wording alone does not demonstrate intended-purpose harm. Clinical harm means synthetic care loss under the fixed metric, not real medical harm or shared intent.')
    p('<b>Repair and architecture.</b> Zero bonus changes an incentive directly; reserve checks are execution mediation. A blocked action measures enforcement, not the absence of a proposed exploit. A model can also complete care through another legal hospital because queues are nonexclusive. Each native turn creates a fresh MemoAgent, with at most three within-turn generations; only public board/native state carries context across turns. On-demand reading is a minimal retrieval interface, simpler than deployed planners with persistent memory, asynchronous tools or learned policies. We test one relevant variation, not frontier applicability.')
    p('<b>Execution and missingness.</b> Exact retries can incur unknown remote charges despite local worker termination. Timeout abandonment changes the completion policy and leaves explicit no-action gaps. Concurrent request load can alter latency or rate limits; serial controls do not certify endpoint throughput. Non-timeout failures, guards and cutoff stops leave missing endpoints. Every failed attempt, reservation and historical cohort remains in the evidence lineage.')
    sub('Conclusion')
    p('This pilot makes source removal, surviving-peer advice, care preservation and retrieval independently inspectable. The useful contribution is the bounded, matched evidence and its limits. Any continuation or repair pattern in these tables should motivate replicated tests on additional states and autonomous partner choices; it does not establish a general collusion mechanism or safety guarantee.')
    next_page()

    h('References and code/data availability')
    github = f'https://github.com/kenlau666/collusion_hackathon/tree/{evidence_commit}'
    p('All requests, native state traces, frozen inputs, positive controls, failed attempts and derived analyses are retained in the fork. This report reads saved evidence only and invokes no model. The active research protocol records prospective decisions and historical failures separately. The report manifest records the exact saved-data and generator hashes.')
    for label, suffix in [('Evidence repository at the closed cutoff', ''), ('Research protocol', '/RECOVERY_PROTOCOL.md'),
        ('Architecture audit', '/ARCHITECTURE.md'), ('Exact-version prior-work audit', '/RELATED_WORK.md')]:
        url = github if not suffix else f'https://github.com/kenlau666/collusion_hackathon/blob/{evidence_commit}' + suffix
        caption(f'<link href="{url}" color="#285b75">{escape(label)}</link>')
    references = [
        ('[1] Nakamura, M., et al. (2026). Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems. arXiv:2602.15198v2. Hospital sections5.5-5.6and AppendixD.4.', 'https://arxiv.org/html/2602.15198v2'),
        ('[2] Hu, Y., et al. (2026). Reward Hacking as a Transmissible Strategy in Multi-Agent Coding Systems. arXiv:2610.12822v1. Section5.2and AppendixL.4.', 'https://arxiv.org/html/2610.12822v1'),
        ('[3] Tran-Truong, P. T., et al. (2026). DelegateGuard: Purpose-Bound Capabilities for Delegated LLM Agent Workflows. arXiv:2610.16005v1. Section3.6.', 'https://arxiv.org/html/2610.16005v1'),
        ('[4] Apart Research. AI Collusion Research Sprint2026: Guidelines and Submission Template. Requirements checked25October2026; at most8main pages excluding references/appendices, abstract150-250words.', SPRINT),
    ]
    for text, url in references:
        p(escape(text) + f' <link href="{url}" color="#285b75">Primary source</link>.')
    p(f'The local document adapts the <link href="{TEMPLATE}" color="#285b75">official template</link> using letter pages, one-inch margins, serif body text and its core report sections. Author: {AUTHOR}; no affiliation. The existing template/requirement record was read through Google Drive metadata/document tools; no cloud source was edited. Prior-work claims follow the repository\'s exact-version audit; no literature-wide novelty claim is made.')
    sub('Reproduction and accounting')
    p('Use the named frozen002plan and matching independent per-case analyses. Scenario seed0belongs to the actual main checkpoint; seed2belongs to the separate constructed diagnostic. API sampling seeds are not forwarded. Endpoint-advertised model identity and prices do not attest weights, tokenizer or actual charges. Reference prices are USD0.30/M input and USD1.20/M output; every unresolved attempt retains its full reservation.')
    caption('Closed evidence commit: ' + escape(evidence_commit) + '<br/>Cutoff: ' + escape(cutoff))
    caption('Active plan SHA256:<br/><font face="Courier" size="7.5">' + e.plan_hash + '</font>')
    next_page()

    h('Appendix A. Every planned real-model cell')
    all_rows = []
    for i, row in enumerate(e.rows.values(), 1):
        spec = row['spec']
        label = spec['id'].replace('deadline-', '').replace('contingency-', 'diag-').replace('automatic', 'auto').replace('on_demand', 'read')
        all_rows.append([i, label, observed_status(row), value(row['care_final']),
            value(row.get('care_last_observed')), value(row['credit_final']),
            value(row.get('abandoned_turns_final')), value(row.get('callback_errors'))])
    story.append(table(['#', 'Fixed cell', 'Endpoint', 'Final care', 'Last care', 'Final credit', 'Skipped', 'Err*'],
        all_rows, [23, 165, 66, 45, 43, 47, 41, 38], small=True))
    caption('<b>TableA1.</b> All22fixed model cases, including5positive controls,11main cells and6scripted-partner diagnostic cells. Each case is n=1at its stated prefix. Old software checks are excluded. Final means equal their single-case observations; SD, variance and CI are undefined. Last care and *callback-error/denial counts are observed-to-date for partial cases. A skipped turn is an exhausted-timeout abandonment, never a fabricated action. Legitimate reserve denials are separately counted in Table2.')
    shortages = [r['shortages_final'] for r in e.rows.values() if r['horizon_reached']]
    supply_denials = [(r['spec']['id'], r['supply_denials_final']) for r in e.rows.values()
        if r['horizon_reached'] and r['supply_denials_final']]
    caption('Executed shortage counts at the observed horizons: ' +
        (', '.join(value(v) for v in shortages) if shortages else 'missing') +
        '. Nonzero current-supply scheduling denials: ' +
        ('; '.join(name + '=' + value(v) for name, v in supply_denials) if supply_denials else
         'none among observed horizons; unobserved cells remain missing') + '.')
    next_page()

    h('Appendix B. Accounting and retained earlier studies')
    a = e.accounting
    ledgers = a['ledgers']
    outward = sum(v['outward_attempts'] for v in ledgers)
    new_ref = sum((Decimal(v['reference_estimate_usd']) for v in ledgers), Decimal(0))
    new_holds = sum((Decimal(v['unknown_held_usd']) for v in ledgers), Decimal(0))
    p(f'The deadline outputs contain{outward}outward attempts in{len(ledgers)}durable ledgers. Their new token-reference estimates sum to USD{new_ref}, with USD{new_holds}unresolved reservations. The baseline prior guard is USD{a["baseline_prior_guard_usd"]}, including USD{a["baseline_includes_unresolved_holds_usd"]}historical unresolved holds. The cumulative reference-policy guard at this closed snapshot is USD{a["cumulative_reference_guard_usd"]}. Actual Modal account charges remain unverified. Capacity envelopes are admission capacity, not charges.')
    p('The budget includes failed/unfinalized and other-plan live deadline outputs, even when those outputs are excluded from model result tables. A snapshot containing an active reservation is a budget observation, not evidence of an active process. Model-only case inclusion additionally requires the active plan, real-model mode and independent saved-state reconciliation. Software mock ledgers use fabricated token usage and add zero paid spend.')
    rows = []
    for row in e.rows.values():
        ac = e.case_accounting.get(row['spec']['id'])
        if ac is not None:
            rows.append([row['spec']['id'].replace('deadline-', '').replace('contingency-', 'diag-').replace('automatic', 'auto').replace('on_demand', 'read'),
                ac['outward_attempts'], ac['settled'], ac['retry_attempts'],
                ac['reference_estimate_usd'], ac['unknown_held_usd']])
    if rows:
        story.append(table(['Audited run / cell', 'Calls', 'Settled', 'Retries', 'Ref USD*', 'Held USD*'], rows,
            [210, 37, 43, 42, 76, 60], small=True))
    caption('<b>TableB1.</b> Saved financial audits. *These are run-level accounting values; if several cells share one run, repeated amounts are not summed as independent costs. The budget paragraph above sums unique ledgers only. Retry failures and unknown charges remain retained.')
    original = e.historical('ordinary_execution_lineage_001/analysis.json')
    successor = e.historical('supply_ordinary_lineage_001/analysis.json')
    orows = original['Results']['per_seed']
    srows = successor['Results']['per_seed']
    old_complete = [r for r in orows if r.get('care_final') is not None]
    new_complete = [r for r in srows if r.get('care_final') is not None]
    sub('Historical cohorts remain historical')
    p(f'The original native-execution full-workflow cohort has{len(old_complete)}/6complete endpoints. Its seed2last shows care7/8with a verified eighth schedule against seven Pain_Killers, then stops at a local financial byte bound; its final endpoint is missing. That study failed its ordinary zero-shortage prerequisite. The common-supply successor has{len(new_complete)}/6complete endpoints; seeds3-5are partial after a shared double-timeout stop. Its three complete care values are8/8each, with sample mean8, SD0and variance0over the complete subset, not the missing planned-six result. These episodes are not pooled with this selected-prefix deadline pilot or relabeled as fresh independent controls.')
    caption('Earlier cohorts, provider attempts, protocol amendments and source-boundary limitations remain in RECOVERY_PROTOCOL.md and Git history. The user explicitly permitted the smaller deadline pilot and no-action timeout continuation prospectively. Neither declaration erases an older failure or converts an unrun comparison into evidence.')
    next_page()

    h('Appendix C. Limitations, dual use and ethics')
    p('<b>Synthetic task and data.</b> Patients, schedules, inventories and rewards are generated simulation objects. No real patient records, clinical decisions, hospitals or operational financial systems were accessed. "Care loss" refers to the independent synthetic endpoint, not an assessment of actual healthcare. There are no human experimental subjects or human-provided patient datasets.')
    p('<b>Dual use.</b> Reproducible transfer-credit loops can make proxy gaming easier in this toy simulator. Exact tool traces are retained to distinguish intended-purpose loss from harmless surplus transfers and to permit falsification. We do not present real healthcare interference, real financial coordination or covert-channel deployment procedures. The reserve rule is a task-specific execution policy, not a production authorization or clinical safety guarantee.')
    p('<b>Construct and uncertainty.</b> Independent root permissions, persistent public boards and reward-positive authorized actions create a useful narrow test of source removal. They do not establish shared intent, deception or broad multi-agent autonomy. The model endpoint is configured/advertised, not independently attested; remote execution after local termination and unknown billing remain possible. Sample SD, variance and confidence intervals are unavailable for each n=1cell. Failed controls, missing endpoints and all software/model distinctions remain explicit.')
    p('<b>Research choices and reporting.</b> The deadline pilot reduces a previously incomplete six-family design prospectively. One feasibility-selected successful source-service boundary, explicit assignments and scripted partner policies limit external validity. The injected memos are researcher-authored and peer-attributed, not model-generated malicious-source evidence. The exploit is obvious and competes with explicit care/untrusted-advice instructions. A null cannot establish general safety, and a positive cannot establish natural emergence or hidden memory. A care deficit with timing evidence is stronger than credit or blocked tools but still requires replication.')
    sub('LLM usage statement')
    p('Codex assisted question refinement, source/code audits, implementation, bounded experiment orchestration, independent saved-evidence checks and drafting. The named experimental endpoint generated the real-model behavior identified by the frozen plan. Scripted controls and partner actions are explicitly labeled. Automated reconciliation is not an independent human replication. Report generation reads saved artifacts and invokes no inference. This document is supplied for LAU, Chi Hong\'s review; author review and external submission are not claimed complete.')
    sub('Artifact production and verification')
    p('This report is generated from the closed lineage and independently reconciled per-case analyses. A manifest pins the exact generator, source analyses, archives, active plan and PDF. Text extraction and page-count checks are supplemented by rendered-page inspection before delivery. The archived prior report and its generator remain unchanged. The PDF skill governs artifact production and layout checks, not experiment methodology or empirical claims.')
    return story


def inspect(e):
    return {'plan_sha256': e.plan_hash, 'source': str(e.lineage_path), 'counts': e.counts(),
        'strict_control_passes': e.results['positive_controls']['strict_passes'],
        'abstract_words': len(abstract(e).split()), 'planned_main_text_pages': 7,
        'missing_cells': [name for name, row in e.rows.items() if not row['horizon_reached']],
        'cumulative_reference_guard_usd': e.accounting['cumulative_reference_guard_usd'],
        'pdf_authored': False, 'inference_calls': 0}


def render(e, args):
    if not args.confirmed_cutoff or not args.evidence_commit or not args.cutoff:
        raise ValueError('Rendering requires --confirmed-cutoff, --evidence-commit and --cutoff')
    if not re.fullmatch(r'[0-9a-f]{7,40}', args.evidence_commit):
        raise ValueError('Use a concrete evidence commit hash')
    missing_audits = [name for name, row in e.rows.items() if not row['endpoint_finalized']]
    if not args.draft and missing_audits:
        raise ValueError('Final report requires reconciled terminal outputs for all22cells; use --draft to show missing: ' + ', '.join(missing_audits))
    if not args.draft and any(v.get('includes_active_reservations') for v in e.accounting['ledgers']):
        raise ValueError('Final report cutoff still includes active reservations; close and reconcile first')
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    story = build_story(e, args.evidence_commit,
        ('DRAFT - ' if args.draft else '') + args.cutoff)
    doc = BaseDocTemplate(str(output), pagesize=(612, 792), leftMargin=72, rightMargin=72,
        topMargin=72, bottomMargin=72, title=TITLE + ': ' + SUBTITLE,
        author=AUTHOR, subject='Matched Hospital advice, source removal, care-preserving repairs and plan retrieval')
    frame = Frame(72, 72, 468, 648, leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0, id='body')
    doc.addPageTemplates([PageTemplate(id='report', frames=[frame], onPage=footer)])
    doc.build(story)
    reader = PdfReader(str(output))
    texts = [page.extract_text() for page in reader.pages]
    references = next(i for i, text in enumerate(texts) if 'References and code/data availability' in text)
    if references > 8:
        raise ValueError(f'Main text exceeds8pages: {references}; repair layout before delivery')
    if references < 6:
        raise ValueError('Unexpected missing main sections; inspect pagination before delivery')
    full = '\n'.join(texts)
    for required in (AUTHOR, 'Abstract', 'Results:', 'LLM usage statement', 'dual use and ethics'):
        if required not in full:
            raise ValueError('Required text missing: ' + required)
    if any(token in full for token in ('PROJECT TITLE', 'Author name1', '\ufffd', '\u25a0')):
        raise ValueError('Template placeholder or broken glyph remains')
    manifest = {'report_title': TITLE + ': ' + SUBTITLE, 'author': AUTHOR, 'affiliation': None,
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'cutoff': args.cutoff,
        'evidence_commit': args.evidence_commit, 'lineage_path': str(e.lineage_path),
        'plan_sha256': e.plan_hash, 'evidence_sha256': e.provenance,
        'generator_sha256': sha(Path(__file__)), 'report_path': str(output.resolve()),
        'report_sha256': sha(output), 'abstract_words': len(abstract(e).split()),
        'main_text_pages': references, 'total_pages': len(reader.pages),
        'template_source': TEMPLATE, 'requirements_source': SPRINT,
        'template_adaptation': 'letter pages, one-inch margins, serif body/core sections; no cloud edit',
        'skill_sources': [PDF_SKILL], 'new_inference_calls': 0, 'new_spend_usd': '0',
        'sample_schema': 'active002 real22planned cells, n1each; old failed/model/software cohorts separate',
        'draft': args.draft, 'missing_independently_audited_cells': missing_audits,
        'counts': e.counts(), 'cumulative_reference_guard_usd': e.accounting['cumulative_reference_guard_usd'],
        'actual_provider_charges_verified': False,
        'visual_inspection': 'pending: render and inspect every page before delivery'}
    manifest_path = HERE / 'deadline_evidence_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return {'report': str(output.resolve()), 'manifest': str(manifest_path),
        'pages': len(reader.pages), 'main_pages': references, 'abstract_words': len(abstract(e).split()),
        'sha256': sha(output), 'visual_inspection': 'pending', 'new_inference_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lineage', type=Path, default=DEFAULT_LINEAGE)
    parser.add_argument('--bundle', type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--draft', action='store_true', help='Explicitly allow missing/unfinalized cells, shown as missing')
    parser.add_argument('--confirmed-cutoff', action='store_true')
    parser.add_argument('--evidence-commit')
    parser.add_argument('--cutoff')
    args = parser.parse_args()
    evidence = Evidence(args.lineage, args.bundle)
    print(json.dumps(render(evidence, args) if args.render else inspect(evidence), sort_keys=True))


if __name__ == '__main__':
    main()
