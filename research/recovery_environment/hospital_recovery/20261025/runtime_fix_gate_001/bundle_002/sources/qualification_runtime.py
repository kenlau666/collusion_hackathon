"""Implementation-only qualification repetition under standing human approval.

The unchanged engagement runner owns native inputs, cases and pass criteria.
This module changes transport supervision and diagnostic retention only.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import fcntl
import tempfile

from budget_client import BudgetError, BudgetLedger, BudgetedChatClient, _approved
from deadline_transport import DeadlineTransport
import engagement_pilot as engagement

HERE = Path(__file__).resolve().parent
BASE = HERE/'20261025'
ORIGINAL = BASE/'engagement_gate_001/bundle'
STANDING = BASE/'standing_qualification_authorization.json'
SOURCES = ('request_worker.py', 'deadline_transport.py', 'qualification_runtime.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history():
    paths = [BASE/'controls_live_001/accounting/ledger.json',
             BASE/'main_live_001/accounting/ledger.redacted.json']
    paths += sorted(BASE.glob('engagement_live_*/accounting/ledger.json'))
    rows = []
    for path in paths:
        data = json.loads(path.read_text())
        rows.append({'path': str(path), 'sha256': sha(path), 'calls': data['calls'],
                     'known_usd': data['spent_usd'], 'held_usd': data['held_usd']})
    return {'ledgers': rows,
            'conservative_usd': str(sum((Decimal(r['known_usd'])+Decimal(r['held_usd']) for r in rows), Decimal(0)))}


def prepare(output):
    engagement.verify_bundle(ORIGINAL)
    standing = json.loads(STANDING.read_text())
    if standing.get('approved') is not True or standing.get('main_study_authorized') is not False:
        raise BudgetError('standing qualification approval required')
    prior = history()
    if Decimal(prior['conservative_usd'])+Decimal(10) > Decimal(standing['total_hospital_ceiling_usd']):
        raise BudgetError('insufficient remaining conservative budget')
    output.mkdir(parents=True, exist_ok=False)
    (output/'sources').mkdir()
    for name in SOURCES:
        shutil.copyfile(HERE/name, output/'sources'/name)
    plan = {'stage': 'same_cap3_qualification_transport_fix', 'approved': False,
            'original_bundle': str(ORIGINAL), 'original_plan_sha256': sha(ORIGINAL/'plan.json'),
            'standing_approval_sha256': sha(STANDING), 'max_calls':198, 'max_usd':'10',
            'scope':'full', 'total_ceiling_usd':'50', 'request_deadline_seconds':60,
            'retry_count':0, 'fallbacks':False, 'main_study_started':False,
            'changes':['Typed sanitized transport diagnostics','Killable whole-request deadline'],
            'scientific_contract':'Exact original engagement.run_case/execute, inputs, matrix and criteria',
            'prior_accounting':prior, 'sources':{name:sha(HERE/name) for name in SOURCES}}
    engagement.save(output/'plan.json', plan)
    return plan


def validate_output(output):
    resolved=output.resolve()
    if (resolved.parent!=BASE.resolve() or not re.fullmatch(r'engagement_live_[0-9]{3}',resolved.name)
        or output.exists()):
        raise BudgetError('fresh direct engagement_live_NNN output required for cumulative accounting')
    return resolved


async def preflight(bundle, authorization_path, output):
    validate_output(output)
    plan = json.loads((bundle/'plan.json').read_text())
    for name in SOURCES:
        if sha(HERE/name)!=plan['sources'][name] or sha(bundle/'sources'/name)!=plan['sources'][name]:
            raise BudgetError('runtime source differs from freeze')
    if (plan['original_bundle']!=str(ORIGINAL) or plan['original_plan_sha256']!=engagement.verify_bundle(ORIGINAL)
        or plan['standing_approval_sha256']!=sha(STANDING) or plan['prior_accounting']!=history()
        or plan['max_calls']!=198 or plan['max_usd']!='10' or plan['scope']!='full'
        or plan['total_ceiling_usd']!='50' or plan['request_deadline_seconds']!=60
        or plan['retry_count']!=0 or plan['fallbacks'] is not False or plan['main_study_started'] is not False):
        raise BudgetError('runtime plan/accounting mismatch')
    authorization = json.loads(authorization_path.read_text())
    approved = _approved(authorization, sha(bundle/'plan.json'))
    if approved['max_calls']!=198 or Decimal(approved['max_usd'])!=Decimal(10) or approved['scope']!='full':
        raise BudgetError('qualification bounds mismatch')
    if authorization.get('standing_approval_sha256')!=sha(STANDING):
        raise BudgetError('standing approval binding mismatch')
    if Decimal(plan['prior_accounting']['conservative_usd'])+10>50:
        raise BudgetError('total ceiling insufficient')
    roots = await engagement.verify_initial_inputs(ORIGINAL)
    raw, current = engagement.fetch_endpoint()
    if current!=json.loads((ORIGINAL/'pricing_snapshot.json').read_text())['critical_endpoint']:
        raise BudgetError('critical public metadata changed')
    return plan, authorization, roots, raw, current


async def run(bundle, authorization_path, output):
    # A real advisory lock, released by the OS on exit, serializes new runs.
    lock_path = Path(tempfile.gettempdir())/('hospital-qualification-'+hashlib.sha256(str(HERE).encode()).hexdigest()[:16]+'.lock')
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BudgetError('another qualification runtime owns the lock') from None
        return await run_locked(bundle, authorization_path, output)


async def run_locked(bundle, authorization_path, output):
    plan, authorization, roots, raw, critical = await preflight(bundle, authorization_path, output)
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise BudgetError('explicit OpenRouter key required')
    output.mkdir(parents=True, exist_ok=False)
    engagement.save(output/'preflight.json',{'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'plan_sha256':sha(bundle/'plan.json'),'original_plan_sha256':plan['original_plan_sha256'],
        'prior_accounting':plan['prior_accounting'],'critical_endpoint':critical})
    ledger = BudgetLedger(output/'accounting', scope='full', max_calls=198, max_usd='10',
                          plan_sha256=sha(bundle/'plan.json'), authorization=authorization)
    transport = DeadlineTransport(authorization=authorization, api_key=key,
        expected_plan_sha256=sha(bundle/'plan.json'), worker_sha256=plan['sources']['request_worker.py'],
        ledger=ledger, diagnostics=output/'transport_diagnostics')
    client = BudgetedChatClient(ledger=ledger, transport=transport, request_timeout=60)
    return await engagement.execute(client, output, roots)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--authorization',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='prepare':
            prepare(args.out);return 0
        _,summary=asyncio.run(run(args.bundle,args.authorization,args.out))
        return 0 if summary['qualification_passed'] else 2
    except (BudgetError,OSError,ValueError):
        print(json.dumps({'status':'stopped','error_type':'runtime_or_transport_failure'}));return 1


if __name__=='__main__':
    raise SystemExit(main())
