"""Read-only discovery of the user's existing Modal endpoint; no generation/deployment."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
import httpx2 as httpx


@dataclass
class EndpointConfig:
    base_url: str
    model: str
    auth_mode: str
    headers: dict = field(repr=False)

    @classmethod
    def from_values(cls, values):
        url=values.get("MODAL_ENDPOINT_BASE_URL","").strip().rstrip("/")
        parsed=urlsplit(url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an HTTPS endpoint URL without embedded credentials, query, or fragment")
        if not parsed.path:
            url+="/v1"
        bearer=values.get("MODAL_ENDPOINT_API_KEY") or values.get("MODAL_PROXY_TOKEN")
        token_id=values.get("MODAL_PROXY_TOKEN_ID")
        token_secret=values.get("MODAL_PROXY_TOKEN_SECRET")
        if bool(token_id)!=bool(token_secret):
            raise ValueError("Both Modal proxy token fields are required when using separate headers")
        headers={}
        if bearer:
            headers["Authorization"]="Bearer "+bearer
        if token_id:
            headers.update({"Modal-Key":token_id,"Modal-Secret":token_secret})
        if not headers:
            raise ValueError("Configure endpoint bearer credentials or a Modal proxy token pair locally")
        mode="bearer_and_proxy" if bearer and token_id else "bearer" if bearer else "proxy_headers"
        return cls(url,values.get("MODAL_ENDPOINT_MODEL") or "",mode,headers)


def probe(config, transport):
    response=transport.get(config.base_url+"/models",headers=config.headers)
    report={"checked_at":datetime.now(timezone.utc).isoformat(),"endpoint_base_url":config.base_url,
            "method":"GET","path":"/models","authentication_used":True,
            "auth_mode":config.auth_mode,"generation_requests":0,"http_status":response.status_code}
    if response.status_code==200:
        data=response.json()
        report["model_ids"]=[m["id"] for m in data.get("data",[]) if isinstance(m,dict) and isinstance(m.get("id"),str)]
        report["configured_model_listed"]=(config.model in report["model_ids"]) if config.model else None
    elif response.status_code in (401,403):
        report["finding"]="Authentication rejected; check endpoint credentials and token scope locally"
    else:
        report["finding"]="Model listing unavailable; endpoint API details need inspection"
    return report


if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    values=dict(dotenv_values(root/"compute.env"))
    values.update(os.environ)
    try:
        config=EndpointConfig.from_values(values)
    except ValueError as exc:
        raise SystemExit(str(exc))
    with httpx.Client(timeout=30,follow_redirects=False) as transport:
        report=probe(config,transport)
    output=Path(__file__).parent/"modal_endpoint_preflight.json"
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["http_status"]==200 else 1)
