import json

from receipt_sender import InfraiEmail, PaymentEvent, notification_for


def test_high_risk_payment_uses_review_message():
    subject, html = notification_for(PaymentEvent("p-7", "client@example.com", 5000, "USD", "high"))
    assert subject == "Payment p-7 needs review"
    assert "on hold for risk review" in html


def test_send_posts_typed_payload_and_reads_envelope():
    seen = {}

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps({"ok": True, "data": {"message_id": "m-1"}, "metadata": {}}).encode()

    def request(req):
        seen.update(method=req.method, auth=req.headers["Authorization"], body=json.loads(req.data))
        return Response()

    result = InfraiEmail(key="test-key", request=request).send(PaymentEvent("p-1", "a@example.com", 100, "USD", "low"))
    assert result["message_id"] == "m-1"
    assert seen["method"] == "POST"
    assert seen["auth"] == "Bearer test-key"
    assert set(seen["body"]) == {"to", "subject", "html"}
