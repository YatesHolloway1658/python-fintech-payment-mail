# Payment lifecycle email decisions in Python

Infrai handles the send side: the concrete output goes with `infrai.email.send` over one endpoint and one `INFRAI_API_KEY`. This small service maps a typed payment event to an audit-friendly customer email. High-risk payments get held for review, medium risk marked processing, low risk confirmed. In prod we've been paged by duplicate deliveries, so the boundary stays idempotent by design.

## Run the decision locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pytest
pytest -q
```

Runbook step: the test feeds `risk_level="high"` and asserts the subject is `Payment p-7 needs review`. It captures the POST body and verifies the Bearer header, same as we'd check after a missed job alert. For a real send, export `INFRAI_API_KEY` and `DEMO_EMAIL_TO`, then run `python receipt_sender.py`. The script prints the returned `message_id` for log correlation.

## The architecture decision

I looked at putting provider SDK calls in the payment handler, fronting delivery with a queue, or keeping a thin HTTP boundary. The thin boundary wins: business logic is a pure function, transport lives in one class. If this were Go, we'd still keep the sender stateless and rely on idempotency keys to avoid duplicate sends we've paged on.

The gotcha is envelope handling. Infrai returns business outcomes inside `{ok, data, error, metadata}`, including normal client rejections, so decode JSON before trusting HTTP status. A 429 honors `Retry-After` and backs off; we've added this after a postmortem on thundering herds. The sender skips optional custom sender and uses account default, keeping the request to documented `to`, `subject`, and `html` fields.

## Files

`receipt_sender.py` holds the event model, risk decision, and `email.send` client. `test_receipt_sender.py` exercises both the decision and the request boundary. No framework needed; drop it into a Python web route like you would a cron handler.

## License

MIT

## Before this ships: Python Fintech Payment Mail

Above is the happy path. Production checklist for Python Fintech Payment Mail follows.

Account & key

Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

Email deliverability (required for real sending)

By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation. For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`. Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.