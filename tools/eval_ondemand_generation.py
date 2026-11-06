#!/usr/bin/env python3
"""Generate real-model outputs from the five-route memory evaluation artifacts.

Without configured credentials/model/base URL this writes a not_run report and
makes no network calls. Generation is not an automatic answer/persona grade:
blind-review fields remain pending_review until a reviewer supplies judgments.
"""
from __future__ import annotations

import argparse
from dataclasses import fields, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from guanghe_companion.expression_clients import (
    OpenAIResponsesClient, OpenAICompatibleChatClient, _default_transport,
    MAX_OPENAI_PROMPT_LENGTH, MAX_OPENAI_RESPONSE_BYTES,
    client_config_from_settings,
)
from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style, provider_api_key_required
from guanghe_companion.expression_expressor import ShinsekaiAIExpressor
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.expression_parser import parse_shinsekai_object_stream, ExpressionPayloadError


KEY_ENV_NAMES = ("EMOTI_HOLDOUT_API_KEY", "EMOTI_LLM_API_KEY", "OPENAI_API_KEY")


def sha256(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, nargs="+", required=True, help="Per-method JSON files from eval_ondemand_memory")
    p.add_argument("--output", type=Path, default=ROOT / "artifacts/ondemand-memory/generation.json")
    p.add_argument("--model", help="Explicit model; alternatively EMOTI_LLM_MODEL")
    p.add_argument("--app-settings", type=Path, help="Existing expression_settings.json; preserves provider protocol and model")
    p.add_argument("--base-url", help="Explicit API endpoint/base; alternatively EMOTI_LLM_BASE_URL")
    p.add_argument("--api-style", choices=("responses", "chat"))
    p.add_argument("--api-key-env", help="Environment variable containing the key; never a literal CLI key")
    p.add_argument("--max-requests", type=int, default=20)
    p.add_argument("--max-output-tokens", type=int, default=512)
    p.add_argument("--timeout", type=float)
    p.add_argument("--production-expression", action="store_true",
                   help="Use the desktop expressor including its bounded review; retain every raw provider call")
    p.add_argument("--query-ids", nargs="+")
    p.add_argument("--splits", nargs="+", choices=("development", "validation", "holdout"))
    p.add_argument("--input-price-per-million", type=float)
    p.add_argument("--cached-input-price-per-million", type=float)
    p.add_argument("--output-price-per-million", type=float)
    args = p.parse_args(argv)
    if not 1 <= args.max_requests <= 10000:
        p.error("--max-requests must be between 1 and 10000")
    if not 1 <= args.max_output_tokens <= 4096:
        p.error("--max-output-tokens must be between 1 and 4096 (existing client contract)")
    if args.app_settings and any(value is not None for value in (args.model, args.base_url, args.api_style, args.api_key_env)):
        p.error("--app-settings cannot be combined with provider overrides")
    if args.timeout is not None and (not math.isfinite(args.timeout) or not 1 <= args.timeout <= 60):
        p.error("--timeout must be between 1 and 60 seconds")
    prices = (args.input_price_per_million, args.cached_input_price_per_million, args.output_price_per_million)
    if any(value is not None and (not math.isfinite(value) or value < 0) for value in prices):
        p.error("token prices must be finite and nonnegative")
    if (args.input_price_per_million is None) != (args.output_price_per_million is None):
        p.error("provide both input and output prices, or neither")
    if args.cached_input_price_per_million is not None and args.input_price_per_million is None:
        p.error("cached-input price requires input/output prices")
    return args


def load_cases(args):
    cases, sources, seen = [], [], set()
    for path in args.input:
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list) or not data.get("method"):
            raise ValueError("input must be a per-method retrieval artifact with method and rows")
        digest = sha256(raw)
        sources.append({"path": str(path.resolve()), "sha256": digest, "method": data["method"],
                        "size": data.get("size"), "source_commit": data.get("source_commit"),
                        "source_sha256": data.get("source_sha256"), "dataset_sha256": data.get("dataset_sha256"),
                        "presentation": data.get("presentation")})
        for row in data["rows"]:
            if args.query_ids and row.get("query_id") not in args.query_ids:
                continue
            if args.splits and row.get("split") not in args.splits:
                continue
            key = (data["method"], data.get("size"), row.get("split"), row.get("query_id"))
            if key in seen:
                raise ValueError("duplicate method/size/split/query_id; select one frozen retrieval run")
            seen.add(key)
            cases.append({**row, "method": data["method"], "size": data.get("size"), "retrieval_artifact_sha256": digest})
    # Spend on matched question blocks across methods, rather than exhausting
    # the request budget on whichever file happened to be listed first.
    cases.sort(key=lambda row: (row.get("split", ""), row.get("story_id", ""), row.get("query_id", ""),
                                row.get("size") or 0, row["method"]))
    return cases, sources


def final_evidence_ids(prompt):
    line = next((line for line in prompt.splitlines() if line.startswith("emotional_memory: ")), "")
    if not line:
        return []
    memory = json.loads(line.removeprefix("emotional_memory: "))
    result = [row["memory_id"] for row in memory.get("shared_memories", [])
              if isinstance(row, dict) and row.get("memory_id") and row.get("summary")]
    overview = memory.get("memory_overview", {})
    for claim in overview.get("claims", []) if isinstance(overview, dict) else []:
        if not isinstance(claim, dict) or not (claim.get("text") or claim.get("summary") or claim.get("claim")):
            continue
        ids = claim.get("source_memory_ids", claim.get("memory_ids", []))
        ids = [ids] if isinstance(ids, str) else ids
        result.extend(ids)
        result.extend(claim[key] for key in ("memory_id", "source_memory_id") if claim.get(key))
    return list(dict.fromkeys(result))


def render_prompt(payload):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("missing saved ExpressionRequest")
    allowed = {field.name for field in fields(ExpressionRequest)}
    if set(payload) - allowed:
        raise ValueError("saved ExpressionRequest has unknown fields")
    request = ExpressionRequest(**payload)
    with ShinsekaiAIExpressor(enabled=False) as expressor:
        return expressor.build_prompt(request)


def redact(value, secret):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED_API_KEY]")
    if isinstance(value, dict):
        return {redact(str(key), secret): redact(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    return value


def measured_cost(usage, args):
    if args.input_price_per_million is None or not isinstance(usage, dict):
        return None
    incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
    outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
    if type(incoming) is not int or type(outgoing) is not int or min(incoming, outgoing) < 0:
        return None
    details = usage.get("input_tokens_details", usage.get("prompt_tokens_details")) or {}
    cached = details.get("cached_tokens", 0)
    if type(cached) is not int or not 0 <= cached <= incoming:
        return None
    cached_price = args.cached_input_price_per_million
    if cached_price is None:
        cached_price = args.input_price_per_million
    return ((incoming - cached) * args.input_price_per_million + cached * cached_price
            + outgoing * args.output_price_per_million) / 1_000_000


class RecordingTransport:
    def __init__(self, *, delegate, api_style, max_output_tokens, max_requests=None):
        self.delegate, self.api_style, self.max_output_tokens = delegate, api_style, max_output_tokens
        self.calls = 0
        self.last = {}
        self.records = []
        self.max_requests = max_requests

    def __call__(self, request, timeout):
        if self.max_requests is not None and self.calls >= self.max_requests:
            raise RuntimeError("provider request budget exhausted")
        body = json.loads(request.data)
        if self.api_style == "responses":
            body["max_output_tokens"] = self.max_output_tokens
        request.data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.calls += 1
        started = perf_counter()
        self.last = {"wire_payload": body, "timeout_seconds": timeout}
        try:
            raw = self.delegate(request, timeout)
            self.last["response_bytes"] = len(raw) if isinstance(raw, (bytes, bytearray)) else None
            if isinstance(raw, (bytes, bytearray)) and len(raw) <= MAX_OPENAI_RESPONSE_BYTES:
                self.last["response_sha256"] = sha256(bytes(raw))
                self.last["raw_response_text"] = raw.decode("utf-8", errors="replace")
                try:
                    self.last["provider_response"] = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
            return raw
        finally:
            self.last["transport_latency_ms"] = (perf_counter() - started) * 1000
            self.records.append(dict(self.last))


def recorded_app_client(path, *, max_requests=10000, max_output_tokens=4096):
    if not path.is_file():
        raise ValueError("app settings file is missing")
    settings = ExpressionSettingsStore(path).load()
    config = client_config_from_settings(settings)
    if config.client is None:
        raise ValueError("app settings must enable a configured expression provider")
    style = "responses" if provider_api_style(settings.provider) == "responses" else "chat"
    meter = RecordingTransport(delegate=_default_transport, api_style=style,
                               max_output_tokens=max_output_tokens, max_requests=max_requests)
    client = config.client
    client.transport = meter
    if isinstance(client, OpenAICompatibleChatClient):
        client.max_tokens = max_output_tokens
    metadata = {"api_style": style, "requested_model": settings.model, "base_url": settings.base_url,
                "credential_source": "app_settings", "transport": "real_http",
                "timeout_seconds": settings.timeout_seconds, "max_requests": max_requests,
                "max_output_tokens": max_output_tokens}
    return client, meter, metadata, settings.api_key


def run(args, *, environ=None, transport=None):
    environ = os.environ if environ is None else environ
    keys = (args.api_key_env,) if args.api_key_env else KEY_ENV_NAMES
    key_env = next((name for name in keys if environ.get(name, "").strip()), None)
    api_key = environ[key_env].strip() if key_env else ""
    model = (args.model if args.model is not None else environ.get("EMOTI_LLM_MODEL", "")).strip()
    base_url = (args.base_url if args.base_url is not None else environ.get("EMOTI_LLM_BASE_URL", "")).strip()
    missing = [name for name, value in (("api_key", api_key), ("model", model), ("base_url", base_url)) if not value]
    settings = None
    api_style = args.api_style or "responses"
    timeout = args.timeout if args.timeout is not None else 30
    if args.app_settings:
        settings = ExpressionSettingsStore(args.app_settings).load()
        if args.timeout is not None:
            settings = replace(settings, timeout_seconds=args.timeout)
        api_key, model, base_url = settings.api_key, settings.model, settings.base_url
        key_env = None
        timeout = settings.timeout_seconds
        api_style = "responses" if provider_api_style(settings.provider) == "responses" else "chat"
        missing = []
        if not args.app_settings.is_file():
            missing.append("app_settings")
        if not settings.enabled:
            missing.append("enabled")
        if provider_api_key_required(settings.provider) and not api_key:
            missing.append("api_key")
    invalid = []
    if model and (len(model) > 80 or any(ord(char) < 32 for char in model)):
        invalid.append("model")
    endpoint = urlsplit(base_url)
    if base_url and (len(base_url) > 240 or endpoint.scheme not in {"http", "https"} or not endpoint.hostname
                     or endpoint.username or endpoint.password or any(ord(char) < 32 for char in base_url)):
        invalid.append("base_url")
    if api_key and len(api_key) > 512:
        invalid.append("api_key")
    cases, sources = load_cases(args)
    report = {"schema_version": 1, "status": "not_run", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "production_expression" if args.production_expression else "raw_provider",
        "scope": "actual model generation from saved retrieval evidence; not desktop interaction",
        "sources": sources, "script_sha256": sha256(Path(__file__).read_bytes()),
        "fallback_prompt_builder_sha256": sha256((ROOT / "src/guanghe_companion/expression_expressor.py").read_bytes()),
        "provider": {"api_style": api_style, "requested_model": model, "base_url": base_url,
                     "credential_source": "app_settings" if settings else "environment",
                     "credential_env_name": key_env, "transport": "injected_test" if transport else "real_http"},
        "budget": {"max_requests": args.max_requests, "max_output_tokens": args.max_output_tokens,
                   "timeout_seconds": timeout, "max_prompt_chars": MAX_OPENAI_PROMPT_LENGTH},
        "pricing": {"source": "user_supplied" if args.input_price_per_million is not None else "not_configured",
                    "input_per_million": args.input_price_per_million,
                    "cached_input_per_million": args.cached_input_price_per_million,
                    "output_per_million": args.output_price_per_million},
        "missing_configuration": missing, "invalid_configuration": invalid,
        "actual_requests": 0, "rows": [], "evaluation": {}}
    meter = RecordingTransport(delegate=transport or _default_transport, api_style=api_style,
                               max_output_tokens=args.max_output_tokens, max_requests=args.max_requests)
    client = None
    if not missing and not invalid:
        if settings is not None:
            client = client_config_from_settings(settings).client
            client.transport = meter
            if isinstance(client, OpenAICompatibleChatClient):
                client.max_tokens = args.max_output_tokens
        elif api_style == "responses":
            client = OpenAIResponsesClient(api_key=api_key, model=model, base_url=base_url,
                                           timeout_seconds=timeout, transport=meter)
        else:
            client = OpenAICompatibleChatClient(api_key=api_key, model=model, base_url=base_url,
                timeout_seconds=timeout, max_tokens=args.max_output_tokens, transport=meter)
    expressor = ShinsekaiAIExpressor(llm_client=client, timeout_seconds=timeout) if client and args.production_expression else None
    def checkpoint():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".pending")
        temporary.write_text(json.dumps(redact(report, api_key), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.output)
    try:
        for case in cases:
            record = {key: case.get(key) for key in ("query_id", "story_id", "split", "family", "query", "method", "size",
                "expected_status", "expected_routes", "gold_ids", "forbidden_ids", "retrieval_artifact_sha256")}
            record.update(review_id=sha256(json.dumps(record, sort_keys=True, ensure_ascii=False))[:20],
                          status="not_run", answer=None, output_text=None,
                          review={"answer_correctness": "not_run", "persona_behavior": "not_run",
                                  "unsupported_claims": "not_run", "natural_unknown": "not_run"})
            report["rows"].append(record)
            try:
                if "actual_provider_prompt" in case:
                    prompt = case["actual_provider_prompt"]
                    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_OPENAI_PROMPT_LENGTH:
                        raise ValueError("saved provider prompt is empty or exceeds the existing client limit")
                    record["prompt_origin"] = "saved_provider_prompt"
                else:
                    prompt = render_prompt(case.get("actual_expression_request"))
                    record["prompt_origin"] = "rebuilt_with_current_production_builder"
                if args.production_expression:
                    if render_prompt(case.get("actual_expression_request")) != prompt:
                        raise ValueError("saved prompt differs from the current production request")
                record.update(final_prompt=prompt, final_prompt_sha256=sha256(prompt), final_prompt_chars=len(prompt),
                              final_prompt_evidence_ids=final_evidence_ids(prompt))
            except (ValueError, TypeError, KeyError) as exc:
                record.update(status="failed", reason="prompt_build_failed", error_type=type(exc).__name__)
                checkpoint()
                continue
            if client is None:
                record["reason"] = "missing_configuration" if missing else "invalid_configuration"
                continue
            if meter.calls >= args.max_requests:
                record["reason"] = "request_budget_exhausted"
                continue
            started = perf_counter()
            meter.last = {}
            call_start = len(meter.records)
            try:
                if expressor is not None:
                    events = expressor.express(ExpressionRequest(**case["actual_expression_request"]))
                    if expressor.last_fallback_reason:
                        record["fallback_reason"] = expressor.last_fallback_reason
                        raise ValueError("production expression did not deliver a validated model answer")
                    output = json.dumps(events, ensure_ascii=False)
                else:
                    output = client(prompt)
                response = meter.last.get("provider_response") or {}
                response = response if isinstance(response, dict) else {}
                usage = response.get("usage")
                record.update(status="completed", output_text=output, provider_model=response.get("model"),
                    provider_response_id=response.get("id"), usage=usage, cost_usd=measured_cost(usage, args),
                    review={name: "pending_review" for name in record["review"]})
                try:
                    events = parse_shinsekai_object_stream(output, None)
                    record["schema_status"] = "valid" if events else "invalid"
                    record["answer"] = "\n".join(event["speech"] for event in events) if events else output
                except ExpressionPayloadError as exc:
                    record["schema_status"] = exc.reason
                    record["answer"] = output
            except Exception as exc:
                # Error text can contain a credential or provider body. Keep
                # structured public reasons; never substitute an unknown answer.
                record.update(status="failed", reason=getattr(exc, "public_reason", "generation_error"),
                              error_type=type(exc).__name__)
            record.update(client_latency_ms=(perf_counter() - started) * 1000, **meter.last)
            if args.production_expression:
                calls = meter.records[call_start:]
                record["provider_calls"] = calls
                record["provider_call_count"] = len(calls)
                draft_response = calls[0].get("provider_response", {}) if calls else {}
                choices = draft_response.get("choices", []) if isinstance(draft_response, dict) else []
                draft = choices[0].get("message", {}).get("content") if choices else None
                record["draft_output_text"] = draft
                if isinstance(draft, str):
                    try:
                        record["draft_schema_status"] = "valid" if parse_shinsekai_object_stream(draft, None) else "invalid"
                    except ExpressionPayloadError as exc:
                        record["draft_schema_status"] = exc.reason
                usages = [call.get("provider_response", {}).get("usage") for call in calls]
                complete_usage = usages and all(isinstance(u, dict)
                    and type(u.get("prompt_tokens", u.get("input_tokens"))) is int
                    and type(u.get("completion_tokens", u.get("output_tokens"))) is int for u in usages)
                record["total_usage"] = ({"input_tokens": sum(u.get("prompt_tokens", u.get("input_tokens")) for u in usages),
                                          "output_tokens": sum(u.get("completion_tokens", u.get("output_tokens")) for u in usages)}
                                         if complete_usage else None)
            response = meter.last.get("provider_response")
            if isinstance(response, dict):
                record.update(provider_model=response.get("model"), usage=response.get("usage"),
                              provider_response_id=response.get("id"), cost_usd=measured_cost(response.get("usage"), args))
            report["actual_requests"] = meter.calls
            checkpoint()
    finally:
        if expressor is not None:
            expressor.close()
        elif client is not None:
            client.close()
    completed = sum(row["status"] == "completed" for row in report["rows"])
    failed = sum(row["status"] == "failed" for row in report["rows"])
    pending = sum(row["status"] == "not_run" for row in report["rows"])
    report["status"] = ("not_run" if not meter.calls and not failed else "completed" if completed and not failed and not pending
                        else "partial" if completed else "failed")
    report.update(actual_requests=meter.calls, completed_outputs=completed, failed_cases=failed,
                  not_run_cases=pending, completed_at_utc=datetime.now(timezone.utc).isoformat())
    report["evaluation"] = {name: {"status": "pending_review" if completed else "not_run", "value": None,
        "completed_output_denominator": completed, "planned_denominator": len(cases)}
        for name in ("answer_correctness", "persona_behavior", "unsupported_claims", "natural_unknown")}
    call_costs = [measured_cost(call.get("provider_response", {}).get("usage"), args) for call in meter.records]
    known_costs = [cost for cost in call_costs if cost is not None]
    report["cost_coverage"] = {"known_requests": len(known_costs), "attempted_requests": meter.calls}
    report["estimated_cost_usd"] = sum(known_costs) if known_costs and len(known_costs) == meter.calls else None
    report["valid_schema_outputs"] = sum(row.get("schema_status") == "valid" for row in report["rows"])
    report["not_run"] = ["human blind review", "desktop real-user interaction", "phone device validation"]
    checkpoint()
    return redact(report, api_key)


def main(argv=None):
    args = parse_args(argv)
    result = run(args)
    print(json.dumps({"status": result["status"], "actual_requests": result["actual_requests"],
                      "output": str(args.output), "completed_outputs": result["completed_outputs"]}))


if __name__ == "__main__":
    main()
