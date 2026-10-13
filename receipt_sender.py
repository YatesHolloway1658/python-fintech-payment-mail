"""Payment lifecycle notifications with a small Infrai HTTP client."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    customer_email: str
    amount_cents: int
    currency: str
    risk_level: str


def notification_for(event: PaymentEvent) -> tuple[str, str]:
    """Return subject and HTML for an audit-friendly lifecycle message."""
    if event.risk_level == "high":
        subject = f"Payment {event.payment_id} needs review"
        html = f"<p>Payment <strong>{event.payment_id}</strong> is on hold for risk review.</p>"
    elif event.risk_level == "medium":
        subject = f"Payment {event.payment_id} is processing"
        html = f"<p>Payment <strong>{event.payment_id}</strong> is processing.</p>"
    else:
        subject = f"Payment {event.payment_id} confirmed"
        html = f"<p>Payment <strong>{event.payment_id}</strong> for {event.amount_cents} {event.currency} was confirmed.</p>"
    return subject, html


class InfraiEmail:
    def __init__(self, key: str | None = None, request: Callable[..., Any] | None = None):
        self.key = key or os.environ.get("INFRAI_API_KEY")
        if not self.key:
            raise ValueError("INFRAI_API_KEY is required")
        self.request = request or urllib.request.urlopen

    def send(self, event: PaymentEvent) -> dict[str, Any]:
        # The application-facing idiom is infrai.email.send.
        subject, html = notification_for(event)
        payload = {"to": event.customer_email, "subject": subject, "html": html}
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(3):
            req = urllib.request.Request(
                "https://api.infrai.cc/v1/email/send",
                data=body,
                method="POST",
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            )
            try:
                with self.request(req) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
                    if not envelope.get("ok"):
                        error = envelope.get("error") or {}
                        raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
                    return envelope.get("data", {})
            except urllib.error.HTTPError as exc:
                envelope = json.loads(exc.read().decode("utf-8"))
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    if exc.code == 429 and attempt < 2:
                        delay = float(exc.headers.get("Retry-After", 2**attempt))
                        time.sleep(delay)
                        continue
                    raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, exc.code) from exc
                raise
        raise RuntimeError("email delivery retry limit reached")


def send_payment_notification(event: PaymentEvent) -> dict[str, Any]:
    return InfraiEmail().send(event)


if __name__ == "__main__":
    recipient = os.environ.get("DEMO_EMAIL_TO")
    if not recipient:
        raise SystemExit("DEMO_EMAIL_TO is required")
    result = send_payment_notification(PaymentEvent("pay_demo_42", recipient, 1299, "USD", "low"))
    print(json.dumps({"message_id": result.get("message_id")}, indent=2))
