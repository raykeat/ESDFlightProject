"""
Flight Cancellation Composite Service
======================================
Scenario 2 — Phase 1: Cancel the Flight (Synchronous)

Orchestrates:
1. GET flight details from Flight Service (for Kafka payload)
2. PUT flight status to "Cancelled" via Flight Service
3. PUT bulk release all seats via Seat Service
4. Publish flight.cancelled event to Kafka
5. Return success to Airline Staff UI immediately

Endpoints:
    POST /cancel  — Staff UI triggers flight cancellation
    GET  /health  — Health check
"""

import json
import logging
import os
import time

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from kafka import KafkaProducer
from kafka.errors import KafkaError

# ==========================================
# APP SETUP
# ==========================================
app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ==========================================
# SERVICE URLs — from environment variables
# ==========================================
FLIGHT_SERVICE_URL = os.environ.get("FLIGHT_SERVICE_URL", "http://flight-service:3000")
SEATS_SERVICE_URL  = os.environ.get("SEATS_SERVICE_URL",  "http://seats-service:5003")
KAFKA_BOOTSTRAP    = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC        = "flight.cancelled"

# ==========================================
# KAFKA PRODUCER — initialised at module
# level so it's ready before first request
# ==========================================
producer = None

def init_kafka_producer(retries=10, delay=5):
    global producer
    for i in range(retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8"),
                acks="all",   # wait for all replicas to acknowledge
                retries=3,
            )
            logger.info("✓ Connected to Kafka at %s", KAFKA_BOOTSTRAP)
            return
        except Exception as e:
            logger.warning("Kafka not ready, retrying in %ds... (%d/%d) — %s", delay, i+1, retries, e)
            time.sleep(delay)
    logger.error("Could not connect to Kafka after %d retries — events will not be published", retries)

# Initialise at import time so Docker/Gunicorn both work
init_kafka_producer()

# ==========================================
# HELPERS
# ==========================================
def log_event(event, **kwargs):
    logger.info(json.dumps({"event": event, **kwargs}))


def validate_fields(data, required_fields):
    if not data:
        return "Request body is missing or not valid JSON"
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


# ==========================================
# GET /health
# ==========================================
@app.get("/health")
def health():
    return jsonify({
        "status":  "UP",
        "service": "flight-cancellation-composite",
        "kafka":   "connected" if producer else "disconnected"
    }), 200


# ==========================================
# POST /cancel
# Airline Staff UI triggers flight cancellation
#
# Required body:
#   flightID           (int)  — flight to cancel
#   cancellationReason (str)  — reason for cancellation
#
# Steps:
#   1. GET flight details from Flight Service
#   2. PUT flight status to "Cancelled"
#   3. PUT bulk release all seats on the flight
#   4. Publish flight.cancelled event to Kafka
#   5. Return success to UI
# ==========================================
@app.post("/cancel")
def cancel_flight():
    log_event("cancel_flight_request")

    # ── Validate request ─────────────────────────────────────
    data  = request.get_json(silent=True)
    error = validate_fields(data, ["flightID", "cancellationReason"])
    if error:
        return jsonify({
            "error":   "Bad Request",
            "code":    "MISSING_FIELDS",
            "message": error
        }), 400

    flight_id           = data["flightID"]
    cancellation_reason = data["cancellationReason"]

    if not isinstance(flight_id, int) or flight_id <= 0:
        return jsonify({
            "error":   "Bad Request",
            "code":    "INVALID_FIELD_TYPE",
            "message": "flightID must be a positive integer"
        }), 400

    log_event("cancel_flight_started", flightID=flight_id, reason=cancellation_reason)

    # ── Step 1: GET flight details (needed for Kafka payload) ─
    try:
        flight_res = requests.get(
            f"{FLIGHT_SERVICE_URL}/flight/{flight_id}",
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        log_event("flight_service_unreachable", error=str(e))
        return jsonify({
            "error":   "Service Unavailable",
            "code":    "FLIGHT_SERVICE_ERROR",
            "message": "Could not reach Flight Service"
        }), 503

    if flight_res.status_code == 404:
        return jsonify({
            "error":   "Not Found",
            "code":    "FLIGHT_NOT_FOUND",
            "message": f"Flight {flight_id} not found"
        }), 404

    if not flight_res.ok:
        return jsonify({
            "error":   "Service Error",
            "code":    "FLIGHT_SERVICE_ERROR",
            "message": f"Flight Service returned {flight_res.status_code}"
        }), 502

    flight = flight_res.json()

    # Guard: already cancelled
    if flight.get("Status", "").lower() == "cancelled":
        return jsonify({
            "error":   "Conflict",
            "code":    "FLIGHT_ALREADY_CANCELLED",
            "message": f"Flight {flight_id} is already cancelled"
        }), 409

    # ── Step 2: PUT flight status to "Cancelled" ──────────────
    try:
        update_res = requests.put(
            f"{FLIGHT_SERVICE_URL}/flight/{flight_id}/status",
            json={"status": "cancelled"},
            timeout=10
        )
    except requests.exceptions.RequestException as e:
        log_event("flight_status_update_failed", flightID=flight_id, error=str(e))
        return jsonify({
            "error":   "Service Unavailable",
            "code":    "FLIGHT_SERVICE_ERROR",
            "message": "Could not update flight status"
        }), 503

    if not update_res.ok:
        log_event("flight_status_update_failed", flightID=flight_id, status=update_res.status_code)
        return jsonify({
            "error":   "Service Error",
            "code":    "FLIGHT_UPDATE_FAILED",
            "message": f"Failed to update flight status: {update_res.text}"
        }), 502

    log_event("flight_status_updated", flightID=flight_id, status="cancelled")

    # ── Step 3: PUT bulk release all seats on the flight ──────
    seats_released = 0
    seats_failed   = 0

    try:
        release_res = requests.put(
            f"{SEATS_SERVICE_URL}/seats/release/{flight_id}",
            timeout=10
        )
        if release_res.ok:
            seats_released = release_res.json().get("seatsReleased", 0)
            log_event("seats_bulk_released", flightID=flight_id, seatsReleased=seats_released)
        else:
            seats_failed = 1
            logger.warning("Seat Service bulk release failed for flight %d — status %d",
                           flight_id, release_res.status_code)
    except requests.exceptions.RequestException as e:
        # Non-fatal: flight is already cancelled, log and continue
        seats_failed = 1
        logger.warning("Seat Service unreachable for flight %d: %s", flight_id, str(e))

    # ── Step 4: Publish flight.cancelled to Kafka ─────────────
    # Include departureTime so Rebooking Composite can search
    # for alternative flights within ±1 day of original departure
    kafka_payload = {
        "flightID":           flight_id,
        "flightNumber":       flight.get("FlightNumber"),
        "origin":             flight.get("Origin"),
        "destination":        flight.get("Destination"),
        "date":               flight.get("Date"),
        "departureTime":      flight.get("DepartureTime"),
        "cancellationReason": cancellation_reason,
    }

    kafka_published = False
    if producer:
        try:
            future = producer.send(
                KAFKA_TOPIC,
                key=flight_id,  # flightID as message key — ensures partition ordering per flight
                value=kafka_payload,
            )
            producer.flush()
            record_metadata = future.get(timeout=10)
            kafka_published  = True
            log_event("kafka_published",
                      topic=record_metadata.topic,
                      partition=record_metadata.partition,
                      offset=record_metadata.offset,
                      flightID=flight_id)
        except KafkaError as e:
            logger.error("Failed to publish to Kafka: %s", str(e))
    else:
        logger.warning("Kafka producer not available — event not published")

    # ── Step 5: Return success to Staff UI ────────────────────
    log_event("cancel_flight_completed",
              flightID=flight_id,
              seatsReleased=seats_released,
              kafkaPublished=kafka_published)

    return jsonify({
        "message":        "Flight successfully cancelled",
        "flightID":       flight_id,
        "flightNumber":   flight.get("FlightNumber"),
        "seatsReleased":  seats_released,
        "seatsFailed":    seats_failed,
        "kafkaPublished": kafka_published,
    }), 200


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5010))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)