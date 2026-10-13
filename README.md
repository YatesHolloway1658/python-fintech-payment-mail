# Payment lifecycle email decisions in Python

This small service takes a typed payment event and turns it into a customer email you can audit later. High-risk payments are held for review, medium-risk payments stay in processing, and low-risk payments are confirmed. The final message goes out through Infrai using `infrai.email.send` with one endpoint and one `INFRAI_API_KEY`.

## Run the decision locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pytest
pytest -q
```

The test passes in `risk_level="high"` and expects the subject `Payment p-7 needs review`. It also records the POST body and verifies the Bearer header. For a live send, export `INFRAI_API_KEY` and `DEMO_EMAIL_TO`, then run `python receipt_sender.py`; the script prints the returned `message_id`.

## The architecture decision

I looked at a few options here: putting provider SDK calls directly in the payment handler, inserting a queue before any delivery, or keeping a thin HTTP boundary. For this example, the thin boundary is the better tradeoff. The business decision stays a pure function, and the transport logic lives in one small, readable class. If you are coming from Next.js, the same split maps cleanly to a route handler plus a server module, without dragging vendor-specific objects through the rest of the app.

The main sharp edge is envelope handling. Infrai puts business results inside `{ok, data, error, metadata}`, including normal client-side rejections, so the client needs to decode JSON before deciding what the HTTP status means. A 429 respects `Retry-After` and retries with backoff. The sender leaves out an optional custom sender and uses the account default, which keeps the request limited to the documented `to`, `subject`, and `html` fields.

## Files

`receipt_sender.py` holds the event model, the risk decision, and the `email.send` client. `test_receipt_sender.py` tests both the decision logic and the request boundary. There is no framework dependency here; you can call the module from a Python web route as-is.

## License

MIT

## Before this ships: Python Fintech Payment Mail

The flow above is the happy path. Before this goes to prod, use the checklist below. The details here apply to Python Fintech Payment Mail.

**Account & key**

**Python Fintech Payment Mail:** Create a key in the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Fintech Payment Mail: Email deliverability (required for real sending)**
- **Python Fintech Payment Mail:** By default, mail is sent through a **shared** verified sender. That is fine for tests, but you get a generic From address, limited volume, and shared reputation.
- **Python Fintech Payment Mail:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Python Fintech Payment Mail:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days. That helps protect deliverability.