"""SMS sender abstraction.

Two implementations:
  - LogSender: prints the message + returns a 'log_only' status. Used
    automatically when Twilio isn't configured. The override request
    response also includes the code in `code_dev_echo` so the user can
    proceed without setting up SMS.
  - TwilioSender: sends a real SMS via Twilio's REST API. No SDK
    dependency — uses httpx directly.

Per spec §2.6: 'The override service is deliberately friction. It is
supposed to be slightly inconvenient. If it were one tap away, it would
not solve the consent-of-future-self problem.' The LogSender path is
*development only* — in real use the user has to physically obtain the
code from the approver.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from buddy.config import get_settings

log = logging.getLogger("buddy.sms")


@dataclass
class SmsResult:
    status: str          # 'sent' | 'failed' | 'log_only'
    detail: str = ""


class SmsSender(Protocol):
    def send(self, *, to: str, body: str) -> SmsResult:
        ...


class LogSender:
    """No-op sender for dev / unconfigured installs. Logs the message
    and returns 'log_only', which is also the signal the API uses to
    echo the override code back to the caller."""

    def send(self, *, to: str, body: str) -> SmsResult:
        log.info("SMS [log_only] to=%s body=%s", to, body)
        return SmsResult(status="log_only", detail="No Twilio configured; code echoed in response.")


class TwilioSender:
    BASE = "https://api.twilio.com/2010-04-01"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send(self, *, to: str, body: str) -> SmsResult:
        try:
            resp = httpx.post(
                f"{self.BASE}/Accounts/{self.account_sid}/Messages.json",
                auth=(self.account_sid, self.auth_token),
                data={"From": self.from_number, "To": to, "Body": body},
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            return SmsResult(status="failed", detail=f"network: {exc}")
        if resp.status_code in (200, 201):
            try:
                sid = resp.json().get("sid", "")
            except Exception:
                sid = ""
            return SmsResult(status="sent", detail=f"twilio sid={sid}")
        return SmsResult(
            status="failed",
            detail=f"twilio status {resp.status_code}: {resp.text[:200]}",
        )


def get_sender() -> SmsSender:
    settings = get_settings()
    if settings.sms_configured:
        return TwilioSender(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_number=settings.twilio_from_number,
        )
    return LogSender()
