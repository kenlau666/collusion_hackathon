"""Fail-closed, research-only wrapper around Terrarium's native chat client.

Importing this module and using an injected mock never constructs an HTTP client,
loads dotenv, or reads a credential. A live constructor requires a separately
recorded human authorization; the existence of this code is not authorization.
TogetherClient retains ownership of message/tool formatting and tool parsing.
The local byte guard is not a token estimate. Reservations use published endpoint
limits; reported provider usage is checked separately after a response.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import threading
from typing import Any, Mapping, Protocol
import urllib.error
import urllib.request

import certifi

from llm_server.clients.together_client import TogetherClient

MODEL_ID = "deepseek/deepseek-v3.2"
CANONICAL_MODEL = "deepseek/deepseek-v3.2-20251201"
PROVIDER_SLUG = "deepinfra/fp4"
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_URL = BASE_URL + "/chat/completions"
CONTEXT_LIMIT = 163840
ENDPOINT_OUTPUT_LIMIT = 16384
REQUEST_OUTPUT_LIMIT = 1024
MAX_PAYLOAD_BYTES = 128 * 1024
INPUT_USD_PER_TOKEN = Decimal("0.00000026")
OUTPUT_USD_PER_TOKEN = Decimal("0.00000038")
NATIVE_REQUEST_UPPER_BOUND_USD = Decimal("0.04882432")
RESERVATION_USD = Decimal("0.049")
SUCCESSOR_RESERVATION_USD = Decimal("0.16")
SCOPE_LIMITS = {"controls": (30, Decimal("1.50")), "full": (534, Decimal("27"))}
METADATA = {
    "checked_date_hkt": "2026-10-24",
    "endpoints_url": BASE_URL + "/models/deepseek/deepseek-v3.2/endpoints",
    "models_url": BASE_URL + "/models",
    "routing_url": "https://openrouter.ai/docs/guides/routing/provider-selection",
    "usage_url": "https://openrouter.ai/docs/cookbook/administration/usage-accounting",
    "reasoning_url": "https://openrouter.ai/docs/guides/best-practices/reasoning-tokens",
    "endpoint_snapshot_sha256": "2d7914de64e93ef57ae7e2690de1408f64c4fad8c53d211d74701dfef911c0fd",
    "request_fee": "not explicitly published; request unit-price ceiling is zero",
}


class BudgetError(RuntimeError):
    """Sanitized terminal condition. Never include transport exception text."""


def _money(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise BudgetError("invalid monetary value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BudgetError("invalid monetary value") from None
    if not result.is_finite() or result < 0:
        raise BudgetError("invalid monetary value")
    return result


def _integer(value: Any, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _plan_hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _limits(scope: str, max_calls: Any, max_usd: Any) -> tuple[int, Decimal]:
    if scope not in SCOPE_LIMITS:
        raise BudgetError("unknown authorization scope")
    cap_calls, cap_usd = SCOPE_LIMITS[scope]
    calls = cap_calls if max_calls is None else max_calls
    dollars = cap_usd if max_usd is None else _money(max_usd)
    if not _integer(calls, 1) or calls > cap_calls or dollars <= 0 or dollars > cap_usd:
        raise BudgetError("scope budget exceeds fixed limits or is invalid")
    return calls, dollars


def _approved(authorization: Mapping[str, Any], expected_plan_sha256: str) -> dict[str, Any]:
    if not isinstance(authorization, Mapping) or authorization.get("approved") is not True:
        raise BudgetError("explicit human authorization required")
    if not _plan_hash(expected_plan_sha256) or authorization.get("plan_sha256") != expected_plan_sha256:
        raise BudgetError("authorization plan fingerprint mismatch")
    reference = authorization.get("approval_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise BudgetError("human authorization reference required")
    scope = authorization.get("scope")
    if "max_calls" not in authorization or "max_usd" not in authorization:
        raise BudgetError("explicit authorization limits required")
    calls, dollars = _limits(scope, authorization["max_calls"], authorization["max_usd"])
    return {"approved": True, "scope": scope, "max_calls": calls, "max_usd": str(dollars),
            "plan_sha256": expected_plan_sha256,
            "approval_reference_sha256": hashlib.sha256(reference.encode()).hexdigest()}


def _redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Remove known credentials and common bearer forms from saved JSON only."""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", value)
        return re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
    if isinstance(value, list):
        return [_redact(v, secrets) for v in value]
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if str(k).lower() in
                {"authorization", "api_key", "api-key", "x-api-key"} else _redact(v, secrets))
                for k, v in value.items()}
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetLedger:
    """A new directory and atomic JSON ledger; resumption is deliberately refused.

    Each reservation appends a record and is fsynced before transport invocation.
    The whole ledger is atomically replaced, so records and balances commit as a
    unit. Unknown charges retain their reservation. A crashed ledger cannot be
    reopened by this class. Independent ledgers do not coordinate shared keys.
    """
    def __init__(self, directory: str | Path, *, scope: str = "controls",
                 max_calls: int | None = None, max_usd: Any = None,
                 plan_sha256: str | None = None,
                 authorization: Mapping[str, Any] | None = None,
                 reservation_usd: Any = None):
        calls, dollars = _limits(scope, max_calls, max_usd)
        reservation = RESERVATION_USD if reservation_usd is None else _money(reservation_usd)
        if reservation not in {RESERVATION_USD, SUCCESSOR_RESERVATION_USD}:
            raise BudgetError("unsupported per-attempt reservation profile")
        authorization = dict(authorization or {})
        if (reservation != RESERVATION_USD or "reservation_usd" in authorization):
            if (authorization.get("approved") is not True or
                    _money(authorization.get("reservation_usd")) != reservation):
                raise BudgetError("explicit matching per-attempt reservation authorization required")
        if plan_sha256 is not None and not _plan_hash(plan_sha256):
            raise BudgetError("invalid plan fingerprint")
        self.directory = Path(directory)
        self.path = self.directory / "ledger.json"
        self._lock = threading.RLock()
        self.authorization = deepcopy(authorization)
        self._reservation_usd = reservation
        self.plan_sha256 = plan_sha256
        authorization_summary = (_approved(self.authorization, plan_sha256)
            if self.authorization.get("approved") is True else {"approved": False})
        self.scope, self.max_calls, self.max_usd = scope, calls, dollars
        try:
            self.directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise BudgetError("existing ledger or resume refused") from None
        self.state = {
            "schema_version": 1, "created_at_utc": _now(), "scope": scope,
            "max_calls": calls, "max_usd": str(dollars), "plan_sha256": plan_sha256,
            "authorization": authorization_summary,
            "reservation_usd": str(self.reservation_usd), "calls": 0,
            "spent_usd": "0", "held_usd": "0", "status": "ready",
            "halt_reason": None, "records": [], "metadata": deepcopy(METADATA),
        }
        self._persist()

    @property
    def reservation_usd(self) -> Decimal:
        """One fixed, authorization-bound amount shared by every attempt path."""
        return self._reservation_usd

    def _persist(self) -> None:
        temporary = self.directory / ".ledger.pending"
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(self.state, handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            descriptor = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except Exception:
            self.state["status"] = "halted"
            self.state["halt_reason"] = "ledger_persistence_failure"
            raise BudgetError("ledger persistence failed; execution stopped") from None

    def halt(self, reason: str) -> None:
        with self._lock:
            self.state["status"] = "halted"
            self.state["halt_reason"] = reason
            self._persist()

    def reserve(self, payload: dict[str, Any], payload_bytes: int) -> int:
        with self._lock:
            if self.state["status"] != "ready":
                raise BudgetError("ledger is not available for another request")
            if self.state["calls"] >= self.max_calls:
                self.halt("call_limit")
                raise BudgetError("call limit reached")
            guarded_spend = max(_money(self.state["spent_usd"]),
                                _money(self.state.get("reported_cost_sum_usd", "0")))
            if (guarded_spend + _money(self.state["held_usd"]) +
                    self.reservation_usd > self.max_usd):
                self.halt("dollar_limit")
                raise BudgetError("dollar limit reached before request")
            call_id = self.state["calls"] + 1
            record = {"call_id": call_id, "reserved_at_utc": _now(), "status": "reserved",
                      "reservation_usd": str(self.reservation_usd), "payload_bytes": payload_bytes,
                      "payload": deepcopy(payload), "response": None, "response_id": None,
                      "usage": None, "known_cost_usd": None}
            self.state["records"].append(record)
            self.state["calls"] = call_id
            self.state["held_usd"] = str(_money(self.state["held_usd"]) + self.reservation_usd)
            self.state["status"] = "in_flight"
            self._persist()
            return call_id

    def finish(self, call_id: int, *, status_code: Any = None, response: Any = None,
               cost: Decimal | None = None, failure: str | None = None) -> None:
        with self._lock:
            record = self.state["records"][-1]
            if record["call_id"] != call_id or record["status"] != "reserved":
                self.halt("ledger_state_mismatch")
                raise BudgetError("ledger state mismatch")
            record.update({"finished_at_utc": _now(), "http_status": status_code,
                           "response": deepcopy(response),
                           "response_id": response.get("id") if isinstance(response, dict) else None,
                           "usage": deepcopy(response.get("usage")) if isinstance(response, dict) else None,
                           "known_cost_usd": str(cost) if cost is not None else None})
            if cost is not None:
                self.state["spent_usd"] = str(_money(self.state["spent_usd"]) + cost)
            if failure:
                record.update({"status": "failed", "failure": failure})
                self.state.update({"status": "halted", "halt_reason": failure})
                # The reservation remains held even if a failed reply reports a cost.
            else:
                record["status"] = "settled"
                self.state["held_usd"] = str(_money(self.state["held_usd"]) - self.reservation_usd)
                self.state["status"] = "ready"
            self._persist()

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy({k: v for k, v in self.state.items() if k != "records"})


@dataclass(frozen=True)
class TransportReply:
    status_code: int
    body: Any


class OneShotTransport(Protocol):
    def post(self, payload: dict[str, Any], *, timeout: float) -> TransportReply: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _verified_https_handler():
    """Use the installed CA bundle without weakening hostname/certificate checks."""
    context = ssl.create_default_context(cafile=certifi.where())
    return urllib.request.HTTPSHandler(context=context)


class LiveOpenRouterTransport:
    """Only live constructor. Never invoked by the offline validator.

    The caller must supply the actual human-approval record and bundle hash.
    This is an authorization check, not a source of permission. Credentials are
    held only in memory; no environment variables or files are read here.
    """
    is_real = True

    def __init__(self, *, authorization: Mapping[str, Any], api_key: str,
                 expected_plan_sha256: str):
        self.authorization_summary = _approved(authorization, expected_plan_sha256)
        if (not isinstance(api_key, str) or not api_key.strip() or
                any(c in api_key for c in "\r\n")):
            raise BudgetError("a valid in-memory API credential is required")
        self._api_key = api_key
        # Constructing HTTP machinery occurs only after approval validation.
        self._opener = urllib.request.build_opener(_NoRedirect(), _verified_https_handler())

    def sanitize_for_log(self, value: Any) -> Any:
        return _redact(value, (self._api_key,))

    def post(self, payload: dict[str, Any], *, timeout: float) -> TransportReply:
        if not CHAT_URL.startswith("https://openrouter.ai/"):
            raise BudgetError("unexpected inference destination")
        request = urllib.request.Request(CHAT_URL,
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"})
        try:
            response = self._opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            status = response.code
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            body = raw.decode("utf-8", errors="replace")
        return TransportReply(status_code=status, body=body)


class _NativeResponse:
    """Only the native formatter's successful requests.Response surface."""
    ok = True
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, body: dict[str, Any]):
        self.body = body

    def json(self) -> dict[str, Any]:
        return self.body


class _ReservedSession:
    def __init__(self, owner: "BudgetedChatClient"):
        self.owner = owner

    def post(self, url: str, *, headers: dict[str, str], data: str, timeout: float) -> _NativeResponse:
        owner, ledger = self.owner, self.owner.ledger
        if url != CHAT_URL or headers:
            ledger.halt("unexpected_native_transport_fields")
            raise BudgetError("unexpected native transport fields")
        try:
            payload = json.loads(data)
            payload.update({"model": MODEL_ID, "stream": False, "max_tokens": REQUEST_OUTPUT_LIMIT,
                            "temperature": 0, "seed": owner._request_seed,
                            "reasoning": {"enabled": False},
                            "provider": {"only": [PROVIDER_SLUG], "order": [PROVIDER_SLUG],
                                "allow_fallbacks": False, "require_parameters": True,
                                "max_price": {"prompt": 0.26, "completion": 0.38, "request": 0}}})
            serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except Exception:
            ledger.halt("invalid_payload")
            raise BudgetError("invalid request payload") from None
        if len(serialized) > MAX_PAYLOAD_BYTES:
            ledger.halt("payload_byte_limit")
            raise BudgetError("payload exceeds local byte limit")
        sanitize = getattr(owner.transport, "sanitize_for_log", _redact)
        call_id = ledger.reserve(sanitize(payload), len(serialized))
        try:
            reply = owner.transport.post(deepcopy(payload), timeout=timeout)
        except Exception:
            ledger.finish(call_id, failure="transport_failure")
            raise BudgetError("transport failure; reservation retained") from None
        try:
            status, body = reply.status_code, reply.body
            saved_body = sanitize(body)
            # Reject non-JSON-compatible fake/provider data without exposing repr.
            json.dumps(saved_body, allow_nan=False)
        except Exception:
            ledger.finish(call_id, failure="invalid_transport_reply")
            raise BudgetError("invalid transport reply; reservation retained") from None
        failure, cost = _validate_reply(status, body, reservation_usd=ledger.reservation_usd)
        ledger.finish(call_id, status_code=status, response=saved_body, cost=cost, failure=failure)
        if failure:
            raise BudgetError("provider response rejected; reservation retained")
        # Downstream native context/logging receives the same credential-safe
        # response that was persisted, including in an unexpected provider echo.
        return _NativeResponse(saved_body)


def _validate_reply(status: Any, body: Any, *, reservation_usd: Decimal = RESERVATION_USD) -> tuple[str | None, Decimal | None]:
    if not _integer(status, 100) or not 200 <= status < 300:
        return "http_failure", None
    if not isinstance(body, dict):
        return "malformed_response", None
    usage = body.get("usage")
    if not isinstance(usage, dict) or "cost" not in usage:
        return "missing_cost", None
    try:
        cost = _money(usage["cost"])
    except BudgetError:
        return "invalid_cost", None
    if cost > reservation_usd:
        return "overreservation_cost", cost
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if not _integer(prompt) or prompt > CONTEXT_LIMIT:
        return "reported_input_token_limit", cost
    if not _integer(completion) or completion > REQUEST_OUTPUT_LIMIT:
        return "reported_output_token_limit", cost
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict) and details.get("reasoning_tokens", 0) != 0:
        return "unexpected_reasoning_tokens", cost
    if body.get("model") not in {MODEL_ID, CANONICAL_MODEL}:
        return "returned_model_mismatch", cost
    choices = body.get("choices")
    if (not isinstance(body.get("id"), str) or not body["id"] or not isinstance(choices, list)
            or not choices or not isinstance(choices[0], dict)
            or not isinstance(choices[0].get("message"), dict)):
        return "malformed_response", cost
    return None, cost


class BudgetedChatClient(TogetherClient):
    """Native formatter/parser plus one reserved, fixed-route outward attempt."""
    def __init__(self, *, ledger: BudgetLedger, transport: OneShotTransport,
                 seed: int = 0, request_timeout: int = 60):
        if not _integer(seed) or not _integer(request_timeout, 1):
            raise BudgetError("invalid seed or timeout")
        if getattr(transport, "is_real", False):
            approved = _approved(ledger.authorization, ledger.plan_sha256)
            if approved != transport.authorization_summary or ledger.scope != approved["scope"]:
                raise BudgetError("live authorization does not match ledger")
            if (ledger.max_calls > approved["max_calls"] or
                    ledger.max_usd > _money(approved["max_usd"])):
                raise BudgetError("ledger exceeds live authorization")
        # Deliberately omit TogetherClient.__init__: no dotenv/key/session lookup.
        self.ledger, self.transport, self.seed = ledger, transport, seed
        self.base_url, self.request_timeout = BASE_URL, request_timeout
        self._request_seed = seed
        self._generation_lock = threading.Lock()
        self.session = _ReservedSession(self)

    @staticmethod
    def _get_retry_config() -> tuple[int, float, float]:
        return 0, 0.0, 0.0

    def _build_headers(self) -> dict[str, str]:
        # A separately authorized live transport owns credentials/headers.
        return {}

    def generate_response(self, input: list[dict[str, Any]], params: dict[str, Any]):
        if not self._generation_lock.acquire(blocking=False):
            raise BudgetError("concurrent client calls are refused")
        try:
            if not isinstance(params, dict) or params.get("model") != MODEL_ID:
                self.ledger.halt("model_mismatch")
                raise BudgetError("requested model does not match fixed model")
            for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
                if key in params and (not _integer(params[key], 1) or params[key] > REQUEST_OUTPUT_LIMIT):
                    self.ledger.halt("requested_output_limit")
                    raise BudgetError("requested output exceeds fixed limit or is invalid")
            seed = params.get("seed", self.seed)
            if not _integer(seed):
                self.ledger.halt("invalid_seed")
                raise BudgetError("invalid per-request seed")
            self._request_seed = seed
            return super().generate_response(input=input, params=params)
        finally:
            self._generation_lock.release()
