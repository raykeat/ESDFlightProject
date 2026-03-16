"""
Notification Service — Single File Version
==========================================
Runs Flask HTTP server + Kafka consumer + RabbitMQ consumer in one file.
 
Trigger sources:
  - RabbitMQ : booking.confirmed         (Scenario 1 — booking confirmation)
  - Kafka    : flight.cancelled.alt      (Scenario 2 Path A — rebooking offer with coupon)
  - Kafka    : flight.cancelled.noalt    (Scenario 2 Path B — refund with coupon)
  - HTTP POST: /refund-confirmation      (Scenario 3 Path B — passenger rejects rebooking)
 
Usage:
    pip install flask python-dotenv pika kafka-python
    python app.py
"""
 
import json
import logging
import os
import threading
import time
 
import pika
from kafka import KafkaConsumer
from dotenv import load_dotenv
from flask import Flask, Blueprint, request, jsonify
 
load_dotenv()
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
 
 
# =============================================================================
# EMAIL SERVICE (Mock — replace send_email() body when SendGrid is ready)
# =============================================================================
 
def send_email(to_email, to_name, subject, html_content, plain_text):
    """
    Calls the Email Service (atomic) via HTTP POST.
    Email Service is responsible for calling SendGrid.
    """
    import requests as http_requests
 
    email_service_url = os.environ.get("EMAIL_SERVICE_URL", "http://email-service:3005")
 
    try:
        response = http_requests.post(
            f"{email_service_url}/send-email",
            json={
                "to_email": to_email,
                "to_name":  to_name,
                "subject":  subject,
                "html":     html_content,
                "text":     plain_text,
            },
            timeout=10,
        )
        result = response.json()
        if result.get("success"):
            logger.info("Email sent to %s via Email Service | message_id=%s", to_email, result.get("message_id"))
        else:
            logger.error("Email Service failed for %s: %s", to_email, result.get("error"))
        return result
    except Exception as e:
        logger.error("Failed to reach Email Service for %s: %s", to_email, str(e))
        return {"success": False, "error": str(e)}
 
 
# =============================================================================
# EMAIL TEMPLATES
# =============================================================================
 
def booking_confirmation_template(data: dict) -> dict:
    ''' Scenario 1: Booking confirmed after successful payment.
        Consumed from RabbitMQ routing key: booking.confirmed
        Payload fields: booking_id, passenger_name, passenger_email,
                        flight_number, origin, destination,
                        departure_date, seat_number, amount_paid
    '''
    return {
        "subject": f"Booking Confirmed – {data['flight_number']}",
        "html": f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#2c7be5;"> Your Booking is Confirmed!</h2>
          <p>Dear {data['passenger_name']},</p>
          <p>Your booking has been successfully confirmed. Here are your flight details:</p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px;font-weight:bold;">Booking ID</td><td style="padding:8px;">{data['booking_id']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Flight</td><td style="padding:8px;">{data['flight_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">From</td><td style="padding:8px;">{data['origin']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">To</td><td style="padding:8px;">{data['destination']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Date</td><td style="padding:8px;">{data['departure_date']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Seat</td><td style="padding:8px;">{data['seat_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Amount Paid</td><td style="padding:8px;">${data['amount_paid']}</td></tr>
          </table>
          <p>Thank you for flying with us!</p>
        </div>
        """,
        "text": (
            f"Booking Confirmed! Booking ID: {data['booking_id']}. "
            f"Flight: {data['flight_number']} from {data['origin']} to {data['destination']} "
            f"on {data['departure_date']}. Seat: {data['seat_number']}. Amount Paid: ${data['amount_paid']}."
        ),
    }
 
 
def rebooking_offer_template(data: dict) -> dict:
    ''' Scenario 2 – Path A: Flight cancelled, alternative flight found.
        Consumed from Kafka topic: flight.cancelled.alt
        Payload fields: passenger_name, passenger_email, cancellation_reason,
                        cancelled_flight { flight_number, origin, destination, departure_date },
                        alternative_flight { flight_number, origin, destination, departure_date },
                        coupon_code, accept_link, reject_link
        Note: No fare difference is charged — airline absorbs cost difference.
    '''
    cf = data["cancelled_flight"]
    af = data["alternative_flight"]
    return {
        "subject": "Important: Your Flight Has Been Cancelled – Rebooking Offer Inside",
        "html": f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#d97706;">⚠️ Your Flight Has Been Cancelled</h2>
          <p>Dear {data['passenger_name']},</p>
          <p>We regret to inform you that your flight has been cancelled. We have found an alternative flight for you at no extra charge.</p>
 
          <h3 style="color:#e53e3e;">Cancelled Flight</h3>
          <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <tr><td style="padding:8px;font-weight:bold;">Flight</td><td style="padding:8px;">{cf['flight_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">From</td><td style="padding:8px;">{cf['origin']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">To</td><td style="padding:8px;">{cf['destination']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Date</td><td style="padding:8px;">{cf['departure_date']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Reason</td><td style="padding:8px;">{data['cancellation_reason']}</td></tr>
          </table>
 
          <h3 style="color:#2c7be5;">Proposed Alternative Flight</h3>
          <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <tr><td style="padding:8px;font-weight:bold;">Flight</td><td style="padding:8px;">{af['flight_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">From</td><td style="padding:8px;">{af['origin']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">To</td><td style="padding:8px;">{af['destination']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Date</td><td style="padding:8px;">{af['departure_date']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Fare Difference</td><td style="padding:8px;">None — covered by airline</td></tr>
          </table>
 
          <h3 style="color:#2c7be5;">🎟️ Your Compensation Coupon</h3>
          <p>As an apology for the inconvenience, here is a coupon code for your next booking:</p>
          <p style="font-size:24px;font-weight:bold;letter-spacing:4px;color:#2c7be5;">{data['coupon_code']}</p>
 
          <p>Please respond within 24 hours:</p>
          <div style="margin:24px 0;">
            <a href="{data['accept_link']}" style="background:#2c7be5;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;margin-right:12px;">✅ Accept Rebooking</a>
            <a href="{data['reject_link']}" style="background:#e53e3e;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;">❌ Reject & Refund</a>
          </div>
          <p style="color:#666;font-size:12px;">If you reject, you will receive a full refund for your original booking.</p>
        </div>
        """,
        "text": (
            f"Your flight {cf['flight_number']} has been cancelled ({data['cancellation_reason']}). "
            f"Alternative (no extra charge): {af['flight_number']} on {af['departure_date']}. "
            f"Coupon code: {data['coupon_code']}. "
            f"Accept: {data['accept_link']} | Reject & Refund: {data['reject_link']}"
        ),
    }
 
 
def flight_cancelled_refund_template(data: dict) -> dict:
    ''' Scenario 2 – Path B: Flight cancelled, no alternative flight found.
        Consumed from Kafka topic: flight.cancelled.noalt
        Payload fields: passenger_name, passenger_email, booking_id,
                        cancelled_flight { flight_number, origin, destination, departure_date },
                        refund_amount, coupon_code, cancellation_reason
    '''
    cf = data["cancelled_flight"]
    return {
        "subject": "Your Flight Has Been Cancelled – Full Refund Issued",
        "html": f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#e53e3e;">⚠️ Your Flight Has Been Cancelled</h2>
          <p>Dear {data['passenger_name']},</p>
          <p>We regret to inform you that your flight has been cancelled and unfortunately no alternative flight is available on this route.</p>
 
          <h3 style="color:#e53e3e;">Cancelled Flight</h3>
          <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <tr><td style="padding:8px;font-weight:bold;">Booking ID</td><td style="padding:8px;">{data['booking_id']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Flight</td><td style="padding:8px;">{cf['flight_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">From</td><td style="padding:8px;">{cf['origin']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">To</td><td style="padding:8px;">{cf['destination']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Date</td><td style="padding:8px;">{cf['departure_date']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Reason</td><td style="padding:8px;">{data['cancellation_reason']}</td></tr>
          </table>
 
          <h3 style="color:#2c7be5;">💸 Refund Confirmation</h3>
          <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
            <tr><td style="padding:8px;font-weight:bold;">Refund Amount</td><td style="padding:8px;">${data['refund_amount']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Refund Status</td><td style="padding:8px;">Processed — allow 5–7 business days</td></tr>
          </table>
 
          <h3 style="color:#2c7be5;">🎟️ Your Compensation Coupon</h3>
          <p>As an apology for the inconvenience, here is a coupon code for your next booking:</p>
          <p style="font-size:24px;font-weight:bold;letter-spacing:4px;color:#2c7be5;">{data['coupon_code']}</p>
 
          <p>We sincerely apologise for the inconvenience and hope to see you on board again soon.</p>
        </div>
        """,
        "text": (
            f"Your flight {cf['flight_number']} has been cancelled ({data['cancellation_reason']}). "
            f"No alternative flight is available. "
            f"A full refund of ${data['refund_amount']} has been issued. Allow 5–7 business days. "
            f"Compensation coupon code: {data['coupon_code']}."
        ),
    }
 
 
def refund_confirmation_template(data: dict) -> dict:
    ''' Scenario 3 – Path B: Passenger rejected rebooking offer.
        Triggered via HTTP POST by Rebooking Composite Service.
        Payload fields: passenger_name, passenger_email, booking_id,
                        flight_number, origin, destination, refund_amount, reason
    '''
    return {
        "subject": "Rebooking Rejected – Full Refund Issued",
        "html": f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#2c7be5;">💸 Refund Confirmed</h2>
          <p>Dear {data['passenger_name']},</p>
          <p>{data['reason']}</p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr><td style="padding:8px;font-weight:bold;">Booking ID</td><td style="padding:8px;">{data['booking_id']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Flight</td><td style="padding:8px;">{data['flight_number']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">From</td><td style="padding:8px;">{data['origin']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">To</td><td style="padding:8px;">{data['destination']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Refund Amount</td><td style="padding:8px;">${data['refund_amount']}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Refund Status</td><td style="padding:8px;">Processed — allow 5–7 business days</td></tr>
          </table>
          <p>We apologise for the inconvenience and hope to see you on board again soon.</p>
        </div>
        """,
        "text": (
            f"Rebooking rejected. Booking ID: {data['booking_id']}. "
            f"Flight: {data['flight_number']} from {data['origin']} to {data['destination']}. "
            f"Full refund of ${data['refund_amount']} issued. Allow 5–7 business days."
        ),
    }
 
 
 
def notify_booking_confirmation(data: dict) -> dict:
    """Scenario 1 — triggered by RabbitMQ routing key: booking.confirmed"""
    tpl = booking_confirmation_template(data)
    return send_email(data["passenger_email"], data["passenger_name"], tpl["subject"], tpl["html"], tpl["text"])
 
def notify_rebooking_offer(data: dict) -> dict:
    """Scenario 2 Path A — triggered by Kafka topic: flight.cancelled.alt"""
    tpl = rebooking_offer_template(data)
    return send_email(data["passenger_email"], data["passenger_name"], tpl["subject"], tpl["html"], tpl["text"])
 
def notify_flight_cancelled_refund(data: dict) -> dict:
    """Scenario 2 Path B — triggered by Kafka topic: flight.cancelled.noalt"""
    tpl = flight_cancelled_refund_template(data)
    return send_email(data["passenger_email"], data["passenger_name"], tpl["subject"], tpl["html"], tpl["text"])
 
def notify_refund_confirmation(data: dict) -> dict:
    """Scenario 3 Path B — triggered via HTTP POST by Rebooking Composite"""
    tpl = refund_confirmation_template(data)
    return send_email(data["passenger_email"], data["passenger_name"], tpl["subject"], tpl["html"], tpl["text"])
 
 
# Dispatcher used by the RabbitMQ consumer (routing key → handler)
RABBITMQ_HANDLERS = {
    "booking.confirmed": notify_booking_confirmation,
}
 
# Dispatcher used by the Kafka consumer (topic → handler)
KAFKA_HANDLERS = {
    "flight.cancelled.alt":   notify_rebooking_offer,
    "flight.cancelled.noalt": notify_flight_cancelled_refund,
}
 
 
# =============================================================================
# RABBITMQ CONSUMER — Scenario 1 (booking.confirmed)
# =============================================================================
 
RABBITMQ_EXCHANGE   = os.environ.get("RABBITMQ_EXCHANGE", "airline_events")
RABBITMQ_QUEUE      = "notification_booking_queue"
RABBITMQ_BINDING    = "booking.confirmed"
 
 
def _get_rabbitmq_params():
    credentials = pika.PlainCredentials(
        os.environ.get("RABBITMQ_USER", "guest"),
        os.environ.get("RABBITMQ_PASSWORD", "guest"),
    )
    return pika.ConnectionParameters(
        host=os.environ.get("RABBITMQ_HOST", "localhost"),
        port=int(os.environ.get("RABBITMQ_PORT", 5672)),
        virtual_host=os.environ.get("RABBITMQ_VHOST", "/"),
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=300,
    )
 
 
def _on_rabbitmq_message(channel, method, properties, body):
    routing_key = method.routing_key
    logger.info("[RabbitMQ] Received | routing_key=%s", routing_key)
 
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("[RabbitMQ] Invalid JSON — rejected (no requeue)")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
 
    handler = RABBITMQ_HANDLERS.get(routing_key)
    if handler is None:
        logger.warning("[RabbitMQ] No handler for '%s' — skipped", routing_key)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
 
    try:
        result = handler(data)
        if result.get("success"):
            logger.info("[RabbitMQ] Email sent for '%s'", routing_key)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            logger.error("[RabbitMQ] Email failed for '%s': %s — requeued", routing_key, result.get("error"))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as exc:
        logger.exception("[RabbitMQ] Unexpected error for '%s': %s — requeued", routing_key, exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
 
 
def _consume_rabbitmq():
    """Connect and consume from RabbitMQ. Retries on connection loss."""
    while True:
        try:
            connection = pika.BlockingConnection(_get_rabbitmq_params())
            channel = connection.channel()
            channel.exchange_declare(exchange=RABBITMQ_EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            channel.queue_bind(queue=RABBITMQ_QUEUE, exchange=RABBITMQ_EXCHANGE, routing_key=RABBITMQ_BINDING)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=_on_rabbitmq_message)
            logger.info("[RabbitMQ] Consumer started | queue=%s | binding=%s", RABBITMQ_QUEUE, RABBITMQ_BINDING)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as exc:
            logger.warning("[RabbitMQ] Connection lost: %s — retrying in 5s", exc)
            time.sleep(5)
        except Exception as exc:
            logger.exception("[RabbitMQ] Unexpected error: %s — retrying in 5s", exc)
            time.sleep(5)
 
 
def start_rabbitmq_consumer():
    """Launch the RabbitMQ consumer in a background daemon thread."""
    thread = threading.Thread(target=_consume_rabbitmq, name="rabbitmq-consumer", daemon=True)
    thread.start()
    logger.info("[RabbitMQ] Consumer thread started")
 
 
# =============================================================================
# KAFKA CONSUMER — Scenario 2 (flight.cancelled.alt / flight.cancelled.noalt)
# =============================================================================
 
KAFKA_BOOTSTRAP     = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPICS        = ["flight.cancelled.alt", "flight.cancelled.noalt"]
KAFKA_GROUP_ID      = "notification-service-group"
 
 
def _consume_kafka():
    """Connect and consume from Kafka. Retries on connection loss."""
    while True:
        try:
            consumer = KafkaConsumer(
                *KAFKA_TOPICS,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
            )
            logger.info("[Kafka] Consumer started | topics=%s", KAFKA_TOPICS)
 
            for message in consumer:
                topic = message.topic
                data  = message.value
                logger.info("[Kafka] Received message | topic=%s", topic)
 
                handler = KAFKA_HANDLERS.get(topic)
                if handler is None:
                    logger.warning("[Kafka] No handler for topic '%s' — skipped", topic)
                    continue
 
                try:
                    result = handler(data)
                    if result.get("success"):
                        logger.info("[Kafka] Email sent for topic '%s'", topic)
                    else:
                        logger.error("[Kafka] Email failed for topic '%s': %s", topic, result.get("error"))
                except Exception as exc:
                    logger.exception("[Kafka] Unexpected error for topic '%s': %s", topic, exc)
 
        except Exception as exc:
            logger.warning("[Kafka] Connection lost: %s — retrying in 5s", exc)
            time.sleep(5)
 
 
def start_kafka_consumer():
    """Launch the Kafka consumer in a background daemon thread."""
    thread = threading.Thread(target=_consume_kafka, name="kafka-consumer", daemon=True)
    thread.start()
    logger.info("[Kafka] Consumer thread started")
 
 
# =============================================================================
# FLASK HTTP ROUTES
# =============================================================================
 
notification_bp = Blueprint("notifications", __name__)
 
 
def _validate(body, required_fields):
    return [f for f in required_fields if not body.get(f)]
 
def _bad_request(missing):
    return jsonify({"success": False, "errors": [f"'{f}' is required" for f in missing]}), 400
 
def _send_and_respond(handler, data):
    result = handler(data)
    if result.get("success"):
        return jsonify({"success": True, "message_id": result.get("message_id")}), 200
    return jsonify({"success": False, "error": result.get("error", "Failed to send email")}), 502
 
 
@notification_bp.post("/refund-confirmation")
def refund_confirmation():
    """
    Scenario 3 – Path B: Passenger rejects the rebooking offer.
    Called via HTTP POST by the Rebooking Composite Service.
 
    Body:
      passenger_email, passenger_name, booking_id,
      flight_number, origin, destination,
      refund_amount, reason
    """
    body = request.get_json(force=True) or {}
    required = ["passenger_email", "passenger_name", "booking_id",
                "flight_number", "origin", "destination",
                "refund_amount", "reason"]
    if missing := _validate(body, required):
        return _bad_request(missing)
    return _send_and_respond(notify_refund_confirmation, body)
 
 
# =============================================================================
# FLASK APP + ENTRY POINT
# =============================================================================
 
app = Flask(__name__)
 
@app.get("/health")
def health():
    return {"status": "UP", "service": "notification-service"}, 200
 
app.register_blueprint(notification_bp, url_prefix="/api/notifications")
 
 
if __name__ == "__main__":
    start_rabbitmq_consumer()   # Scenario 1 — booking.confirmed
    start_kafka_consumer()      # Scenario 2 — flight.cancelled.alt / flight.cancelled.noalt
 
    port  = int(os.environ.get("FLASK_PORT", 3004))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
 
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
 