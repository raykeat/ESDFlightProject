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
    POST /cancellation  — Staff UI triggers flight cancellation
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
RECORD_SERVICE_URL = os.environ.get("RECORD_SERVICE_URL", "http://record-service:3000")
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
# POST /cancellation
# Airline Staff UI triggers flight cancellation
#
# Required body:
#   FlightID             (int)  — flight to cancel
#   CancellationReason   (str)  — reason for cancellation
#
# Steps:
#   1. GET flight details from Flight Service
#   2. PUT flight status to "Cancelled"
#   3. PUT bulk release all seats on the flight
#   4. Publish flight.cancelled event to Kafka
#   5. Return success to UI
# ==========================================
@app.post("/cancellation")
@app.post("/cancel")
def cancel_flight():
    log_event("cancel_flight_request")

    # ── Validate request ─────────────────────────────────────
    data  = request.get_json(silent=True)
    normalized = {
        "FlightID": data.get("FlightID") if data else None,
        "CancellationReason": data.get("CancellationReason") if data else None,
    }

    if normalized["FlightID"] is None and data:
        normalized["FlightID"] = data.get("flightID")
    if normalized["CancellationReason"] is None and data:
        normalized["CancellationReason"] = data.get("cancellationReason")

    error = validate_fields(normalized, ["FlightID", "CancellationReason"])
    if error:
        return jsonify({
            "error":   "Bad Request",
            "code":    "MISSING_FIELDS",
            "message": error
        }), 400

    flight_id           = normalized["FlightID"]
    cancellation_reason = normalized["CancellationReason"]

    if not isinstance(flight_id, int) or flight_id <= 0:
        return jsonify({
            "error":   "Bad Request",
            "code":    "INVALID_FIELD_TYPE",
            "message": "flightID must be a positive integer"
        }), 400

    log_event("cancel_flight_started", flightID=flight_id, reason=cancellation_reason)

    # ── Step 1: PUT flight status to cancelled (returns flight details) ─
    try:
        flight_res = requests.put(
            f"{FLIGHT_SERVICE_URL}/flights/{flight_id}",
            json={
                "Status": "Cancelled",
                "CancellationReason": cancellation_reason,
            },
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

    # ── Step 2a: GET count of affected passengers (confirmed bookings) ──
    passengers_affected = 0
    try:
        records_res = requests.get(
            f"{RECORD_SERVICE_URL}/records",
            params={"FlightID": flight_id, "bookingstatus": "Confirmed"},
            timeout=10
        )
        if records_res.ok:
            records = records_res.json()
            passengers_affected = len(records) if isinstance(records, list) else 0
        else:
            logger.warning("Record Service returned %d for flightID=%d", records_res.status_code, flight_id)
            passengers_affected = 0
    except requests.exceptions.RequestException as e:
        logger.warning("Could not count affected passengers for flightID=%d: %s", flight_id, str(e))
        passengers_affected = 0

    # ── Step 2b: PUT bulk cancel all seats on the flight ──────

    try:
        release_res = requests.put(
            f"{SEATS_SERVICE_URL}/seats/cancel",
            params={"FlightID": flight_id},
            timeout=10
        )
        if not release_res.ok:
            return jsonify({
                "error": "Service Error",
                "code": "SEAT_UPDATE_FAILED",
                "message": f"Failed to cancel seats: {release_res.text}"
            }), 502
        seats_result = release_res.json() if release_res.content else {}
        seats_cancelled = seats_result.get("SeatsCancelled", 0)
    except requests.exceptions.RequestException as e:
        log_event("seat_service_unreachable", flightID=flight_id, error=str(e))
        return jsonify({
            "error": "Service Unavailable",
            "code": "SEAT_SERVICE_ERROR",
            "message": "Could not cancel seats for the flight"
        }), 503

    # ── Step 3: Publish flight.cancelled to Kafka ─────────────
    kafka_payload = {
        "FlightID":           flight_id,
        "Origin":             flight.get("Origin"),
        "Destination":        flight.get("Destination"),
        "Date":               flight.get("FlightDate") or flight.get("Date"),
        "DepartureTime":      flight.get("DepartureTime"),
        "CancellationReason": cancellation_reason,
    }

    kafka_published = False
    if not producer:
        init_kafka_producer()

    if producer:
        try:
            future = producer.send(
                KAFKA_TOPIC,
                key=str(flight_id),
                value=kafka_payload,
            )
            producer.flush()
            record_metadata = future.get(timeout=10)
            kafka_published = True
            log_event("kafka_published",
                      topic=record_metadata.topic,
                      partition=record_metadata.partition,
                      offset=record_metadata.offset,
                      flightID=flight_id)
        except KafkaError as e:
            logger.error("Failed to publish to Kafka: %s", str(e))
    else:
        logger.error("Kafka producer not available — event not published")

    if not kafka_published:
        log_event("cancel_flight_failed", flightID=flight_id, reason="Kafka publish failed")
        return jsonify({
            "error":   "Service Unavailable",
            "code":    "KAFKA_PUBLISH_FAILED",
            "message": "Flight was cancelled, but the cancellation event could not be published to the rebooking pipeline. Please retry when Kafka is available."
        }), 503

    # ── Step 4: Return success to Staff UI ────────────────────
    log_event("cancel_flight_completed",
              flightID=flight_id,
              kafkaPublished=kafka_published)

    return jsonify({
        "message": f"Flight {flight_id} successfully cancelled.",
        "SeatsCancelled": seats_cancelled,
        "seatsReleased": seats_cancelled,
        "PassengersAffected": passengers_affected
    }), 200


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5010))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)