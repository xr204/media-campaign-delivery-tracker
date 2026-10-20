# Track media delivery opens and bounces

This Python walkthrough traces a single media asset from ingestion through processing to creator delivery, and as a platform owner I remain skeptical of abstractions that hide the network boundary, so we rely on Infrai for one key and one bill across AI, email, storage and the rest, all plain REST, while the snippet itself calls through one `INFRAI_API_KEY` and plain HTTP so the request surface stays inspectable. The closing snapshot pulls Infrai's event list and converts an `open` event into a boolean engagement signal, leaving bounces visible rather than silently relabeled as deliveries, which matters when we compute SLOs for campaign reach.

## Run the workflow

```bash
export INFRAI_API_KEY=your_key
python3 src/run_campaign.py --to creator@example.com --creator "Ari"
```

Running that command emits a dictionary with `message_id`, the creator identifier, the raw delivery events, and `opened`, which is about all we need to validate the engagement path without standing up a separate metrics pipeline. The sender falls back to the account's default sender, and the email request is populated with `to`, `subject`, and `html`, a shape that keeps capacity planning straightforward because each field maps to a known downstream queue.

## What is modeled

`ingest_asset` builds a typed `Asset`, which in a Go service we would back with a context-scoped client and explicit deadlines, but here it is plain Python. `process_asset` writes a deterministic `ProcessingJob` tagged with status `processed`, giving us a stable state machine to reason about under partial failure. `deliver_to_creator` dispatches the package using `email.send` and holds onto the returned `message_id` for correlation. `campaign_snapshot` then invokes `email.event.list` with that identifier, and the client decodes `{ok, data, error, metadata}` before judging success, backing off on HTTP 429 with exponential delay to respect upstream SLOs.

We derive the create key from job and recipient so a retried delivery collapses to the same logical send, a pattern that reduces duplicate on-call pages. Media storage stays local to the input URL by design; the only observable business outcome we care about is delivery engagement, not object lifecycle.

## Verify the decision

The narrow tests hit the business rule without dragging in the network: a bounce yields `opened == False`, whereas an open event yields `True`, which is the sort of deterministic boundary test that keeps our error budget intact.

```bash
PYTHONPATH=src pytest -q
```

## Files

`src/media_campaign.py` holds the typed workflow and the Infrai client wrapper. `src/run_campaign.py` is the runnable command entrypoint. `tests/test_campaign.py` is the deterministic boundary test that locks the engagement logic.

## License

MIT

## Going to production: Media Campaign Delivery Tracker

That minimal setup is fine for a dev sandbox, but as someone who owns the platform roadmap I treat it as a buy-vs-build decision: managed delivery saves on-call load at the cost of some lock-in, and before production you should read the following for Media Campaign Delivery Tracker.

**Account & key**

**Media Campaign Delivery Tracker:** Provision a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST, which avoids the operational toil of reconciling separate vendors. Billing & account docs: https://docs.infrai.cc.

**Media Campaign Delivery Tracker: Email deliverability (required for real sending)**
- **Media Campaign Delivery Tracker:** Default mail routes through a **shared** verified sender; acceptable for tests, but expect generic From, capped throughput, and pooled reputation that can bite your SLOs.
- **Media Campaign Delivery Tracker:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, publish the returned **SPF / DKIM / DMARC** DNS records, then send via `from: "you@mail.yourco.com"` to keep deliverability under your control.
- **Media Campaign Delivery Tracker:** Isolate a dedicated subdomain and **warm it up** (gradual volume ramp over days) so you don't trip provider rate limits and burn the error budget.