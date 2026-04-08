import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pika
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("PORT", "5013"))
RECORD_SERVICE_URL = os.environ.get("RECORD_SERVICE_URL", "http://record-service:3000").rstrip("/")
FLIGHT_SERVICE_URL = os.environ.get("FLIGHT_SERVICE_URL", "http://flight-service:3000").rstrip("/")
MILES_EARN_SERVICE_URL = os.environ.get("MILES_EARN_SERVICE_URL", "http://miles-earn-service:5009").rstrip("/")

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672")
RABBITMQ_EXCHANGE = os.environ.get("RABBITMQ_EXCHANGE", "airline_events")
FLIGHT_LANDED_KEY = os.environ.get("FLIGHT_LANDED_KEY", "flight.landed")
FLIGHT_LANDED_QUEUE = os.environ.get("FLIGHT_LANDED_QUEUE", "miles_awarding_flight_landed_queue")


def first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def parse_positive_int(value):
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except Exception:
        return None
    return None


def award_booking_if_completed(booking_id, force=False):
    booking_response = requests.get(
        f"{RECORD_SERVICE_URL}/records/{booking_id}",
        timeout=15,
    )
    booking_response.raise_for_status()
    booking = booking_response.json() or {}

    if str(first_non_empty(booking.get("status"), booking.get("bookingstatus"), "")).lower() != "confirmed":
        return {"awarded": False, "reason": "booking_not_confirmed"}

    if booking.get("milesAwardedAt"):
        return {
            "awarded": False,
            "reason": "already_awarded",
            "milesAwardedAt": booking.get("milesAwardedAt"),
            "milesAwarded": booking.get("milesAwarded"),
            "transactionID": booking.get("milesTransactionID"),
        }

    passenger_id = parse_positive_int(first_non_empty(booking.get("passengerID"), booking.get("PassengerID")))
    if not passenger_id:
        return {"awarded": False, "reason": "guest_or_missing_passenger"}

    flight_id = parse_positive_int(first_non_empty(booking.get("flightID"), booking.get("FlightID")))
    if not flight_id:
        return {"awarded": False, "reason": "missing_flight_id"}

    flight_response = requests.get(f"{FLIGHT_SERVICE_URL}/flight/{flight_id}", timeout=15)
    flight_response.raise_for_status()
    flight = flight_response.json() or {}

    flight_status = str(first_non_empty(flight.get("Status"), flight.get("status"), "")).lower()
    if flight_status == "cancelled":
        return {"awarded": False, "reason": "flight_cancelled"}

    if not force and flight_status != "landed":
        return {
            "awarded": False,
            "reason": "flight_not_landed",
            "flightStatus": first_non_empty(flight.get("Status"), flight.get("status")),
        }

    amount_paid_raw = first_non_empty(booking.get("amountPaid"), booking.get("amount"), booking.get("AmountPaid"))
    try:
        amount_paid = float(amount_paid_raw)
    except Exception:
        return {"awarded": False, "reason": "invalid_amount_paid"}

    earn_response = requests.post(
        f"{MILES_EARN_SERVICE_URL}/miles/earn",
        json={
            "passengerID": passenger_id,
            "flightCost": amount_paid,
            "bookingReference": f"BK-{str(booking_id).zfill(5)}",
            "currency": "SGD",
            "milesPerDollar": 1,
        },
        timeout=20,
    )
    earn_response.raise_for_status()
    earn_data = earn_response.json() or {}

    mark_response = requests.put(
        f"{RECORD_SERVICE_URL}/records/{booking_id}/miles-awarded",
        json={
            "milesAwarded": earn_data.get("earnedMiles"),
            "transactionID": earn_data.get("transactionID"),
        },
        timeout=15,
    )
    mark_response.raise_for_status()

    return {
        "awarded": True,
        "bookingID": booking_id,
        "passengerID": passenger_id,
        "flightID": flight_id,
        "earnedMiles": earn_data.get("earnedMiles"),
        "transactionID": earn_data.get("transactionID"),
        "newBalance": earn_data.get("newBalance"),
        "forced": bool(force),
    }


def award_flight(flight_id, force=False):
    bookings_response = requests.get(
        f"{RECORD_SERVICE_URL}/records",
        params={"FlightID": flight_id, "bookingstatus": "Confirmed"},
        timeout=20,
    )
    bookings_response.raise_for_status()
    bookings = bookings_response.json() if isinstance(bookings_response.json(), list) else []

    summary = {
        "flightID": int(flight_id),
        "totalBookings": len(bookings),
        "awarded": 0,
        "skipped": 0,
        "failed": 0,
        "details": [],
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for booking in bookings:
            booking_id = parse_positive_int(first_non_empty(booking.get("bookingID"), booking.get("BookingID")))
            if booking_id:
                futures[executor.submit(award_booking_if_completed, booking_id, force)] = booking_id

        for future in as_completed(futures):
            booking_id = futures[future]
            try:
                result = future.result()
                if result.get("awarded"):
                    summary["awarded"] += 1
                else:
                    summary["skipped"] += 1
                summary["details"].append({"bookingID": booking_id, **result})
            except Exception as exc:
                summary["failed"] += 1
                summary["details"].append(
                    {
                        "bookingID": booking_id,
                        "awarded": False,
                        "reason": "error",
                        "message": str(exc),
                    }
                )

    return summary


def start_rabbit_consumer():
    while True:
        connection = None
        channel = None
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.exchange_declare(exchange=RABBITMQ_EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue=FLIGHT_LANDED_QUEUE, durable=True)
            channel.queue_bind(queue=FLIGHT_LANDED_QUEUE, exchange=RABBITMQ_EXCHANGE, routing_key=FLIGHT_LANDED_KEY)

            def _on_message(ch, method, properties, body):
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                    flight_id = parse_positive_int(first_non_empty(payload.get("flightID"), payload.get("FlightID")))
                    force = bool(payload.get("force", False))
                    if not flight_id:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return

                    result = award_flight(flight_id, force=force)
                    print(f"Processed flight.landed event for flight {flight_id}: {result}")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    print(f"Failed to process flight.landed event: {exc}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=FLIGHT_LANDED_QUEUE, on_message_callback=_on_message)
            print("Miles awarding composite consuming flight.landed events")
            channel.start_consuming()
        except Exception as exc:
            print(f"RabbitMQ consumer error: {exc}")
            time.sleep(3)
        finally:
            try:
                if channel and channel.is_open:
                    channel.close()
            except Exception:
                pass
            try:
                if connection and connection.is_open:
                    connection.close()
            except Exception:
                pass


@app.get("/health")
def health():
    return jsonify({"status": "OK", "service": "miles-awarding-composite"}), 200


@app.post("/award/booking/<int:booking_id>")
def award_booking_endpoint(booking_id):
    force = bool((request.get_json(silent=True) or {}).get("force", False))
    try:
        result = award_booking_if_completed(booking_id, force=force)
        if result.get("awarded") or result.get("reason") == "already_awarded":
            return jsonify({"success": True, **result}), 200
        if result.get("reason") in {"flight_not_landed", "booking_not_confirmed"}:
            return jsonify({"success": False, **result}), 409
        return jsonify({"success": False, **result}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": "Failed to award miles", "message": str(exc)}), 500


@app.post("/award/flight/<int:flight_id>")
def award_flight_endpoint(flight_id):
    force = bool((request.get_json(silent=True) or {}).get("force", False))
    try:
        summary = award_flight(flight_id, force=force)
        return jsonify({"success": True, **summary}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": "Failed to award flight miles", "message": str(exc)}), 500


if __name__ == "__main__":
    consumer = threading.Thread(target=start_rabbit_consumer, daemon=True)
    consumer.start()
    app.run(host="0.0.0.0", port=PORT)
