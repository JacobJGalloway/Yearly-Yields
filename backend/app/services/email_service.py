"""
Email delivery via Resend.

Each public function builds a params dict and hands it to _send(), which runs the
synchronous Resend SDK call in a thread pool so it doesn't block the event loop.

Callers are responsible for handling exceptions — both functions raise on delivery
failure so the caller can decide whether to retry or surface the error.
"""

import asyncio
import base64
import logging
from datetime import date, datetime
from typing import Optional

import resend

from app.config import settings

logger = logging.getLogger(__name__)

_ALERT_TYPE_LABELS: dict[str, str] = {
    "temperature_high": "Temperature High",
    "temperature_low":  "Temperature Low",
    "humidity_high":    "Humidity High",
    "humidity_low":     "Humidity Low",
    "combined":         "Combined Anomaly",
}


def _fmt_dt(dt: datetime) -> str:
    return f"{dt.strftime('%B')} {dt.day}, {dt.year} at {dt.strftime('%H:%M')} UTC"


def _send_sync(params: dict) -> None:
    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send(params)


async def _send(params: dict) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, params)


def _from_header() -> str:
    return f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"


# ── Alert email ───────────────────────────────────────────────────────────────

def _alert_html(label: str, area_name: str, assessment_summary: str, created_str: str, year: int) -> str:
    app_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:4200"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;color:#1a1a1a;max-width:580px;margin:0 auto;padding:24px;">
  <div style="border-bottom:3px solid #C9A227;padding-bottom:12px;margin-bottom:24px;">
    <span style="font-size:20px;font-weight:bold;letter-spacing:0.5px;">Yearly Yields</span>
  </div>
  <h2 style="color:#b71c1c;margin:0 0 4px;">{label} Alert</h2>
  <p style="color:#666;margin:0 0 20px;font-size:0.9rem;">{area_name} &middot; Detected {created_str}</p>
  <div style="background:#fafafa;border-left:4px solid #C9A227;padding:16px;margin:0 0 24px;font-size:0.95rem;line-height:1.6;">
    {assessment_summary}
  </div>
  <p style="margin:0 0 24px;">
    <a href="{app_url}/dashboard/alerts"
       style="display:inline-block;background:#2e7d32;color:#fff;padding:10px 22px;text-decoration:none;border-radius:4px;font-family:Arial,sans-serif;font-size:0.9rem;">
      View Alert
    </a>
  </p>
  <div style="border-top:1px solid #e0e0e0;margin-top:32px;padding-top:12px;font-size:0.8rem;color:#999;">
    You received this alert because sensor readings for {area_name} exceeded normal thresholds.<br>
    &copy; {year} Yearly Yields
  </div>
</body>
</html>"""


def _alert_plain(label: str, area_name: str, assessment_summary: str, created_str: str) -> str:
    return (
        f"{label} Alert — {area_name}\n"
        f"Detected: {created_str}\n\n"
        f"Agent Assessment:\n{assessment_summary}\n\n"
        f"Log in to Yearly Yields to view and manage this alert."
    )


async def send_alert_email(
    to_email: str,
    to_name: str,
    alert_type: str,
    area_name: str,
    assessment_summary: str,
    created_at: datetime,
) -> None:
    label = _ALERT_TYPE_LABELS.get(alert_type, alert_type.replace("_", " ").title())
    created_str = _fmt_dt(created_at)
    params: dict = {
        "from": _from_header(),
        "to": [to_email],
        "subject": f"[Yearly Yields] {label} Alert — {area_name}",
        "text": _alert_plain(label, area_name, assessment_summary, created_str),
        "html": _alert_html(label, area_name, assessment_summary, created_str, created_at.year),
    }
    await _send(params)
    logger.info("Alert email sent → %s | %s | %s", to_email, alert_type, area_name)


# ── Invoice email ─────────────────────────────────────────────────────────────

def _invoice_html(
    to_name: str,
    short_id: str,
    description: str,
    quantity: float,
    unit: str,
    unit_price: Optional[float],
    total_amount: Optional[float],
    invoice_date_str: str,
    due_date_str: Optional[str],
    year: int,
) -> str:
    price_row = (
        f"<tr><td style='padding:6px 0;color:#666;'>Unit Price</td>"
        f"<td style='padding:6px 0;text-align:right;'>${unit_price:,.2f} / {unit}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#666;'>Total</td>"
        f"<td style='padding:6px 0;text-align:right;font-weight:600;font-size:1.05rem;'>${total_amount:,.2f}</td></tr>"
        if unit_price is not None else
        "<tr><td colspan='2' style='padding:6px 0;color:#b71c1c;font-size:0.85rem;'>Pricing to be confirmed — contact Yearly Yields.</td></tr>"
    )
    due_row = (
        f"<tr><td style='padding:6px 0;color:#666;'>Due Date</td>"
        f"<td style='padding:6px 0;text-align:right;font-weight:500;'>{due_date_str}</td></tr>"
        if due_date_str else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;color:#1a1a1a;max-width:580px;margin:0 auto;padding:24px;">
  <div style="border-bottom:3px solid #C9A227;padding-bottom:12px;margin-bottom:24px;">
    <span style="font-size:20px;font-weight:bold;letter-spacing:0.5px;">Yearly Yields</span>
  </div>
  <h2 style="margin:0 0 4px;">Invoice #{short_id}</h2>
  <p style="color:#666;margin:0 0 20px;font-size:0.9rem;">{invoice_date_str}</p>
  <p style="margin:0 0 20px;line-height:1.6;">
    Dear {to_name},<br><br>
    Please find your invoice attached. A summary is provided below.
  </p>
  <table style="width:100%;border-collapse:collapse;margin:0 0 24px;font-size:0.9rem;">
    <tr><td style="padding:6px 0;color:#666;">Description</td>
        <td style="padding:6px 0;text-align:right;">{description}</td></tr>
    <tr><td style="padding:6px 0;color:#666;">Quantity</td>
        <td style="padding:6px 0;text-align:right;">{quantity:g} {unit}</td></tr>
    {price_row}
    {due_row}
  </table>
  <p style="font-size:0.85rem;color:#666;margin:0 0 8px;">
    The invoice PDF is attached for your records. Please remit payment by the due date.
  </p>
  <div style="border-top:1px solid #e0e0e0;margin-top:32px;padding-top:12px;font-size:0.8rem;color:#999;">
    &copy; {year} Yearly Yields
  </div>
</body>
</html>"""


def _invoice_plain(
    to_name: str,
    short_id: str,
    description: str,
    quantity: float,
    unit: str,
    unit_price: Optional[float],
    total_amount: Optional[float],
    invoice_date_str: str,
    due_date_str: Optional[str],
) -> str:
    lines = [
        f"Invoice #{short_id} — {invoice_date_str}",
        f"\nDear {to_name},",
        "\nPlease find your invoice attached.",
        f"\nDescription: {description}",
        f"Quantity: {quantity:g} {unit}",
    ]
    if unit_price is not None:
        lines.append(f"Unit Price: ${unit_price:,.2f} / {unit}")
        lines.append(f"Total: ${total_amount:,.2f}")
    if due_date_str:
        lines.append(f"Due Date: {due_date_str}")
    lines.append("\nPlease remit payment by the due date.")
    return "\n".join(lines)


async def send_invoice_email(
    to_email: str,
    to_name: str,
    short_id: str,
    description: str,
    quantity: float,
    unit: str,
    unit_price: Optional[float],
    total_amount: Optional[float],
    invoice_date: date,
    due_date: Optional[date],
    pdf_bytes: bytes,
) -> None:
    invoice_date_str = _fmt_dt(datetime(invoice_date.year, invoice_date.month, invoice_date.day)).split(" at ")[0]
    due_date_str = _fmt_dt(datetime(due_date.year, due_date.month, due_date.day)).split(" at ")[0] if due_date else None
    params: dict = {
        "from": _from_header(),
        "to": [to_email],
        "subject": f"Invoice #{short_id} — {description}",
        "text": _invoice_plain(to_name, short_id, description, quantity, unit, unit_price, total_amount, invoice_date_str, due_date_str),
        "html": _invoice_html(to_name, short_id, description, quantity, unit, unit_price, total_amount, invoice_date_str, due_date_str, invoice_date.year),
        "attachments": [
            {
                "filename": f"invoice-{short_id.lower()}.pdf",
                "content": base64.b64encode(pdf_bytes).decode(),
            }
        ],
    }
    await _send(params)
    logger.info("Invoice email sent → %s | invoice #%s", to_email, short_id)


# ── Password reset email ──────────────────────────────────────────────────────

def _reset_html(reset_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;color:#1a1a1a;max-width:580px;margin:0 auto;padding:24px;">
  <div style="border-bottom:3px solid #C9A227;padding-bottom:12px;margin-bottom:24px;">
    <span style="font-size:20px;font-weight:bold;letter-spacing:0.5px;">Yearly Yields</span>
  </div>
  <h2 style="margin:0 0 12px;">Reset your password</h2>
  <p style="margin:0 0 24px;line-height:1.6;">
    We received a request to reset your Yearly Yields password.
    Click the button below to choose a new one. This link expires in 60 minutes.
  </p>
  <p style="margin:0 0 24px;">
    <a href="{reset_url}"
       style="display:inline-block;background:#2e7d32;color:#fff;padding:10px 22px;text-decoration:none;border-radius:4px;font-family:Arial,sans-serif;font-size:0.9rem;">
      Reset Password
    </a>
  </p>
  <p style="font-size:0.85rem;color:#666;margin:0 0 8px;">
    If you didn't request this, you can safely ignore this email.
  </p>
  <p style="font-size:0.8rem;color:#999;word-break:break-all;">
    Or copy this link: {reset_url}
  </p>
</body>
</html>"""


async def send_password_reset_email(to_email: str, reset_url: str) -> None:
    params: dict = {
        "from": _from_header(),
        "to": [to_email],
        "subject": "Reset your Yearly Yields password",
        "text": (
            f"Reset your Yearly Yields password\n\n"
            f"Click the link below (expires in 60 minutes):\n{reset_url}\n\n"
            f"If you didn't request this, ignore this email."
        ),
        "html": _reset_html(reset_url),
    }
    await _send(params)
    logger.info("Password reset email sent → %s", to_email)
