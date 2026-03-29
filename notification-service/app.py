"""
Notification Service
====================
Atomic microservice — consumes booking.confirmed from RabbitMQ
and sends booking confirmation email directly via SendGrid REST API.

Scenario 1 only: booking confirmation email after successful payment.

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

import pika
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# SENDGRID — calls REST API directly (bypasses latin-1 encoding issue)
# =============================================================================

def send_email(to_email: str, to_name: str, subject: str, html: str, text: str) -> dict:
    """Sends email via SendGrid REST API using UTF-8 encoding."""

    api_key    = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["SENDGRID_FROM_EMAIL"]
    from_name  = os.environ.get("SENDGRID_FROM_NAME", "YourAirline")

    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email, "name": to_name}]
            }
        ],
        "from":    {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html",  "value": html}
        ]
    }

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
            return {"success": True, "message_id": message_id}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error("SendGrid HTTP error for %s: %s - %s", to_email, e.code, error_body)
        return {"success": False, "error": error_body}
    except Exception as e:
        logger.error("SendGrid error for %s: %s", to_email, str(e))
        return {"success": False, "error": str(e)}


# =============================================================================
# EMAIL TEMPLATE — Scenario 1
# =============================================================================

def _format_money(amount) -> str:
    try:
        return f"{float(amount):.2f}"
    except Exception:
        return str(amount)


def _normalize_flights(data: dict) -> list[dict]:
    flights = data.get("flights")
    if isinstance(flights, list) and flights:
        return flights

    return [{
        "leg": "outbound",
        "flight_number": data.get("flight_number", "N/A"),
        "origin": data.get("origin", "Origin"),
        "destination": data.get("destination", "Destination"),
        "departure_date": data.get("departure_date", "N/A"),
        "seat_number": data.get("seat_number", "N/A"),
        "booking_id": data.get("booking_id"),
    }]

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
                    <div style="background:linear-gradient(135deg,#1d4ed8,#2563eb);padding:24px 28px;color:#ffffff;">
                        <h2 style="margin:0;font-size:28px;line-height:1.2;">{heading}</h2>
                        <p style="margin:10px 0 0;font-size:14px;opacity:0.95;">Dear {data['passenger_name']}, your payment has been received and your itinerary is confirmed.</p>
                    </div>
                    <div style="padding:24px 28px;">
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
                        <p style="margin:18px 0 0;color:#4b5563;font-size:13px;">Thank you for flying with us.</p>
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
# EMAIL TEMPLATE — Scenario 3 (Voucher Conversion)
# =============================================================================

def _display_name(data: dict) -> str:
    if data.get("passengerName"):
        return data["passengerName"]
    first = data.get("firstName") or ""
    last = data.get("lastName") or ""
    full = f"{first} {last}".strip()
    return full or "Valued Passenger"


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
# NOTIFICATION HANDLER
# =============================================================================

def notify_booking_confirmation(data: dict) -> dict:
    """Handles booking.confirmed event from RabbitMQ."""
    tpl = booking_confirmation_template(data)
    return send_email(
        data["passenger_email"],
        data["passenger_name"],
        tpl["subject"],
        tpl["html"],
        tpl["text"]
    )


# =============================================================================
# RABBITMQ CONSUMER
# =============================================================================

RABBITMQ_EXCHANGE = os.environ.get("RABBITMQ_EXCHANGE", "airline_events")
RABBITMQ_QUEUE    = "notification_booking_queue"
RABBITMQ_BINDING  = "booking.confirmed"


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
        logger.error("[RabbitMQ] Invalid JSON - rejected (no requeue)")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    if routing_key != "booking.confirmed":
        logger.warning("[RabbitMQ] Unexpected routing key '%s' - skipped", routing_key)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        result = notify_booking_confirmation(data)
        if result.get("success"):
            logger.info("[RabbitMQ] Booking confirmation email sent successfully")
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            logger.error("[RabbitMQ] Email failed: %s - requeued", result.get("error"))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as exc:
        logger.exception("[RabbitMQ] Unexpected error: %s - requeued", exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def _consume():
    """Connect and consume from RabbitMQ. Retries automatically on connection loss."""
    while True:
        try:
            connection = pika.BlockingConnection(_get_rabbitmq_params())
            channel = connection.channel()
            channel.exchange_declare(
                exchange=RABBITMQ_EXCHANGE,
                exchange_type="topic",
                durable=True
            )
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            channel.queue_bind(
                queue=RABBITMQ_QUEUE,
                exchange=RABBITMQ_EXCHANGE,
                routing_key=RABBITMQ_BINDING
            )
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=RABBITMQ_QUEUE,
                on_message_callback=_on_message
            )
            logger.info(
                "[RabbitMQ] Consumer started | queue=%s | binding=%s",
                RABBITMQ_QUEUE, RABBITMQ_BINDING
            )
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
# FLASK APP — health check only
# =============================================================================

app = Flask(__name__)


@app.post("/notifications/voucher")
def notify_voucher_conversion():
    data = request.get_json(silent=True) or {}

    passenger_email = data.get("passengerEmail")
    if not passenger_email:
        return {"success": False, "error": "Missing passengerEmail"}, 400

    template = voucher_confirmation_template(data)
    result = send_email(
        passenger_email,
        _display_name(data),
        template["subject"],
        template["html"],
        template["text"],
    )

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
    result = send_email(
        passenger_email,
        _display_name(data),
        template["subject"],
        template["html"],
        template["text"],
    )

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
