"""Reconstruct a locally rejected request without network or inference."""
import asyncio
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import socket
import sys

NETWORK=[]
def deny(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        NETWORK.append(event);raise RuntimeError('network denied during rejected-payload audit')
sys.addaudithook(deny)
ipv6=socket.has_ipv6
try:
    socket.has_ipv6=False
    import full_workflow as f
    from memo_delivery import restore_prefix
    from branch_runtime import ScriptedChatClient,digest
    from llm_server.clients.together_client import _convert_tools
finally:
    socket.has_ipv6=ipv6

HERE=Path(__file__).resolve().parent
RUN=HERE/'20261025/full_workflow_live_ordinary_retry1_s1_001'


async def main():
    out=RUN/'payload_audit'
    out.mkdir(exist_ok=False)
    path=RUN/'full-ordinary-s1.json.gz';ledger_path=RUN/'accounting/ledger.json'
    case=json.loads(gzip.decompress(path.read_bytes()));ledger=json.loads(ledger_path.read_text())
    assert ledger['halt_reason']=='payload_or_prompt_bound' and case['turns'][-1]['generation_attempts']==0
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    plan={'case_sha256':sha(path),'ledger_sha256':sha(ledger_path),
        'source_sha256':sha(Path(__file__).resolve()),
        'positive':'previous completed turn first input reproduces actually transmitted wire bytes',
        'negative':'rejected turn first input exceeds the frozen old local guard',
        'inference_calls':0}
    (out/'plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n')
    previous_index=len(case['turns'])-2
    previous=restore_prefix(case['turns'][previous_index-1]['after'])
    client=ScriptedChatClient()
    await f.native_turn(previous,case['turns'][previous_index],client,model=ledger['metadata']['model'])
    offset=sum(t['generation_attempts'] for t in case['turns'][:previous_index])
    actual=ledger['records'][offset]
    request=client.requests[0]
    assert request['input']==actual['payload']['messages']
    assert _convert_tools(request['params']['tools'])==actual['payload']['tools']
    check=json.loads(actual['wire_payload_json'])
    check.update(messages=request['input'],tools=_convert_tools(request['params']['tools']))
    assert json.dumps(check,ensure_ascii=False,allow_nan=False)==actual['wire_payload_json']
    prefix=deepcopy(case['turns'][-2]['after']);original=digest(prefix)
    branch=restore_prefix(prefix);client=ScriptedChatClient()
    await f.native_turn(branch,case['turns'][-1],client,model=ledger['metadata']['model'])
    request=client.requests[0]
    payload=json.loads(actual['wire_payload_json'])
    payload.update(messages=request['input'],tools=_convert_tools(request['params']['tools']))
    wire=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
    padding=512*(len(payload['messages'])+len(payload['tools'])+1)
    content_bytes=sum(len((m.get('content') or '').encode()) for m in payload['messages'])
    noncontent_bytes=sum(len(json.dumps({k:v for k,v in m.items() if k!='content'},ensure_ascii=False).encode()) for m in payload['messages'])
    tools_bytes=len(json.dumps(payload['tools'],ensure_ascii=False).encode())
    assert len(wire)>128*1024 or len(wire)+padding>131072
    assert digest(prefix)==original and not NETWORK
    (out/'rejected_wire.json').write_bytes(wire)
    result={'passed':True,'seed':1,'positive_matching_actual_call':actual['call_id'],
        'positive_wire_equal':True,'rejected_logical_request':106,'rejected_turn_index':case['turns'][-1]['turn_index'],
        'wire_bytes':len(wire),'old_padded_bound':len(wire)+padding,'old_input_bound_limit':131072,
        'decoded_content_utf8_bytes':content_bytes,'noncontent_message_json_bytes':noncontent_bytes,
        'tool_schema_json_bytes':tools_bytes,'padding_bytes':padding,
        'decoded_fields_plus_padding':content_bytes+noncontent_bytes+tools_bytes+padding,
        'wire_sha256':hashlib.sha256(wire).hexdigest(),'old_guard_rejects':True,
        'prefix_not_mutated':True,'network_attempts':NETWORK,'inference_calls':0,
        'n':1,'sample_sd':None,'sample_variance':None,
        'limit':'decoded byte counts are software measurements; not a verified server tokenizer count or a completed endpoint'}
    (out/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':asyncio.run(main())
