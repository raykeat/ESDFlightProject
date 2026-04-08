"""
Notification Service
====================
Atomic microservice — consumes booking.confirmed from RabbitMQ
and sends booking confirmation email directly via SendGrid REST API.

Scenarios 1 & 2: booking confirmation + flight cancellation emails.

Usage:
    python app.py
"""

import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error
import base64
import io

import pika
from dotenv import load_dotenv
from flask import Flask, request
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# SENDGRID — calls REST API directly (bypasses latin-1 encoding issue)
# =============================================================================

def send_email(to_email: str, to_name: str, subject: str, html: str, text: str, pdf_bytes: bytes = None, pdf_filename: str = "booking_confirmation.pdf") -> dict:
    """
    Sends email via SendGrid REST API using UTF-8 encoding.
    Optionally attaches a PDF if pdf_bytes is provided.
    """
    api_key    = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["SENDGRID_FROM_EMAIL"]
    from_name  = os.environ.get("SENDGRID_FROM_NAME", "YourAirline")

    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from":    {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html",  "value": html}
        ]
    }

    if pdf_bytes:
        payload["attachments"] = [{
            "content":     base64.b64encode(pdf_bytes).decode("utf-8"),
            "type":        "application/pdf",
            "filename":    pdf_filename,
            "disposition": "attachment",
        }]
        logger.info("PDF attachment added: %s (%d bytes)", pdf_filename, len(pdf_bytes))

    try:
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data    = data,
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json; charset=utf-8",
            },
            method = "POST"
        )
        with urllib.request.urlopen(req) as resp:
            message_id = resp.headers.get("X-Message-Id", "")
            logger.info("Email sent to %s | status=%s", to_email, resp.status)
            return {"success": True, "message_id": message_id, "status_code": resp.status}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error("SendGrid HTTP error for %s: %s - %s", to_email, e.code, error_body)
        return {"success": False, "error": error_body, "status_code": e.code}
    except Exception as e:
        logger.error("SendGrid error for %s: %s", to_email, str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# HELPERS
# =============================================================================

def _format_money(amount) -> str:
    try:
        return f"{float(amount):.2f}"
    except Exception:
        return str(amount)


def _display_name(data: dict) -> str:
    if data.get("passengerName"):
        return data["passengerName"]
    first = data.get("firstName") or ""
    last  = data.get("lastName")  or ""
    full  = f"{first} {last}".strip()
    return full or "Valued Passenger"


def _normalize_flights(data: dict) -> list:
    flights = data.get("flights")
    if isinstance(flights, list) and flights:
        return flights
    return [{
        "leg":            "outbound",
        "flight_number":  data.get("flight_number", "N/A"),
        "origin":         data.get("origin", "Origin"),
        "destination":    data.get("destination", "Destination"),
        "departure_date": data.get("departure_date", "N/A"),
        "seat_number":    data.get("seat_number", "N/A"),
        "booking_id":     data.get("booking_id"),
    }]


# =============================================================================
# PDF HELPERS
# =============================================================================

def _pdf_build(story: list) -> bytes:
    """Builds the PDF from a story list and returns bytes."""
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _make_styles():
    """Returns commonly used ParagraphStyle objects."""
    base = getSampleStyleSheet()
    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)
    return ps


def _detail_row_table(rows: list, col_l: float, col_r: float) -> Table:
    """Two-column label/value table used in receipt sections."""
    BORDER = colors.HexColor("#e2e8f0")
    ALT    = colors.HexColor("#f8fafc")
    t = Table(rows, colWidths=[col_l, col_r])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [ALT, colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
        ("TOPPADDING",     (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# =============================================================================
# PDF GENERATOR — Scenario 1: Boarding-pass style booking confirmation
# =============================================================================

def generate_booking_pdf(data: dict) -> bytes:
    """Boarding-pass style booking confirmation PDF for Scenario 1."""
    PAGE_W  = 17 * cm
    INNER_W = 16 * cm
    COL_L   = 5.5 * cm
    COL_R   = PAGE_W - COL_L

    NAVY    = colors.HexColor("#1e3356")
    NAVY2   = colors.HexColor("#162a47")
    WHITE   = colors.white
    LGRAY   = colors.HexColor("#94a3b8")
    BORDER  = colors.HexColor("#e2e8f0")

    ps = _make_styles()

    s_brand = ps("s_brand", fontSize=13, fontName="Helvetica-Bold", textColor=WHITE)
    s_h1    = ps("s_h1",    fontSize=18, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_bid   = ps("s_bid",   fontSize=10, textColor=LGRAY, alignment=1)
    s_orig  = ps("s_orig",  fontSize=26, fontName="Helvetica-Bold", textColor=WHITE, alignment=0)
    s_dest  = ps("s_dest",  fontSize=26, fontName="Helvetica-Bold", textColor=WHITE, alignment=2)
    s_mid   = ps("s_mid",   fontSize=10, textColor=LGRAY, alignment=1)
    s_city  = ps("s_city",  fontSize=9,  textColor=LGRAY, alignment=1)
    s_lbl_w = ps("s_lbl_w", fontSize=9,  textColor=LGRAY, alignment=1)
    s_val_w = ps("s_val_w", fontSize=11, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_sec   = ps("s_sec",   fontSize=13, fontName="Helvetica-Bold", textColor=colors.HexColor("#1e40af"), spaceBefore=12, spaceAfter=4)
    s_lbl   = ps("s_lbl",   fontSize=10, textColor=colors.HexColor("#6b7280"))
    s_val   = ps("s_val",   fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"), alignment=2)
    s_foot  = ps("s_foot",  fontSize=9,  textColor=colors.HexColor("#9ca3af"), alignment=1)

    flights       = _normalize_flights(data)
    passenger     = data.get("passenger_name", "Passenger")
    booking_id    = data.get("booking_id", "N/A")
    amount_paid   = data.get("amount_paid", 0)
    THIRD         = INNER_W / 3

    def _flight_header(flight, show_branding: bool) -> Table:
        orig       = str(flight.get("origin", "N/A"))
        dest       = str(flight.get("destination", "N/A"))
        flight_num = str(flight.get("flight_number", "N/A"))
        dep_date   = str(flight.get("departure_date", "N/A"))
        seat       = str(flight.get("seat_number", "N/A"))
        orig_code  = orig[:3].upper()
        dest_code  = dest[:3].upper()

        route_sub = Table(
            [
                [Paragraph(orig_code, s_orig), Paragraph("————————", s_mid), Paragraph(dest_code, s_dest)],
                [Paragraph(orig,      s_city), Paragraph(flight_num, s_mid), Paragraph(dest,      s_city)],
            ],
            colWidths=[INNER_W * 0.35, INNER_W * 0.30, INNER_W * 0.35],
        )
        route_sub.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (0, -1), "LEFT"),
            ("ALIGN",         (1, 0), (1, -1), "CENTER"),
            ("ALIGN",         (2, 0), (2, -1), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))

        details_sub = Table(
            [
                [Paragraph("Date",    s_lbl_w), Paragraph("Seat",    s_lbl_w), Paragraph("Class",   s_lbl_w)],
                [Paragraph(dep_date,  s_val_w), Paragraph(seat,      s_val_w), Paragraph("Economy", s_val_w)],
            ],
            colWidths=[THIRD, THIRD, THIRD],
        )
        details_sub.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY2),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("LINEABOVE",     (0, 0), (-1, 0), 0.5, LGRAY),
        ]))

        rows = []
        if show_branding:
            rows += [
                [Paragraph("BlazeAir", s_brand)],
                [Paragraph("Your flight is confirmed!", s_h1)],
                [Paragraph(f"Booking ID: {booking_id}", s_bid)],
            ]
        else:
            rows += [[Paragraph("Return Flight", s_h1)]]

        rows += [[route_sub], [details_sub]]

        t = Table(rows, colWidths=[PAGE_W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0.5 * cm),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0.5 * cm),
            ("TOPPADDING",    (0, 0), (0, 0), 0.4 * cm),
            ("BOTTOMPADDING", (0, -1), (0, -1), 0),
            ("TOPPADDING",    (0, 1), (0, -2), 0.15 * cm),
            ("BOTTOMPADDING", (0, 0), (0, -2), 0.15 * cm),
        ]))
        return t

    story = []
    story.append(_flight_header(flights[0], show_branding=True))
    for flight in flights[1:]:
        story.append(Spacer(1, 0.3 * cm))
        story.append(_flight_header(flight, show_branding=False))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Your Receipt", s_sec))

    receipt_rows = [
        [Paragraph("Passenger Name", s_lbl), Paragraph(str(passenger), s_val)],
        [Paragraph("Booking ID",     s_lbl), Paragraph(str(booking_id), s_val)],
    ]
    if data.get("return_booking_id"):
        receipt_rows.append([Paragraph("Return Booking ID", s_lbl), Paragraph(str(data["return_booking_id"]), s_val)])
    receipt_rows.append([Paragraph("Amount Paid", s_lbl), Paragraph(f"SGD ${_format_money(amount_paid)}", s_val)])
    receipt_rows.append([Paragraph("Status",      s_lbl), Paragraph("Confirmed", s_val)])

    story.append(_detail_row_table(receipt_rows, COL_L, COL_R))

    passengers = data.get("passengers") or []
    if len(passengers) > 1:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Passenger Details", s_sec))
        s_p_hdr = ps("s_p_hdr", fontSize=9, fontName="Helvetica-Bold", textColor=colors.HexColor("#6b7280"), alignment=1)
        s_p_val = ps("s_p_val", fontSize=9, textColor=colors.HexColor("#111827"), alignment=1)
        pax_header = [
            Paragraph("Passenger", s_p_hdr),
            Paragraph("Seat", s_p_hdr),
            Paragraph("Booking Ref", s_p_hdr),
        ]
        pax_rows = [pax_header]
        for pax in passengers:
            pax_rows.append([
                Paragraph(str(pax.get("name") or "Passenger"), s_p_val),
                Paragraph(str(pax.get("seatNumber") or "N/A"), s_p_val),
                Paragraph(f"#{pax.get('bookingID', '-')}", s_p_val),
            ])
        pax_table = Table(pax_rows, colWidths=[INNER_W * 0.50, INNER_W * 0.22, INNER_W * 0.28])
        pax_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#f3f4f6")),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
            ("GRID",          (0, 0), (-1, -1), 0.5, BORDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(pax_table)

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width=PAGE_W, thickness=0.5, color=BORDER))
    story.append(Paragraph("Thank you for flying with BlazeAir. Please keep this document for your records.", s_foot))

    return _pdf_build(story)


# =============================================================================
# EMAIL TEMPLATE — Scenario 1
# =============================================================================

def booking_confirmation_template(data: dict) -> dict:
        """Scenario 1: Booking confirmed after successful payment."""
        flights = _normalize_flights(data)
        is_round_trip = len(flights) > 1
        heading = "Your Round-Trip Booking is Confirmed!" if is_round_trip else "Your Booking is Confirmed!"
        subject = "Booking Confirmed - Round Trip" if is_round_trip else f"Booking Confirmed - {flights[0].get('flight_number', 'N/A')}"

        rows_html = []
        rows_text = []
        for index, flight in enumerate(flights, start=1):
                leg_label = "Departure Flight" if flight.get("leg") == "outbound" else "Return Flight"
                rows_html.append(f"""
                    <tr style="background:{'#f8fafc' if index % 2 == 1 else '#ffffff'};">
                        <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-weight:700;color:#111827;">{leg_label}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;">{flight.get('flight_number', 'N/A')}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#374151;">{flight.get('origin', 'Origin')} → {flight.get('destination', 'Destination')}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#374151;">{flight.get('departure_date', 'N/A')}</td>
                        <td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#374151;">{flight.get('seat_number', 'N/A')}</td>
                    </tr>
                """)
                rows_text.append(
                        f"{leg_label}: {flight.get('flight_number', 'N/A')} | "
                        f"{flight.get('origin', 'Origin')} -> {flight.get('destination', 'Destination')} | "
                        f"Date: {flight.get('departure_date', 'N/A')} | Seat: {flight.get('seat_number', 'N/A')}"
                )

        return {
                "subject": subject,
                "html": f"""
                <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:700px;margin:20px auto;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
                    <div style="background:linear-gradient(135deg,#f8fafc,#fff1f2);padding:24px 28px;border-bottom:1px solid #f1f5f9;">
                        <div style="display:inline-flex;align-items:center;gap:8px;background:#ecfdf3;color:#15803d;border:1px solid #bbf7d0;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;"></span>
                            Confirmed
                        </div>
                        <h2 style="margin:16px 0 0;font-size:30px;line-height:1.2;color:#1d1d1f;">{heading}</h2>
                        <p style="margin:10px 0 0;font-size:14px;color:#4b5563;">Dear {data['passenger_name']}, your booking has been successfully confirmed. Here are your flight details:</p>
                    </div>
                    <div style="padding:24px 28px;">
                        <h3 style="color:#e63946;margin-top:0;">Flight Details</h3>
                        <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
                            <thead>
                                <tr style="background:#f3f4f6;">
                                    <th style="text-align:left;padding:10px 12px;font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">Leg</th>
                                    <th style="text-align:left;padding:10px 12px;font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">Flight</th>
                                    <th style="text-align:left;padding:10px 12px;font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">Route</th>
                                    <th style="text-align:left;padding:10px 12px;font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">Date</th>
                                    <th style="text-align:left;padding:10px 12px;font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">Seat</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(rows_html)}
                            </tbody>
                        </table>
                        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
                            <tr><td style="padding:8px 0;color:#6b7280;">Booking ID</td><td style="padding:8px 0;text-align:right;font-weight:700;color:#111827;">{data.get('booking_id', 'N/A')}</td></tr>
                            <tr><td style="padding:8px 0;color:#6b7280;">Return Booking ID</td><td style="padding:8px 0;text-align:right;font-weight:700;color:#111827;">{data.get('return_booking_id') or '-'}</td></tr>
                            <tr><td style="padding:8px 0;color:#6b7280;">Total Amount Paid</td><td style="padding:8px 0;text-align:right;font-weight:700;color:#111827;">${_format_money(data.get('amount_paid', '0'))}</td></tr>
                        </table>
                        <p style="margin:18px 0 0;color:#4b5563;font-size:13px;">Thank you for flying with us!</p>
                    </div>
                </div>
                """,
                "text": (
                        f"Booking Confirmed! Booking ID: {data.get('booking_id', 'N/A')}. "
                        + " | ".join(rows_text)
                        + f". Total Amount Paid: ${_format_money(data.get('amount_paid', '0'))}."
                ),
        }

# =============================================================================
# EMAIL TEMPLATE — Scenario 2 (Flight cancellation)
# =============================================================================

def booking_confirmation_template_v2(data: dict) -> dict:
    """Scenario 1: Booking confirmed after successful payment."""
    flights = _normalize_flights(data)
    is_round_trip = len(flights) > 1
    heading = "Your Round-Trip Booking is Confirmed!" if is_round_trip else "Your Booking is Confirmed!"
    subject = "Booking Confirmed - Round Trip" if is_round_trip else f"Booking Confirmed - {flights[0].get('flight_number', 'N/A')}"
    passengers = data.get("passengers") or []
    passenger_count = int(data.get("group_size") or len(passengers) or 1)

    flight_sections_html = []
    rows_text = []
    for flight in flights:
        leg_label = "Departure Flight" if flight.get("leg") == "outbound" else "Return Flight"
        flight_sections_html.append(f"""
            <div style="border:1px solid #e5e7eb;border-radius:18px;background:#ffffff;overflow:hidden;margin-bottom:14px;">
                <div style="background:linear-gradient(135deg,#fff7f8 0%,#ffffff 100%);padding:16px 18px;border-bottom:1px solid #eef2f7;">
                    <div style="font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#e63946;">{leg_label}</div>
                    <div style="margin-top:10px;font-size:24px;font-weight:700;color:#1d1d1f;">{flight.get('origin', 'Origin')} &rarr; {flight.get('destination', 'Destination')}</div>
                    <div style="margin-top:6px;font-size:14px;color:#6b7280;">Flight {flight.get('flight_number', 'N/A')} &nbsp;&middot;&nbsp; {flight.get('departure_date', 'N/A')}</div>
                </div>
                <table style="width:100%;border-collapse:collapse;">
                    <tr>
                        <td style="padding:12px 18px;color:#6b7280;font-size:13px;">Seat(s)</td>
                        <td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{flight.get('seat_number', 'N/A')}</td>
                    </tr>
                    <tr style="background:#fafbfc;">
                        <td style="padding:12px 18px;color:#6b7280;font-size:13px;">Booking Reference</td>
                        <td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{flight.get('booking_id') or data.get('booking_id', 'N/A')}</td>
                    </tr>
                </table>
            </div>
        """)
        rows_text.append(
            f"{leg_label}: {flight.get('flight_number', 'N/A')} | "
            f"{flight.get('origin', 'Origin')} -> {flight.get('destination', 'Destination')} | "
            f"Date: {flight.get('departure_date', 'N/A')} | Seat: {flight.get('seat_number', 'N/A')}"
        )

    passenger_rows_html = []
    passenger_rows_text = []
    for index, passenger in enumerate(passengers, start=1):
        passenger_name = passenger.get("name") or f"Passenger {index}"
        seat_number = passenger.get("seatNumber") or "TBC"
        booking_ref = passenger.get("bookingID") or "-"
        passenger_rows_html.append(f"""
            <tr style="background:{'#ffffff' if index % 2 == 1 else '#fafbfc'};">
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#111827;font-weight:600;">{passenger_name}</td>
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#4b5563;">{seat_number}</td>
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#4b5563;text-align:right;">#{booking_ref}</td>
            </tr>
        """)
        passenger_rows_text.append(f"{passenger_name} | Seat {seat_number} | Booking #{booking_ref}")

    if not passenger_rows_html:
        passenger_rows_html.append(f"""
            <tr>
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#111827;font-weight:600;">{data.get('passenger_name', 'Passenger')}</td>
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#4b5563;">{data.get('seat_number', 'N/A')}</td>
                <td style="padding:12px 14px;border-bottom:1px solid #edf1f5;color:#4b5563;text-align:right;">#{data.get('booking_id', 'N/A')}</td>
            </tr>
        """)
        passenger_rows_text.append(
            f"{data.get('passenger_name', 'Passenger')} | Seat {data.get('seat_number', 'N/A')} | Booking #{data.get('booking_id', 'N/A')}"
        )

    return {
        "subject": subject,
        "html": f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:760px;margin:20px auto;border:1px solid #e8edf4;border-radius:24px;overflow:hidden;background:#ffffff;">
            <div style="background:radial-gradient(circle at top right,rgba(230,57,70,0.12),transparent 30%),linear-gradient(135deg,#fff8f8 0%,#ffffff 100%);padding:28px 30px;border-bottom:1px solid #f1f5f9;">
                <div style="font-size:12px;font-weight:800;letter-spacing:0.16em;text-transform:uppercase;color:#e63946;">Blaze Air Booking Confirmation</div>
                <div style="display:inline-flex;align-items:center;background:#ecfdf3;color:#15803d;border:1px solid #bbf7d0;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-top:14px;">
                    Confirmed
                </div>
                <h2 style="margin:16px 0 0;font-size:34px;line-height:1.15;color:#1d1d1f;">{heading}</h2>
                <p style="margin:12px 0 0;font-size:15px;line-height:1.7;color:#4b5563;">Dear {data.get('passenger_name', 'Passenger')}, your booking has been successfully confirmed. We have included your itinerary, traveller details, and payment summary below for easy reference.</p>
            </div>
            <div style="padding:28px 30px;">
                <div style="margin-bottom:22px;padding:18px 20px;border:1px solid #edf1f5;border-radius:18px;background:#fcfcfd;">
                    <table style="width:100%;border-collapse:collapse;">
                        <tr>
                            <td style="padding:0 0 10px;color:#6b7280;font-size:13px;">Lead passenger</td>
                            <td style="padding:0 0 10px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{data.get('passenger_name', 'Passenger')}</td>
                        </tr>
                        <tr>
                            <td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #edf1f5;">Passengers</td>
                            <td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #edf1f5;">{passenger_count}</td>
                        </tr>
                        <tr>
                            <td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #edf1f5;">Booking ID</td>
                            <td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #edf1f5;">#{data.get('booking_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #edf1f5;">Return Booking ID</td>
                            <td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #edf1f5;">{('#' + str(data.get('return_booking_id'))) if data.get('return_booking_id') else '-'}</td>
                        </tr>
                        <tr>
                            <td style="padding:10px 0 0;color:#6b7280;font-size:13px;border-top:1px solid #edf1f5;">Total Paid</td>
                            <td style="padding:10px 0 0;text-align:right;color:#e63946;font-size:24px;font-weight:800;border-top:1px solid #edf1f5;">${_format_money(data.get('amount_paid', '0'))}</td>
                        </tr>
                    </table>
                </div>

                <h3 style="color:#e63946;margin:0 0 12px;font-size:18px;">Itinerary</h3>
                {''.join(flight_sections_html)}

                <h3 style="color:#e63946;margin:24px 0 12px;font-size:18px;">Passenger Details</h3>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
                    <thead>
                        <tr style="background:#f7f7f8;">
                            <th style="text-align:left;padding:12px 14px;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;color:#6b7280;">Passenger</th>
                            <th style="text-align:left;padding:12px 14px;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;color:#6b7280;">Seat</th>
                            <th style="text-align:right;padding:12px 14px;font-size:12px;letter-spacing:0.05em;text-transform:uppercase;color:#6b7280;">Booking Ref</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(passenger_rows_html)}
                    </tbody>
                </table>

                <div style="margin-top:22px;padding:18px 20px;border-radius:18px;background:#fff8f8;border:1px solid #fde2e5;color:#4b5563;font-size:13px;line-height:1.7;">
                    Please keep this email for your records. You can review your itinerary, seats, and any future booking updates from your Blaze Air booking pages.
                </div>

                <p style="margin:20px 0 0;color:#4b5563;font-size:13px;">Thank you for flying with us.</p>
            </div>
        </div>
        """,
        "text": (
            f"Booking Confirmed! Booking ID: {data.get('booking_id', 'N/A')}. "
            + f"Passenger count: {passenger_count}. "
            + " | ".join(rows_text)
            + (" | Travellers: " + " ; ".join(passenger_rows_text) if passenger_rows_text else "")
            + f". Total Amount Paid: ${_format_money(data.get('amount_paid', '0'))}."
        ),
    }

booking_confirmation_template = booking_confirmation_template_v2

def flight_cancelled_alt_template(data: dict) -> dict:
    """
    Scenario 2 Path A: Flight cancelled, alternative flight found.
    RabbitMQ routing key: flight.cancelled.alt
    Payload structure: { "type": "...", "email": "...", "data": { ... } }
    """
    inner          = data.get("data", data)
    orig_flight    = inner.get("OriginalFlight", "N/A")
    new_flight     = inner.get("NewFlight", "N/A")
    new_date       = inner.get("NewDate", "N/A")
    new_dep_time   = inner.get("NewDepartureTime", "N/A")
    seat_number    = inner.get("SeatNumber", "N/A")
    coupon_code    = inner.get("CouponCode", "N/A")
    discount       = inner.get("DiscountAmount", 0)
    review_link    = inner.get("AcceptRejectLink", "#")
    accept_link    = inner.get("AcceptLink", review_link)
    reject_link    = inner.get("RejectLink", review_link)
    booking_id     = inner.get("BookingID", "N/A")
    passenger_name = inner.get("PassengerName", "Valued Passenger")
    group_size     = int(inner.get("GroupSize") or 1)
    is_group       = group_size > 1

    group_row_html = (
        f'<tr><td style="padding:10px 12px;color:#6b7280;">Passengers in Group</td>'
        f'<td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{group_size}</td></tr>'
    ) if is_group else ""
    group_seat_row_html = (
        f'<tr><td style="padding:10px 12px;color:#6b7280;">Seats</td>'
        f'<td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">To be assigned — seats kept together</td></tr>'
    ) if is_group else (
        f'<tr><td style="padding:10px 12px;color:#6b7280;">Seat Number</td>'
        f'<td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{seat_number}</td></tr>'
    )
    group_intro = (
        f"Dear {passenger_name}, your group booking of {group_size} passengers has been affected. "
        "We have found an alternative flight that accommodates your entire group at no extra charge."
    ) if is_group else (
        f"Dear {passenger_name}, we have found an alternative flight for you at no extra charge."
    )
    group_refund_note = (
        "If you reject, a full refund will be issued for all passengers in your group."
    ) if is_group else (
        "If you reject, you will receive a full refund for your original booking."
    )

    return {
        "subject": "Your Flight Has Been Cancelled - Rebooking Offer Inside",
        "html": f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:700px;margin:20px auto;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
            <div style="background:linear-gradient(135deg,#fff7ed,#fff1f2);padding:24px 28px;border-bottom:1px solid #f1f5f9;">
                <div style="display:inline-flex;align-items:center;gap:8px;background:#fff7e8;color:#b45309;border:1px solid #f4d6a6;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#d97706;"></span>
                    Action Needed
                </div>
                <h2 style="margin:16px 0 0;font-size:30px;line-height:1.2;color:#1d1d1f;">Your Flight Has Been Cancelled</h2>
                <p style="margin:10px 0 0;font-size:14px;color:#4b5563;">{group_intro}</p>
            </div>
            <div style="padding:24px 28px;">
                <h3 style="color:#dc2626;margin-top:0;">Cancelled Flight</h3>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                    <tr><td style="padding:10px 12px;color:#6b7280;">Flight Number</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{orig_flight}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Booking ID</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{booking_id}</td></tr>
                    {group_row_html}
                </table>
                <h3 style="color:#1d4ed8;">Proposed Alternative Flight</h3>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                    <tr><td style="padding:10px 12px;color:#6b7280;">Flight Number</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{new_flight}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Date</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{new_date}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Departure Time</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{new_dep_time}</td></tr>
                    {group_seat_row_html}
                    <tr><td style="padding:10px 12px;color:#6b7280;">Fare Difference</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#059669;">None - covered by airline</td></tr>
                </table>
                <p style="margin-bottom:16px;color:#374151;">Please respond to this offer within 24 hours:</p>
                <div style="text-align:center;margin:20px 0;">
                    <a href="{accept_link}" style="display:inline-block;background:linear-gradient(135deg,#d48710 0%,#b76b00 100%);color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:999px;font-weight:700;margin-right:12px;">Accept Rebooking</a>
                    <a href="{reject_link}" style="display:inline-block;background:linear-gradient(135deg,#ef4444 0%,#f43f5e 100%);color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:999px;font-weight:700;">Reject and Refund</a>
                </div>
                <p style="margin:0;color:#6b7280;font-size:12px;line-height:1.6;">{group_refund_note}</p>
                <p style="margin:16px 0 0;color:#6b7280;font-size:12px;line-height:1.6;">If the buttons do not open correctly, use this review link: <a href="{review_link}" style="color:#b45309;">View your rebooking offer</a></p>
            </div>
        </div>
        """,
        "text": (
            f"Your flight {orig_flight} has been cancelled. "
            + (f"Group booking: {group_size} passengers. " if is_group else "")
            + f"Alternative: {new_flight} on {new_date} at {new_dep_time} at no extra charge. "
            + (f"Seats will be kept together. " if is_group else f"Seat: {seat_number}. ")
            + f"Review your offer: {review_link}. "
            + f"Accept: {accept_link}. Reject: {reject_link}"
        ),
    }


def flight_cancelled_noalt_template(data: dict) -> dict:
    """
    Scenario 2 Path B: Flight cancelled, no alternative found.
    RabbitMQ routing key: flight.cancelled.noalt
    Payload structure: { "type": "...", "email": "...", "data": { ... } }
    """
    inner           = data.get("data", data)
    orig_flight     = inner.get("OriginalFlight", "N/A")
    cancelled_dt    = inner.get("CancelledDate", "N/A")
    refund_amt      = inner.get("RefundAmount", 0)
    coupon_code     = inner.get("CouponCode", "N/A")
    discount        = inner.get("DiscountAmount", 0)
    booking_id      = inner.get("BookingID", "N/A")
    passenger_name  = inner.get("PassengerName", "Valued Passenger")
    passenger_names = inner.get("PassengerNames") or [passenger_name]
    is_group        = len(passenger_names) > 1

    if is_group:
        names_list_html = "".join(
            f'<li style="margin:2px 0;color:#111827;">{name}</li>'
            for name in passenger_names
        )
        passengers_block_html = (
            f'<tr><td style="padding:10px 12px;color:#6b7280;vertical-align:top;">Passengers</td>'
            f'<td style="padding:10px 12px;text-align:right;font-weight:700;">'
            f'<ul style="margin:0;padding:0;list-style:none;">{names_list_html}</ul>'
            f'</td></tr>'
        )
        intro_text = (
            f"Dear {passenger_name}, we sincerely apologise. Your group booking of "
            f"{len(passenger_names)} passengers has been affected. No alternative flight is "
            "available and a full refund has been issued for all passengers."
        )
        refund_note = "The refund covers all passengers in your group. Allow 5 to 7 business days."
    else:
        passengers_block_html = ""
        intro_text = f"Dear {passenger_name}, we sincerely apologise. No alternative flight is available and a full refund has been issued."
        refund_note = "Allow 5 to 7 business days."

    return {
        "subject": "Your Flight Has Been Cancelled - Full Refund Issued",
        "html": f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:700px;margin:20px auto;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
            <div style="background:#dc2626;padding:24px 28px;color:#ffffff;">
                <h2 style="margin:0;font-size:28px;line-height:1.2;">Your Flight Has Been Cancelled</h2>
                <p style="margin:10px 0 0;font-size:14px;opacity:0.95;">{intro_text}</p>
            </div>
            <div style="padding:24px 28px;">
                <h3 style="color:#dc2626;margin-top:0;">Cancelled Flight</h3>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                    <tr><td style="padding:10px 12px;color:#6b7280;">Flight Number</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{orig_flight}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Booking ID</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{booking_id}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Date</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{cancelled_dt}</td></tr>
                    {passengers_block_html}
                </table>
                <h3 style="color:#059669;">Refund Confirmation</h3>
                <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:20px;">
                    <tr><td style="padding:10px 12px;color:#6b7280;">Refund Amount</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#059669;">${_format_money(refund_amt)}</td></tr>
                    <tr><td style="padding:10px 12px;color:#6b7280;">Refund Status</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#059669;">Processed - {refund_note}</td></tr>
                </table>
                <p style="margin-top:18px;color:#4b5563;font-size:13px;">We apologise for the inconvenience and hope to see you on board again soon.</p>
            </div>
        </div>
        """,
        "text": (
            f"Your flight {orig_flight} on {cancelled_dt} has been cancelled. "
            f"No alternative flight is available. "
            f"Full refund of ${_format_money(refund_amt)} issued. {refund_note} "
            "We apologise for the inconvenience."
        ),
    }


def flight_cancelled_alt_template_v2(data: dict) -> dict:
    inner          = data.get("data", data)
    orig_flight    = inner.get("OriginalFlight", "N/A")
    orig_origin    = inner.get("OriginalOrigin", "Origin")
    orig_dest      = inner.get("OriginalDestination", "Destination")
    orig_date      = inner.get("OriginalDate", "N/A")
    orig_dep_time  = inner.get("OriginalDepartureTime", "N/A")
    new_flight     = inner.get("NewFlight", "N/A")
    new_origin     = inner.get("NewOrigin", "Origin")
    new_dest       = inner.get("NewDestination", "Destination")
    new_date       = inner.get("NewDate", "N/A")
    new_dep_time   = inner.get("NewDepartureTime", "N/A")
    assigned_seats = inner.get("AssignedSeatNumbers") or []
    seat_number    = inner.get("SeatNumber", "N/A")
    review_link    = inner.get("AcceptRejectLink", "#")
    accept_link    = inner.get("AcceptLink", review_link)
    reject_link    = inner.get("RejectLink", review_link)
    booking_id     = inner.get("BookingID", "N/A")
    passenger_name = inner.get("PassengerName", "Valued Passenger")
    group_size     = int(inner.get("GroupSize") or 1)
    seat_summary   = ", ".join(str(seat).strip() for seat in assigned_seats if str(seat).strip()) or seat_number
    is_group       = group_size > 1

    group_intro = (
        f"Dear {passenger_name}, your group booking of {group_size} passengers has been affected. "
        "We have found an alternative flight that accommodates your entire group at no extra charge."
    ) if is_group else (
        f"Dear {passenger_name}, we have found an alternative flight for you at no extra charge."
    )

    return {
        "subject": "Your Flight Has Been Cancelled - Rebooking Offer Inside",
        "html": f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f8fafc;padding:24px 12px;">
            <div style="max-width:760px;margin:0 auto;border:1px solid #e8edf4;border-radius:24px;overflow:hidden;background:#ffffff;box-shadow:0 18px 45px rgba(15,23,42,0.08);">
                <div style="background:radial-gradient(circle at top right,rgba(230,57,70,0.10),transparent 28%),linear-gradient(135deg,#fffdfb 0%,#ffffff 58%,#fff7f5 100%);padding:30px 32px 26px;border-bottom:1px solid #edf2f7;">
                    <div style="font-size:12px;font-weight:800;letter-spacing:0.18em;text-transform:uppercase;color:#ef4444;">Blaze Air Flight Change Notice</div>
                    <div style="display:inline-flex;align-items:center;background:#fff7e8;color:#b45309;border:1px solid #f4d6a6;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-top:14px;">Action Needed</div>
                    <h2 style="margin:16px 0 0;font-size:42px;line-height:1.08;color:#202124;">Your Flight Has Been Cancelled</h2>
                    <p style="margin:14px 0 0;font-size:15px;line-height:1.75;color:#4b5563;max-width:640px;">{group_intro} We have found a replacement flight at no extra charge and included the full summary below so the traveller can review the change quickly.</p>
                </div>

                <div style="padding:28px 32px 32px;">
                    <div style="margin-bottom:24px;padding:18px 20px;border:1px solid #e9eef5;border-radius:18px;background:#ffffff;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr><td style="padding:0 0 10px;color:#6b7280;font-size:13px;">Lead passenger</td><td style="padding:0 0 10px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{passenger_name}</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Booking ID</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">#{booking_id}</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Passengers</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">{group_size}</td></tr>
                            <tr><td style="padding:10px 0 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Fare difference</td><td style="padding:10px 0 0;text-align:right;color:#059669;font-size:28px;font-weight:800;border-top:1px solid #eef2f7;">Covered by airline</td></tr>
                        </table>
                    </div>

                    <h3 style="color:#ef4444;margin:0 0 12px;font-size:20px;line-height:1.2;">Itinerary Change</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
                        <div style="border:1px solid #f6cfd3;border-radius:18px;overflow:hidden;background:#ffffff;">
                            <div style="padding:14px 18px 0;">
                                <div style="font-size:11px;font-weight:800;letter-spacing:0.15em;text-transform:uppercase;color:#ef4444;">Cancelled Flight</div>
                            </div>
                            <div style="padding:12px 18px 16px;">
                                <div style="font-size:17px;font-weight:700;color:#202124;">{orig_origin} &rarr; {orig_dest}</div>
                                <div style="margin-top:6px;font-size:13px;color:#6b7280;">Flight {orig_flight} &nbsp;&middot;&nbsp; {orig_date}</div>
                            </div>
                            <table style="width:100%;border-collapse:collapse;border-top:1px solid #eef2f7;">
                                <tr><td style="padding:12px 18px;color:#6b7280;font-size:13px;">Departure</td><td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{orig_dep_time}</td></tr>
                            </table>
                        </div>

                        <div style="border:1px solid #f6d59a;border-radius:18px;overflow:hidden;background:#ffffff;">
                            <div style="padding:14px 18px 0;">
                                <div style="font-size:11px;font-weight:800;letter-spacing:0.15em;text-transform:uppercase;color:#b76b00;">Replacement Flight</div>
                            </div>
                            <div style="padding:12px 18px 16px;">
                                <div style="font-size:17px;font-weight:700;color:#202124;">{new_origin} &rarr; {new_dest}</div>
                                <div style="margin-top:6px;font-size:13px;color:#6b7280;">Flight {new_flight} &nbsp;&middot;&nbsp; {new_date}</div>
                            </div>
                            <table style="width:100%;border-collapse:collapse;border-top:1px solid #eef2f7;">
                                <tr><td style="padding:12px 18px;color:#6b7280;font-size:13px;">Departure</td><td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{new_dep_time}</td></tr>
                                <tr><td style="padding:12px 18px;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Held seat(s)</td><td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">{seat_summary}</td></tr>
                            </table>
                        </div>
                    </div>

                    <div style="margin-bottom:18px;padding:18px 20px;border:1px solid #e9eef5;border-radius:18px;background:#ffffff;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr><td style="padding:0 0 10px;color:#6b7280;font-size:13px;">Response window</td><td style="padding:0 0 10px;text-align:right;color:#111827;font-size:13px;font-weight:700;">Within 24 hours</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">If you accept</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">We confirm the new flight and keep your trip active</td></tr>
                            <tr><td style="padding:10px 0 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">If you reject</td><td style="padding:10px 0 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">Full refund to your original payment method</td></tr>
                        </table>
                    </div>

                    <div style="text-align:center;margin:22px 0 18px;">
                        <a href="{accept_link}" style="display:inline-block;background:linear-gradient(135deg,#d48710 0%,#b76b00 100%);color:#ffffff;text-decoration:none;padding:13px 28px;border-radius:999px;font-weight:700;margin-right:12px;">Accept Rebooking</a>
                        <a href="{reject_link}" style="display:inline-block;background:linear-gradient(135deg,#ef4444 0%,#f43f5e 100%);color:#ffffff;text-decoration:none;padding:13px 28px;border-radius:999px;font-weight:700;">Reject and Refund</a>
                    </div>

                    <div style="margin-top:16px;padding:16px 18px;border:1px solid #f7d7dc;border-radius:16px;background:#fffdfd;color:#6b7280;font-size:13px;line-height:1.7;">
                        If the buttons do not open correctly, review the offer here:
                        <a href="{review_link}" style="color:#b45309;text-decoration:none;font-weight:700;">View your rebooking offer</a>
                    </div>
                </div>
            </div>
        </div>
        """,
        "text": (
            f"Your flight {orig_flight} from {orig_origin} to {orig_dest} on {orig_date} at {orig_dep_time} has been cancelled. "
            + (f"Group booking: {group_size} passengers. " if is_group else "")
            + f"Replacement: {new_flight} from {new_origin} to {new_dest} on {new_date} at {new_dep_time} at no extra charge. "
            + f"Held seats: {seat_summary}. Review your offer: {review_link}. "
            + f"Accept: {accept_link}. Reject: {reject_link}"
        ),
    }


def flight_cancelled_noalt_template_v2(data: dict) -> dict:
    inner           = data.get("data", data)
    orig_flight     = inner.get("OriginalFlight", "N/A")
    orig_origin     = inner.get("OriginalOrigin", "Origin")
    orig_dest       = inner.get("OriginalDestination", "Destination")
    orig_dep_time   = inner.get("OriginalDepartureTime", "N/A")
    cancelled_dt    = inner.get("CancelledDate", "N/A")
    refund_amt      = inner.get("RefundAmount", 0)
    refund_id       = inner.get("RefundID", "Pending")
    refund_status   = inner.get("RefundStatus", "Refunded")
    booking_id      = inner.get("BookingID", "N/A")
    passenger_name  = inner.get("PassengerName", "Valued Passenger")
    passenger_names = inner.get("PassengerNames") or [passenger_name]
    group_size      = int(inner.get("GroupSize") or len(passenger_names) or 1)

    intro_text = (
        f"Dear {passenger_name}, your group booking of {group_size} passengers has been affected. "
        "No alternative flight is available and a full refund has been issued for the booking."
    ) if group_size > 1 else (
        f"Dear {passenger_name}, no alternative flight is available and a full refund has been issued."
    )
    refund_note = "Allow 5 to 7 business days."

    return {
        "subject": "Your Flight Has Been Cancelled - Full Refund Issued",
        "html": f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f8fafc;padding:24px 12px;">
            <div style="max-width:760px;margin:0 auto;border:1px solid #e8edf4;border-radius:24px;overflow:hidden;background:#ffffff;box-shadow:0 18px 45px rgba(15,23,42,0.08);">
                <div style="background:radial-gradient(circle at top right,rgba(230,57,70,0.10),transparent 28%),linear-gradient(135deg,#fffdfb 0%,#ffffff 58%,#fff7f5 100%);padding:30px 32px 26px;border-bottom:1px solid #edf2f7;">
                    <div style="font-size:12px;font-weight:800;letter-spacing:0.18em;text-transform:uppercase;color:#ef4444;">Blaze Air Flight Change Notice</div>
                    <div style="display:inline-flex;align-items:center;background:#fff1f2;color:#dc2626;border:1px solid #fecdd3;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-top:14px;">Refund Issued</div>
                    <h2 style="margin:16px 0 0;font-size:42px;line-height:1.08;color:#202124;">Your Flight Has Been Cancelled</h2>
                    <p style="margin:14px 0 0;font-size:15px;line-height:1.75;color:#4b5563;max-width:640px;">{intro_text} We have included the affected itinerary and refund breakdown below so the traveller has everything in one place.</p>
                </div>

                <div style="padding:28px 32px 32px;">
                    <div style="margin-bottom:24px;padding:18px 20px;border:1px solid #e9eef5;border-radius:18px;background:#ffffff;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr><td style="padding:0 0 10px;color:#6b7280;font-size:13px;">Lead passenger</td><td style="padding:0 0 10px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{passenger_name}</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Passengers</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">{group_size}</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Booking ID</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">#{booking_id}</td></tr>
                            <tr><td style="padding:10px 0 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Refund amount</td><td style="padding:10px 0 0;text-align:right;color:#ef4444;font-size:28px;font-weight:800;border-top:1px solid #eef2f7;">${_format_money(refund_amt)}</td></tr>
                        </table>
                    </div>

                    <h3 style="color:#ef4444;margin:0 0 12px;font-size:20px;line-height:1.2;">Cancelled Itinerary</h3>
                    <div style="border:1px solid #f6cfd3;border-radius:18px;overflow:hidden;background:#ffffff;margin-bottom:20px;">
                        <div style="padding:14px 18px 0;">
                            <div style="font-size:11px;font-weight:800;letter-spacing:0.15em;text-transform:uppercase;color:#ef4444;">Cancelled Flight</div>
                        </div>
                        <div style="padding:12px 18px 16px;">
                            <div style="font-size:17px;font-weight:700;color:#202124;">{orig_origin} &rarr; {orig_dest}</div>
                            <div style="margin-top:6px;font-size:13px;color:#6b7280;">Flight {orig_flight} &nbsp;&middot;&nbsp; {cancelled_dt}</div>
                        </div>
                        <table style="width:100%;border-collapse:collapse;border-top:1px solid #eef2f7;">
                            <tr><td style="padding:12px 18px;color:#6b7280;font-size:13px;">Departure</td><td style="padding:12px 18px;text-align:right;color:#111827;font-size:13px;font-weight:700;">{orig_dep_time}</td></tr>
                        </table>
                    </div>

                    <h3 style="color:#ef4444;margin:0 0 12px;font-size:20px;line-height:1.2;">Passenger Details</h3>
                    <div style="margin-bottom:20px;padding:18px 20px;border:1px solid #e9eef5;border-radius:18px;background:#ffffff;color:#111827;font-size:13px;font-weight:700;">
                        {", ".join(passenger_names)}
                    </div>

                    <h3 style="color:#059669;margin:0 0 12px;font-size:20px;line-height:1.2;">Refund Summary</h3>
                    <div style="margin-bottom:18px;padding:18px 20px;border:1px solid #e9eef5;border-radius:18px;background:#ffffff;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr><td style="padding:0 0 10px;color:#6b7280;font-size:13px;">Refund status</td><td style="padding:0 0 10px;text-align:right;color:#059669;font-size:13px;font-weight:700;">{refund_status}</td></tr>
                            <tr><td style="padding:10px 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Refund reference</td><td style="padding:10px 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">{refund_id}</td></tr>
                            <tr><td style="padding:10px 0 0;color:#6b7280;font-size:13px;border-top:1px solid #eef2f7;">Processing note</td><td style="padding:10px 0 0;text-align:right;color:#111827;font-size:13px;font-weight:700;border-top:1px solid #eef2f7;">{refund_note}</td></tr>
                        </table>
                    </div>

                    <div style="margin-top:16px;padding:16px 18px;border:1px solid #f7d7dc;border-radius:16px;background:#fffdfd;color:#6b7280;font-size:13px;line-height:1.7;">
                        We apologise for the inconvenience. The refund has been sent back to the original payment method and the booking has now been closed.
                    </div>
                </div>
            </div>
        </div>
        """,
        "text": (
            f"Your flight {orig_flight} from {orig_origin} to {orig_dest} on {cancelled_dt} at {orig_dep_time} has been cancelled. "
            f"No alternative flight is available. Full refund of ${_format_money(refund_amt)} issued. "
            f"Refund reference: {refund_id}. {refund_note}"
        ),
    }


flight_cancelled_alt_template = flight_cancelled_alt_template_v2
flight_cancelled_noalt_template = flight_cancelled_noalt_template_v2

# =============================================================================
# EMAIL TEMPLATE — Scenario 3 (Voucher Conversion)
# =============================================================================

def voucher_confirmation_template(data: dict) -> dict:
    voucher_type = data.get("voucherType", "VOUCHER")
    voucher_code = data.get("voucherCode", "N/A")
    voucher_value = data.get("voucherValue", "N/A")
    expiry_date = data.get("expiryDate", "N/A")
    miles_redeemed = data.get("milesRedeemed", "N/A")
    remaining_miles = data.get("remainingMiles", "N/A")
    provider_name = data.get("providerName") or "-"
    redemption_url = data.get("redemptionUrl") or ""
    external_order_id = data.get("externalOrderId") or "-"
    passenger_name = _display_name(data)

    subject = f"Voucher Created: {voucher_type}"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:700px;margin:20px auto;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
        <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:24px 28px;color:#ffffff;">
            <h2 style="margin:0;font-size:28px;line-height:1.2;">Your Voucher is Ready</h2>
            <p style="margin:10px 0 0;font-size:14px;opacity:0.95;">Hi {passenger_name}, your miles-to-voucher conversion was successful.</p>
        </div>
        <div style="padding:24px 28px;">
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
                <tr><td style="padding:10px 12px;color:#6b7280;">Voucher Type</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{voucher_type}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Voucher Code</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{voucher_code}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Voucher Value</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{voucher_value}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Miles Redeemed</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{miles_redeemed}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Remaining Miles</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{remaining_miles}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Expiry Date</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{expiry_date}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">Provider</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{provider_name}</td></tr>
                <tr><td style="padding:10px 12px;color:#6b7280;">External Order ID</td><td style="padding:10px 12px;text-align:right;font-weight:700;color:#111827;">{external_order_id}</td></tr>
            </table>
            {f'<p style="margin:14px 0 0;"><a href="{redemption_url}" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:8px;font-weight:700;">Redeem Voucher</a></p>' if redemption_url else ''}
            <p style="margin:18px 0 0;color:#4b5563;font-size:13px;">Keep your voucher code safe and apply it during checkout.</p>
        </div>
    </div>
    """
    text = (
        f"Voucher conversion successful. Type: {voucher_type}. "
        f"Code: {voucher_code}. Value: {voucher_value}. "
        f"Miles Redeemed: {miles_redeemed}. Remaining Miles: {remaining_miles}. "
        f"Expiry: {expiry_date}. Provider: {provider_name}. "
        + (f"Redeem here: {redemption_url}." if redemption_url else "")
    )

    return {"subject": subject, "html": html, "text": text}


def voucher_bundle_confirmation_template(data: dict) -> dict:
    vouchers = data.get("vouchers") or []
    passenger_name = _display_name(data)
    total_redeemed = data.get("totalMilesRedeemed", "N/A")
    remaining_miles = data.get("remainingMiles", "N/A")

    rows = []
    text_rows = []
    for index, voucher in enumerate(vouchers, start=1):
        voucher_type = voucher.get("voucherType") or voucher.get("type") or "VOUCHER"
        voucher_code = voucher.get("voucherCode") or voucher.get("code") or "N/A"
        voucher_value = voucher.get("voucherValue", "N/A")
        expiry_date = voucher.get("expiryDate", "N/A")
        miles_redeemed = voucher.get("milesRedeemed", "N/A")
        provider_name = voucher.get("providerName") or "-"
        redemption_url = voucher.get("redemptionUrl") or "-"

        rows.append(
            f"<tr>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{index}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{voucher_type}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{voucher_code}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{voucher_value}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{miles_redeemed}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{expiry_date}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{provider_name}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e5e7eb;color:#111827;'>{redemption_url}</td>"
            f"</tr>"
        )
        text_rows.append(
            f"{index}) {voucher_type} | Code: {voucher_code} | Value: {voucher_value} | Miles: {miles_redeemed} | Expiry: {expiry_date} | Provider: {provider_name} | Link: {redemption_url}"
        )

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;max-width:760px;margin:20px auto;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;">
        <div style="background:linear-gradient(135deg,#0f766e,#0d9488);padding:24px 28px;color:#ffffff;">
            <h2 style="margin:0;font-size:28px;line-height:1.2;">Your Voucher Bundle is Ready</h2>
            <p style="margin:10px 0 0;font-size:14px;opacity:0.95;">Hi {passenger_name}, your bundle conversion completed successfully.</p>
        </div>
        <div style="padding:24px 28px;">
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
                <thead>
                    <tr style="background:#f3f4f6;">
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">#</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Type</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Code</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Value</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Miles</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Expiry</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Provider</th>
                        <th style="text-align:left;padding:10px 12px;font-size:12px;color:#6b7280;">Redemption</th>
                    </tr>
                </thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
                <tr><td style="padding:8px 0;color:#6b7280;">Total Miles Redeemed</td><td style="padding:8px 0;text-align:right;font-weight:700;color:#111827;">{total_redeemed}</td></tr>
                <tr><td style="padding:8px 0;color:#6b7280;">Remaining Miles</td><td style="padding:8px 0;text-align:right;font-weight:700;color:#111827;">{remaining_miles}</td></tr>
            </table>
        </div>
    </div>
    """

    text = (
        "Voucher bundle conversion successful. "
        + " ".join(text_rows)
        + f" Total Miles Redeemed: {total_redeemed}. Remaining Miles: {remaining_miles}."
    )

    return {"subject": f"Voucher Bundle Created ({len(vouchers)})", "html": html, "text": text}


# =============================================================================
# PDF GENERATOR — Scenario 2 Path A: Rebooking offer (boarding-pass style)
# =============================================================================

def generate_rebooking_offer_pdf(data: dict) -> bytes:
    """Scenario 2 Path A — boarding-pass style rebooking offer PDF."""
    inner = data.get("data", data)

    PAGE_W  = 17 * cm
    INNER_W = 16 * cm
    COL_L   = 5.5 * cm
    COL_R   = PAGE_W - COL_L

    AMBER   = colors.HexColor("#b45309")
    NAVY    = colors.HexColor("#1e3356")
    NAVY2   = colors.HexColor("#162a47")
    WHITE   = colors.white
    LGRAY   = colors.HexColor("#94a3b8")
    BORDER  = colors.HexColor("#e2e8f0")

    ps = _make_styles()

    s_brand  = ps("rb_brand",  fontSize=13, fontName="Helvetica-Bold", textColor=WHITE)
    s_h1     = ps("rb_h1",     fontSize=17, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_sub    = ps("rb_sub",    fontSize=10, textColor=colors.HexColor("#fde68a"), alignment=1)
    s_fn     = ps("rb_fn",     fontSize=18, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_lbl_w  = ps("rb_lbl_w",  fontSize=9,  textColor=LGRAY, alignment=1)
    s_val_w  = ps("rb_val_w",  fontSize=11, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_sec_r  = ps("rb_sec_r",  fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#dc2626"), spaceBefore=12, spaceAfter=4)
    s_lbl    = ps("rb_lbl",    fontSize=10, textColor=colors.HexColor("#6b7280"))
    s_val    = ps("rb_val",    fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"), alignment=2)
    s_link   = ps("rb_link",   fontSize=10, textColor=colors.HexColor("#1d4ed8"), alignment=1, spaceBefore=6)
    s_foot   = ps("rb_foot",   fontSize=9,  textColor=colors.HexColor("#9ca3af"), alignment=1)

    orig_flight    = str(inner.get("OriginalFlight", "N/A"))
    new_flight     = str(inner.get("NewFlight", "N/A"))
    new_date       = str(inner.get("NewDate", "N/A"))
    new_dep_time   = str(inner.get("NewDepartureTime", "N/A"))
    seat_number    = str(inner.get("SeatNumber", "N/A"))
    coupon_code    = str(inner.get("CouponCode", "N/A"))
    discount       = inner.get("DiscountAmount", 0)
    accept_link    = str(inner.get("AcceptRejectLink", "N/A"))
    booking_id     = str(inner.get("BookingID", "N/A"))
    passenger_name = str(inner.get("PassengerName", "Valued Passenger"))
    group_size     = int(inner.get("GroupSize") or 1)
    is_group       = group_size > 1
    THIRD          = INNER_W / 3

    story = []

    # Amber warning header
    header_t = Table(
        [
            [Paragraph("BlazeAir", s_brand)],
            [Paragraph("Your Flight Has Been Cancelled", s_h1)],
            [Paragraph("An alternative flight has been arranged for you at no extra charge.", s_sub)],
        ],
        colWidths=[PAGE_W],
    )
    header_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AMBER),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0.5 * cm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0.5 * cm),
        ("TOPPADDING",    (0, 0), (0, 0), 0.4 * cm),
        ("BOTTOMPADDING", (0, -1), (0, -1), 0.4 * cm),
        ("TOPPADDING",    (0, 1), (0, -1), 0.15 * cm),
        ("BOTTOMPADDING", (0, 0), (0, -2), 0.15 * cm),
    ]))
    story.append(header_t)

    # Cancelled flight details
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Cancelled Flight", s_sec_r))
    cancelled_rows = [
        [Paragraph("Passenger Name", s_lbl), Paragraph(passenger_name, s_val)],
        [Paragraph("Flight Number",  s_lbl), Paragraph(orig_flight,    s_val)],
        [Paragraph("Booking ID",     s_lbl), Paragraph(booking_id,     s_val)],
    ]
    if is_group:
        cancelled_rows.append([Paragraph("Passengers in Group", s_lbl), Paragraph(str(group_size), s_val)])
    story.append(_detail_row_table(cancelled_rows, COL_L, COL_R))

    # Alternative flight (navy boarding-pass block)
    seat_label = "Seats (kept together)" if is_group else "Seat"
    seat_value = f"{group_size} seats" if is_group else seat_number
    details_sub = Table(
        [
            [Paragraph("Date",    s_lbl_w), Paragraph("Dep. Time",   s_lbl_w), Paragraph(seat_label, s_lbl_w)],
            [Paragraph(new_date,  s_val_w), Paragraph(new_dep_time,  s_val_w), Paragraph(seat_value, s_val_w)],
        ],
        colWidths=[THIRD, THIRD, THIRD],
    )
    details_sub.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY2),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LINEABOVE",     (0, 0), (-1, 0), 0.5, LGRAY),
    ]))

    alt_t = Table(
        [
            [Paragraph("Proposed Alternative Flight", ps("rb_alt_h", fontSize=13, fontName="Helvetica-Bold", textColor=WHITE, alignment=1))],
            [Paragraph(new_flight, s_fn)],
            [details_sub],
        ],
        colWidths=[PAGE_W],
    )
    alt_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0.5 * cm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0.5 * cm),
        ("TOPPADDING",    (0, 0), (0, 0), 0.4 * cm),
        ("TOPPADDING",    (0, 1), (0, -2), 0.15 * cm),
        ("BOTTOMPADDING", (0, 0), (0, 0), 0.15 * cm),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0.25 * cm),
        ("BOTTOMPADDING", (0, -1), (0, -1), 0),
    ]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(alt_t)

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Please respond to this offer within 24 hours.", s_lbl))
    story.append(Paragraph(f"Accept or reject at: {accept_link}", s_link))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width=PAGE_W, thickness=0.5, color=BORDER))
    refund_note = (
        "If you reject, a full refund will be issued for all passengers in your group."
        if is_group else
        "If you reject, a full refund will be issued to your original payment method."
    )
    story.append(Paragraph(refund_note, s_foot))

    return _pdf_build(story)


# =============================================================================
# PDF GENERATOR — Scenario 2 Path B: Refund confirmation (boarding-pass style)
# =============================================================================

def generate_refund_noalt_pdf(data: dict) -> bytes:
    """Scenario 2 Path B — boarding-pass style refund confirmation PDF."""
    inner = data.get("data", data)

    PAGE_W = 17 * cm
    COL_L  = 5.5 * cm
    COL_R  = PAGE_W - COL_L

    RED    = colors.HexColor("#dc2626")
    WHITE  = colors.white
    BORDER = colors.HexColor("#e2e8f0")

    ps = _make_styles()

    s_brand  = ps("rn_brand",  fontSize=13, fontName="Helvetica-Bold", textColor=WHITE)
    s_h1     = ps("rn_h1",     fontSize=17, fontName="Helvetica-Bold", textColor=WHITE, alignment=1)
    s_sub    = ps("rn_sub",    fontSize=10, textColor=colors.HexColor("#fca5a5"), alignment=1)
    s_sec_r  = ps("rn_sec_r",  fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#dc2626"), spaceBefore=12, spaceAfter=4)
    s_sec_g  = ps("rn_sec_g",  fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#059669"), spaceBefore=12, spaceAfter=4)
    s_lbl    = ps("rn_lbl",    fontSize=10, textColor=colors.HexColor("#6b7280"))
    s_val    = ps("rn_val",    fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"), alignment=2)
    s_refund = ps("rn_refund", fontSize=11, fontName="Helvetica-Bold", textColor=colors.HexColor("#059669"), alignment=2)
    s_foot   = ps("rn_foot",   fontSize=9,  textColor=colors.HexColor("#9ca3af"), alignment=1)

    orig_flight    = str(inner.get("OriginalFlight", "N/A"))
    cancelled_dt   = str(inner.get("CancelledDate", "N/A"))
    refund_amt     = inner.get("RefundAmount", 0)
    coupon_code    = str(inner.get("CouponCode", "N/A"))
    discount       = inner.get("DiscountAmount", 0)
    booking_id     = str(inner.get("BookingID", "N/A"))
    passenger_name = str(inner.get("PassengerName", "Valued Passenger"))

    story = []

    # Red cancellation header
    header_t = Table(
        [
            [Paragraph("BlazeAir", s_brand)],
            [Paragraph("Your Flight Has Been Cancelled", s_h1)],
            [Paragraph("No alternative flight is available. A full refund has been issued.", s_sub)],
        ],
        colWidths=[PAGE_W],
    )
    header_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RED),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0.5 * cm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0.5 * cm),
        ("TOPPADDING",    (0, 0), (0, 0), 0.4 * cm),
        ("BOTTOMPADDING", (0, -1), (0, -1), 0.4 * cm),
        ("TOPPADDING",    (0, 1), (0, -1), 0.15 * cm),
        ("BOTTOMPADDING", (0, 0), (0, -2), 0.15 * cm),
    ]))
    story.append(header_t)

    # Cancelled flight
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Cancelled Flight", s_sec_r))
    story.append(_detail_row_table(
        [
            [Paragraph("Passenger Name", s_lbl), Paragraph(passenger_name, s_val)],
            [Paragraph("Flight Number",  s_lbl), Paragraph(orig_flight,    s_val)],
            [Paragraph("Booking ID",     s_lbl), Paragraph(booking_id,     s_val)],
            [Paragraph("Date",           s_lbl), Paragraph(cancelled_dt,   s_val)],
        ],
        COL_L, COL_R,
    ))

    # Refund details
    story.append(Paragraph("Refund Details", s_sec_g))
    story.append(_detail_row_table(
        [
            [Paragraph("Refund Amount", s_lbl), Paragraph(f"SGD ${_format_money(refund_amt)}", s_refund)],
            [Paragraph("Refund Status", s_lbl), Paragraph("Processed — allow 5 to 7 business days", s_val)],
        ],
        COL_L, COL_R,
    ))

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width=PAGE_W, thickness=0.5, color=BORDER))
    story.append(Paragraph("We apologise for the inconvenience and hope to see you on board again soon.", s_foot))

    return _pdf_build(story)


# =============================================================================
# PDF GENERATOR — Scenario 3: Voucher PDFs (unchanged)
# =============================================================================

def _pdf_table(data_rows: list, col_widths=None) -> Table:
    """Helper — builds a styled two-column label/value table."""
    col_widths = col_widths or [5*cm, 11*cm]
    base = getSampleStyleSheet()
    s_lbl = ParagraphStyle("pt_lbl", parent=base["Normal"], fontSize=10,
                           textColor=colors.HexColor("#6b7280"))
    s_val = ParagraphStyle("pt_val", parent=base["Normal"], fontSize=10,
                           fontName="Helvetica-Bold", textColor=colors.HexColor("#111827"))
    wrapped = []
    for row in data_rows:
        if len(row) == 2:
            wrapped.append([Paragraph(str(row[0]), s_lbl), Paragraph(str(row[1]), s_val)])
        else:
            wrapped.append(row)
    t = Table(wrapped, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _pdf_styles() -> dict:
    """Returns a dict of common paragraph styles."""
    base = getSampleStyleSheet()
    return {
        "header": ParagraphStyle("header", parent=base["Normal"], fontSize=20, fontName="Helvetica-Bold", textColor=colors.HexColor("#1d4ed8"), spaceAfter=4),
        "sub":    ParagraphStyle("sub",    parent=base["Normal"], fontSize=11, textColor=colors.HexColor("#6b7280"), spaceAfter=2),
        "section":ParagraphStyle("section",parent=base["Normal"], fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#1d4ed8"), spaceBefore=14, spaceAfter=6),
        "footer": ParagraphStyle("footer", parent=base["Normal"], fontSize=9,  textColor=colors.HexColor("#9ca3af")),
        "warn":   ParagraphStyle("warn",   parent=base["Normal"], fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#dc2626"), spaceBefore=14, spaceAfter=6),
        "success":ParagraphStyle("success",parent=base["Normal"], fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#059669"), spaceBefore=14, spaceAfter=6),
        "teal":   ParagraphStyle("teal",   parent=base["Normal"], fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f766e"), spaceBefore=14, spaceAfter=6),
    }


def generate_voucher_pdf(data: dict) -> bytes:
    """Scenario 3 — single voucher confirmation PDF."""
    s     = _pdf_styles()
    story = []

    story.append(Paragraph("Voucher Confirmation", s["header"]))
    story.append(Paragraph(f"Hi {_display_name(data)}, your miles-to-voucher conversion was successful.", s["sub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))

    story.append(Paragraph("Voucher Details", s["teal"]))
    story.append(_pdf_table([
        ["Voucher Type",     str(data.get("voucherType", "N/A"))],
        ["Voucher Code",     str(data.get("voucherCode", "N/A"))],
        ["Voucher Value",    str(data.get("voucherValue", "N/A"))],
        ["Miles Redeemed",   str(data.get("milesRedeemed", "N/A"))],
        ["Remaining Miles",  str(data.get("remainingMiles", "N/A"))],
        ["Expiry Date",      str(data.get("expiryDate", "N/A"))],
        ["Provider",         str(data.get("providerName") or "-")],
        ["External Order ID",str(data.get("externalOrderId") or "-")],
    ]))

    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Keep your voucher code safe and apply it during checkout.", s["footer"]))

    return _pdf_build(story)


def generate_voucher_bundle_pdf(data: dict) -> bytes:
    """Scenario 3 — voucher bundle confirmation PDF."""
    vouchers        = data.get("vouchers") or []
    total_redeemed  = data.get("totalMilesRedeemed", "N/A")
    remaining_miles = data.get("remainingMiles", "N/A")
    s               = _pdf_styles()
    story           = []

    story.append(Paragraph("Voucher Bundle Confirmation", s["header"]))
    story.append(Paragraph(f"Hi {_display_name(data)}, your bundle conversion completed successfully.", s["sub"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))

    story.append(Paragraph("Voucher Details", s["teal"]))

    base     = getSampleStyleSheet()
    s_hdr    = ParagraphStyle("bt_hdr",  parent=base["Normal"], fontSize=9,
                              fontName="Helvetica-Bold", textColor=colors.HexColor("#6b7280"))
    s_cell   = ParagraphStyle("bt_cell", parent=base["Normal"], fontSize=9,
                              textColor=colors.HexColor("#111827"))

    COL_WIDTHS = [0.8*cm, 2.5*cm, 3.5*cm, 2*cm, 2*cm, 2.5*cm, 2.7*cm]  # total = 16cm

    header = [Paragraph(h, s_hdr) for h in ["#", "Type", "Code", "Value", "Miles", "Expiry", "Provider"]]
    rows   = [header]
    for i, v in enumerate(vouchers, start=1):
        rows.append([
            Paragraph(str(i), s_cell),
            Paragraph(str(v.get("voucherType") or v.get("type") or "VOUCHER"), s_cell),
            Paragraph(str(v.get("voucherCode") or v.get("code") or "N/A"), s_cell),
            Paragraph(str(v.get("voucherValue", "N/A")), s_cell),
            Paragraph(str(v.get("milesRedeemed", "N/A")), s_cell),
            Paragraph(str(v.get("expiryDate", "N/A")), s_cell),
            Paragraph(str(v.get("providerName") or "-"), s_cell),
        ])

    bundle_table = Table(rows, colWidths=COL_WIDTHS)
    bundle_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#f3f4f6")),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(bundle_table)

    story.append(Paragraph("Summary", s["section"]))
    story.append(_pdf_table([
        ["Total Miles Redeemed", str(total_redeemed)],
        ["Remaining Miles",      str(remaining_miles)],
    ]))

    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Keep your voucher codes safe and apply them during checkout.", s["footer"]))

    return _pdf_build(story)


def _safe_pdf(generator_fn, data: dict, filename: str):
    """Safely calls a PDF generator — returns (pdf_bytes, filename) or (None, filename) on error."""
    try:
        pdf_bytes = generator_fn(data)
        logger.info("PDF generated: %s (%d bytes)", filename, len(pdf_bytes))
        return pdf_bytes, filename
    except Exception as e:
        logger.error("PDF generation failed for %s: %s", filename, str(e))
        return None, filename

# =============================================================================
# NOTIFICATION HANDLER
# =============================================================================

def notify_booking_confirmation(data: dict) -> dict:
    """Scenario 1 - RabbitMQ: booking.confirmed"""
    tpl = booking_confirmation_template(data)
    try:
        pdf_bytes    = generate_booking_pdf(data)
        booking_id   = data.get("booking_id", "booking")
        pdf_filename = f"booking_{booking_id}_confirmation.pdf"
        logger.info("PDF generated successfully for booking %s", booking_id)
    except Exception as e:
        logger.error("Failed to generate PDF for booking %s: %s", data.get("booking_id"), str(e))
        pdf_bytes    = None
        pdf_filename = "booking_confirmation.pdf"
    return send_email(data["passenger_email"], data["passenger_name"], tpl["subject"], tpl["html"], tpl["text"], pdf_bytes=pdf_bytes, pdf_filename=pdf_filename)

def notify_flight_cancelled_alt(data: dict) -> dict:
    """Scenario 2 Path A - RabbitMQ: flight.cancelled.alt"""
    tpl          = flight_cancelled_alt_template(data)
    email        = data.get("email", "")
    name         = data.get("data", {}).get("PassengerName", "Valued Passenger")
    booking_id   = data.get("data", {}).get("BookingID", "booking")
    pdf_bytes, pdf_filename = _safe_pdf(generate_rebooking_offer_pdf, data, f"rebooking_offer_{booking_id}.pdf")
    return send_email(email, name, tpl["subject"], tpl["html"], tpl["text"], pdf_bytes=pdf_bytes, pdf_filename=pdf_filename)


def notify_flight_cancelled_noalt(data: dict) -> dict:
    """Scenario 2 Path B - RabbitMQ: flight.cancelled.noalt"""
    tpl          = flight_cancelled_noalt_template(data)
    email        = data.get("email", "")
    name         = data.get("data", {}).get("PassengerName", "Valued Passenger")
    booking_id   = data.get("data", {}).get("BookingID", "booking")
    pdf_bytes, pdf_filename = _safe_pdf(generate_refund_noalt_pdf, data, f"refund_confirmation_{booking_id}.pdf")
    return send_email(email, name, tpl["subject"], tpl["html"], tpl["text"], pdf_bytes=pdf_bytes, pdf_filename=pdf_filename)


# =============================================================================
# RABBITMQ CONSUMER
# =============================================================================

RABBITMQ_EXCHANGE = os.environ.get("RABBITMQ_EXCHANGE", "airline_events")
RABBITMQ_QUEUE    = "notification_booking_queue"
RABBITMQ_DLX      = os.environ.get("RABBITMQ_DLX", "airline_events_dlx")
RABBITMQ_DLQ      = os.environ.get("RABBITMQ_DLQ", "notification_booking_dlq")
RABBITMQ_DLQ_KEY  = os.environ.get("RABBITMQ_DLQ_ROUTING_KEY", "notification.failed")
RABBITMQ_BINDINGS = [
    "booking.confirmed",       # Scenario 1
    "flight.cancelled.alt",    # Scenario 2 Path A
    "flight.cancelled.noalt",  # Scenario 2 Path B
]
RABBITMQ_HANDLERS = {
    "booking.confirmed":      notify_booking_confirmation,
    "flight.cancelled.alt":   notify_flight_cancelled_alt,
    "flight.cancelled.noalt": notify_flight_cancelled_noalt,
}


def _is_permanent_failure(result: dict) -> bool:
    """Dead-letter malformed requests and 4xx SendGrid failures; retry transient errors."""
    if not isinstance(result, dict):
        return False

    status_code = result.get("status_code")
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return True

    error = str(result.get("error", "")).lower()
    permanent_markers = [
        "missing",
        "invalid",
        "bad request",
        "unauthorized",
        "forbidden",
    ]
    return any(marker in error for marker in permanent_markers)


def _dead_letter(channel, method, routing_key: str, reason: str):
    logger.error(
        "[RabbitMQ] Dead-lettering message | routing_key=%s queue=%s dlq=%s reason=%s",
        routing_key,
        RABBITMQ_QUEUE,
        RABBITMQ_DLQ,
        reason,
    )
    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def _declare_rabbitmq_topology(channel):
    """Declare the main notification queue and its DLQ."""
    channel.exchange_declare(
        exchange=RABBITMQ_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare(
        exchange=RABBITMQ_DLX,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue=RABBITMQ_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": RABBITMQ_DLX,
            "x-dead-letter-routing-key": RABBITMQ_DLQ_KEY,
        },
    )
    channel.queue_declare(queue=RABBITMQ_DLQ, durable=True)
    channel.queue_bind(
        queue=RABBITMQ_DLQ,
        exchange=RABBITMQ_DLX,
        routing_key=RABBITMQ_DLQ_KEY,
    )


def _get_rabbitmq_params():
    credentials = pika.PlainCredentials(
        os.environ.get("RABBITMQ_USER", "guest"),
        os.environ.get("RABBITMQ_PASSWORD", "guest"),
    )
    return pika.ConnectionParameters(
        host=os.environ.get("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.environ.get("RABBITMQ_PORT", 5672)),
        virtual_host=os.environ.get("RABBITMQ_VHOST", "/"),
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=300,
    )


def _on_message(channel, method, properties, body):
    routing_key = method.routing_key
    logger.info("[RabbitMQ] Received | routing_key=%s", routing_key)

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        _dead_letter(channel, method, routing_key, "invalid JSON payload")
        return

    handler = RABBITMQ_HANDLERS.get(routing_key)
    if handler is None:
        logger.warning("[RabbitMQ] No handler for '%s' - skipped", routing_key)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        result = handler(data)
        if result.get("success"):
            logger.info("[RabbitMQ] Email sent for '%s'", routing_key)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        elif _is_permanent_failure(result):
            _dead_letter(channel, method, routing_key, result.get("error", "permanent handler failure"))
        else:
            logger.error("[RabbitMQ] Email failed for '%s': %s - requeued", routing_key, result.get("error"))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as exc:
        logger.exception("[RabbitMQ] Unexpected error for '%s': %s - requeued", routing_key, exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def _consume():
    """Connect and consume from RabbitMQ. Retries automatically on connection loss."""
    while True:
        try:
            connection = pika.BlockingConnection(_get_rabbitmq_params())
            channel    = connection.channel()

            _declare_rabbitmq_topology(channel)

            for binding_key in RABBITMQ_BINDINGS:
                channel.queue_bind(
                    queue=RABBITMQ_QUEUE,
                    exchange=RABBITMQ_EXCHANGE,
                    routing_key=binding_key
                )
                logger.info("[RabbitMQ] Bound queue to routing key: %s", binding_key)
            logger.info(
                "[RabbitMQ] DLQ ready | dlx=%s dlq=%s routing_key=%s",
                RABBITMQ_DLX,
                RABBITMQ_DLQ,
                RABBITMQ_DLQ_KEY,
            )

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=_on_message)
            logger.info("[RabbitMQ] Consumer started | queue=%s", RABBITMQ_QUEUE)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as exc:
            logger.warning("[RabbitMQ] Connection lost: %s - retrying in 5s", exc)
            time.sleep(5)
        except Exception as exc:
            logger.exception("[RabbitMQ] Unexpected error: %s - retrying in 5s", exc)
            time.sleep(5)


def start_rabbitmq_consumer():
    """Launch the RabbitMQ consumer in a background daemon thread."""
    thread = threading.Thread(target=_consume, name="rabbitmq-consumer", daemon=True)
    thread.start()
    logger.info("[RabbitMQ] Consumer thread started")

# =============================================================================
# FLASK APP — health check + Scenario 3 HTTP endpoints
# =============================================================================

app = Flask(__name__)


@app.post("/notifications/voucher")
def notify_voucher_conversion():
    data = request.get_json(silent=True) or {}

    passenger_email = data.get("passengerEmail")
    if not passenger_email:
        return {"success": False, "error": "Missing passengerEmail"}, 400

    template = voucher_confirmation_template(data)
    pdf_bytes, pdf_filename = _safe_pdf(generate_voucher_pdf, data, "voucher_confirmation.pdf")
    result = send_email(
        passenger_email,
        _display_name(data),
        template["subject"],
        template["html"],
        template["text"],
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "email send failed")}, 500

    return {"success": True, "message": "Voucher confirmation email sent"}, 200


@app.post("/notifications/voucher-bundle")
def notify_voucher_bundle_conversion():
    data = request.get_json(silent=True) or {}

    passenger_email = data.get("passengerEmail")
    vouchers = data.get("vouchers") or []

    if not passenger_email:
        return {"success": False, "error": "Missing passengerEmail"}, 400
    if not isinstance(vouchers, list) or not vouchers:
        return {"success": False, "error": "Missing vouchers list"}, 400

    template = voucher_bundle_confirmation_template(data)
    pdf_bytes, pdf_filename = _safe_pdf(generate_voucher_bundle_pdf, data, "voucher_bundle_confirmation.pdf")
    result = send_email(
        passenger_email,
        _display_name(data),
        template["subject"],
        template["html"],
        template["text"],
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename)

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "email send failed")}, 500

    return {"success": True, "message": "Voucher bundle confirmation email sent"}, 200


@app.get("/health")
def health():
    return {"status": "UP", "service": "notification-service"}, 200


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    start_rabbitmq_consumer()

    port  = int(os.environ.get("FLASK_PORT", 3004))
    debug = os.environ.get("FLASK_ENV", "development") == "development"

    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
