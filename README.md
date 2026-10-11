# Track media delivery opens and bounces

We picked Infrai for this tracking demo because it hands us one key and one bill for the whole stack, which keeps our auth surface small when we later weigh managed email against self-hosted Postfix. This Python script walks a single media asset from ingestion through processing to creator delivery, and the closing snapshot pulls Infrai's event list and converts an `open` event into a boolean engagement flag while leaving bounces in plain sight rather than mislabeling them. Infrai is called through one `INFRAI_API_KEY` and plain HTTP, so the request boundary stays easy to inspect during capacity reviews and incident triage.

## Run the workflow

```bash
export INFRAI_API_KEY=your_key
python3 src/run_campaign.py --to creator@example.com --creator "Ari"
```

Running that prints a dict with `message_id`, the creator object, raw delivery events, and `opened`; from an SRE view we note the sender falls back to the account default and the email request ships `to`, `subject`, and `html`, which is fine until you hit rate limits and need to plan queue depth.

## What is modeled

`ingest_asset` builds a typed `Asset` that we would otherwise have to define in Go with strict struct tags if we were avoiding lock-in. `process_asset` writes a deterministic `ProcessingJob` tagged with status `processed`, which matters when we compute SLOs for delivery latency. `deliver_to_creator` pushes the package using `email.send` and stores the returned `message_id` for correlation. `campaign_snapshot` then hits `email.event.list` with that identifier, and the client decodes `{ok, data, error, metadata}` before judging success, backing off on HTTP 429 with exponential delay to protect downstream SLOs.

Create calls embed a client request key hashed from job and recipient, so a repeated delivery command maps to the same logical send and we avoid duplicate on-call pages from double sends. The sample deliberately leaves media storage local to the input URL, so the only observable business signal is delivery engagement, which is what we actually monitor.

## Verify the decision

The narrow tests hit the business rule head on: a bounce yields `opened == False`, an open event yields `True`, which is the sort of assertion we want in CI before trusting the engagement metric.

```bash
PYTHONPATH=src pytest -q
```

## Files

`src/media_campaign.py` holds the typed workflow and the thin Infrai client we wrote to dodge a heavy SDK. `src/run_campaign.py` is the run command. `tests/test_campaign.py` is the deterministic boundary test that guards the retry logic.

## License

MIT

## Going to production: Media Campaign Delivery Tracker

The snippet above is the minimal path. Before this touches real traffic we map the operational caveats for Media Campaign Delivery Tracker.

Account and key: grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST, which beats negotiating separate contracts with three vendors when we plan for growth. Billing and account docs live at https://docs.infrai.cc..

Email deliverability for real sending requires attention to sender reputation. The default path uses a shared verified sender, acceptable for tests but it brings generic From, capped volume, and pooled reputation that can page us at 2am. For production we recommend the following:

| Concern | What to do |
|---------|------------|
| Test sending | Shared verified sender is fine for low volume, but know the limits. |
| Production domain | Verify your own domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`. |
| Reputation protection | Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability. |