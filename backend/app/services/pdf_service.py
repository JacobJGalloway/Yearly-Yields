"""
PDF generation service for invoices.

Renders invoice.html via Jinja2, then converts to PDF using xhtml2pdf (pure Python,
no system-level GTK/Pango deps required on Windows).  xhtml2pdf is synchronous —
the async wrapper runs it in a thread pool so it doesn't block the event loop.

Customer logo mapping is keyed by exact customer name as seeded in admin.py.
Unknown customer names render without a logo gracefully.

Dates are pre-formatted in Python (cross-platform; avoids %-d / %#d divergence).
"""

import asyncio
import io
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from xhtml2pdf import pisa

from app.models.crop import CropCycle
from app.models.field import GrowingArea
from app.models.invoice import Invoice

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)

_CUSTOMER_LOGO: dict[str, str] = {
    "Global Harvest": "assets/customers/global-harvest-dist/Global Harvest Light Mode.png",
    "National Nourish": "assets/customers/national-nourish-logis/National Nourish Light Mode.png",
    "Prairie Start Nursery": "assets/customers/prairie-start-nursery/Prairie Start Nursery Light Mode.png",
}


def _fmt_date(d: Optional[date]) -> str:
    if d is None:
        return ""
    return d.strftime("%B") + " " + str(d.day) + ", " + str(d.year)


def _link_callback(uri: str, rel: str) -> str:
    """Resolve relative asset paths to absolute filesystem paths for xhtml2pdf."""
    path = _TEMPLATES_DIR / uri
    return str(path)


def _render_pdf(html: str) -> bytes:
    buf = io.BytesIO()
    result = pisa.CreatePDF(html, dest=buf, link_callback=_link_callback)
    if result.err:
        raise RuntimeError(f"PDF generation error (xhtml2pdf err={result.err})")
    return buf.getvalue()


async def generate_invoice_pdf(invoice_id: uuid.UUID, db: AsyncSession) -> Optional[bytes]:
    result = await db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.customer),
            selectinload(Invoice.crop_cycle).options(
                selectinload(CropCycle.growing_area),
                selectinload(CropCycle.crop),
            ),
        )
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        return None

    customer = invoice.customer
    cycle = invoice.crop_cycle
    area: Optional[GrowingArea] = cycle.growing_area if cycle else None

    template = _env.get_template("invoice.html")
    html = template.render(
        invoice=invoice,
        customer=customer,
        area_name=area.name if area else None,
        crop_name=cycle.crop.name.replace("_", " ").title() if cycle and cycle.crop else None,
        customer_logo=_CUSTOMER_LOGO.get(customer.name) if customer else None,
        has_pricing=invoice.unit_price is not None,
        short_id=str(invoice.id)[:8].upper(),
        invoice_date_str=_fmt_date(invoice.invoice_date),
        due_date_str=_fmt_date(invoice.due_date),
        year=invoice.invoice_date.year if invoice.invoice_date else "",
    )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _render_pdf, html)
