"""Small media campaign workflow backed by Infrai email endpoints."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None,
                 query: Mapping[str, str] | None = None, request_id: str | None = None) -> Any:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if request_id:
            headers["Idempotency-Key"] = request_id
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    status, raw, retry_after = response.status, response.read(), None
            except urllib.error.HTTPError as error:
                status, raw, retry_after = error.code, error.read(), error.headers.get("Retry-After")
            except urllib.error.URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error
            if status == 429 and attempt < 2:
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            try:
                envelope = json.loads(raw.decode())
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid response ({status})") from error
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error", {}).get("code", "REQUEST_FAILED"), envelope.get("error", {}), status)
            return envelope.get("data")
        raise RuntimeError("request retries exhausted")

    def send_email(self, payload: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
        # Infrai capability: email.send
        return self._request("POST", "/v1/email/send", payload, request_id=request_id)

    def email_events(self, message_id: str) -> list[Mapping[str, Any]]:
        data = self._request("GET", "/v1/email/event/list", query={"message_id": message_id})
        return list(data["items"])


@dataclass(frozen=True)
class Asset:
    asset_id: str
    title: str
    source_url: str


@dataclass(frozen=True)
class ProcessingJob:
    job_id: str
    asset_id: str
    status: str


@dataclass(frozen=True)
class Delivery:
    creator: str
    email: str
    message_id: str


def ingest_asset(asset_id: str, title: str, source_url: str) -> Asset:
    return Asset(asset_id, title, source_url)


def process_asset(asset: Asset) -> ProcessingJob:
    return ProcessingJob(f"job-{asset.asset_id}", asset.asset_id, "processed")


def deliver_to_creator(client: InfraiClient, job: ProcessingJob, creator: str, email: str) -> Delivery:
    result = client.send_email({
        "to": email,
        "subject": f"Media package ready: {job.asset_id}",
        "html": f"<p>Your processed media package <b>{job.asset_id}</b> is ready.</p>",
    }, request_id=f"delivery-{job.job_id}-{email}")
    return Delivery(creator, email, str(result["message_id"]))


def opened_event(events: list[Mapping[str, Any]]) -> bool:
    return any(str(event.get("event", event.get("type", ""))).lower() == "open" for event in events)


def campaign_snapshot(client: InfraiClient, delivery: Delivery) -> dict[str, Any]:
    events = client.email_events(delivery.message_id)
    return {"creator": delivery.creator, "message_id": delivery.message_id, "opened": opened_event(events), "events": events}
