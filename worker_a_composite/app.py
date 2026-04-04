import json
import logging
import os

import pika
import requests
from dotenv import load_dotenv
from kafka import KafkaConsumer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker-a-composite")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
SEAT_SERVICE_URL = os.getenv("SEAT_SERVICE_URL", "http://seats-service:5003")
PASSENGER_SERVICE_URL = os.getenv("PASSENGER_SERVICE_URL", "https://personal-4whagfbm.outsystemscloud.com/Passenger_Srv/rest/PassengerAPI")
OFFER_SERVICE_URL = os.getenv("OFFER_SERVICE_URL", "http://offer-service:5000")
RECORD_SERVICE_URL = os.getenv("RECORD_SERVICE_URL", "http://record-service:3000")
FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:3000")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672")


def get_json_or_none(response):
    try:
        return response.json()
    except Exception:
        return None


def update_record_status(booking_id, status):
    response = requests.put(
        f"{RECORD_SERVICE_URL}/records/{booking_id}",
        json={"BookingStatus": status},
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Record status update failed ({status}): {response.status_code} {response.text}")


def resolve_assigned_seat_numbers(msg, new_flight_id):
    assigned_numbers = msg.get("AssignedSeatNumbers") or []
    if assigned_numbers:
        return [str(seat).strip() for seat in assigned_numbers if str(seat).strip()]

    assigned_ids = msg.get("AssignedSeatIDs") or []
    if not assigned_ids:
        return []

    seats_response = requests.get(f"{SEAT_SERVICE_URL}/seats/{new_flight_id}", timeout=10)
    if seats_response.status_code >= 400:
        raise RuntimeError(f"Failed to fetch seats for mapping IDs: {seats_response.status_code} {seats_response.text}")

    seats_payload = get_json_or_none(seats_response) or []
    seat_number_by_id = {
        int(seat.get("SeatID") or seat.get("seatID")): str(seat.get("SeatNumber") or seat.get("seatNumber") or "").strip()
        for seat in seats_payload
        if seat.get("SeatID") or seat.get("seatID")
    }

    resolved = []
    for seat_id in assigned_ids:
        seat_number = seat_number_by_id.get(int(seat_id))
        if not seat_number:
            raise RuntimeError(f"Could not resolve seat number for SeatID={seat_id} on flight {new_flight_id}")
        resolved.append(seat_number)
    return resolved


def hold_assigned_seats(new_flight_id, passenger_id, seat_numbers):
    if not seat_numbers:
        raise RuntimeError("Assigned seats missing for Path A hold")

    hold_response = requests.post(
        f"{SEAT_SERVICE_URL}/seats/hold",
        json={
            "flightID": int(new_flight_id),
            "seatNumber": ",".join(seat_numbers),
            "passengerID": int(passenger_id),
        },
        timeout=10,
    )
    if hold_response.status_code >= 400:
        raise RuntimeError(f"Seat hold failed: {hold_response.status_code} {hold_response.text}")


def process_path_a_message(msg):
    passenger_id = msg.get("PassengerID")
    booking_id = msg.get("BookingID")
    orig_flight_id = msg.get("OrigFlightID")
    new_flight_id = msg.get("NewFlightID")
    group_booking_ids = msg.get("GroupBookingIDs") or []
    group_size = msg.get("GroupSize") or len(group_booking_ids)

    if not passenger_id or not booking_id or not new_flight_id:
        raise RuntimeError("Missing required group Path A fields")

    assigned_seat_numbers = resolve_assigned_seat_numbers(msg, new_flight_id)
    hold_assigned_seats(new_flight_id, passenger_id, assigned_seat_numbers)

    passenger_endpoint = f"{PASSENGER_SERVICE_URL.rstrip('/')}/getpassenger/{passenger_id}/"
    passenger_response = requests.get(passenger_endpoint, timeout=10)
    if passenger_response.status_code == 404:
        passenger_response = requests.get(passenger_endpoint.rstrip('/'), timeout=10)
    if passenger_response.status_code >= 400:
        raise RuntimeError(f"Passenger lookup failed: {passenger_response.status_code} {passenger_response.text}")
    passenger_data = get_json_or_none(passenger_response) or {}
    passenger_email = passenger_data.get("Email", "")
    passenger_name = f"{passenger_data.get('FirstName', '')} {passenger_data.get('LastName', '')}".strip() or "Valued Passenger"

    offer_response = requests.post(
        f"{OFFER_SERVICE_URL}/offers",
        json={
            "BookingID": int(booking_id),
            "PassengerID": int(passenger_id),
            "OrigFlightID": int(orig_flight_id),
            "NewFlightID": int(new_flight_id),
            "AssignedSeats": msg.get("AssignedSeatIDs") or msg.get("AssignedSeatNumbers", []),
        },
        timeout=10,
    )
    if offer_response.status_code >= 400:
        raise RuntimeError(f"Offer creation failed: {offer_response.status_code} {offer_response.text}")
    offer_data = get_json_or_none(offer_response) or {}
    offer_id = offer_data.get("OfferID") or offer_data.get("offerID")

    for group_booking_id in group_booking_ids:
        update_record_status(group_booking_id, "Pending")

    orig_flight_response = requests.get(f"{FLIGHT_SERVICE_URL}/flights/{orig_flight_id}", timeout=10)
    orig_flight_data = get_json_or_none(orig_flight_response) or {}
    original_flight_number = orig_flight_data.get("FlightNumber", "")

    new_flight_response = requests.get(f"{FLIGHT_SERVICE_URL}/flights/{new_flight_id}", timeout=10)
    new_flight_data = get_json_or_none(new_flight_response) or {}
    new_flight_number = new_flight_data.get("FlightNumber", "")
    new_flight_date = new_flight_data.get("FlightDate", "")
    new_departure_time = new_flight_data.get("DepartureTime", "")

    notification_payload = {
        "type": "flight.cancelled.alt",
        "email": passenger_email,
        "data": {
            "PassengerID": passenger_id,
            "PassengerName": passenger_name,
            "BookingID": booking_id,
            "OfferID": offer_id,
            "OriginalFlight": original_flight_number,
            "NewFlight": new_flight_number,
            "NewDate": new_flight_date,
            "NewDepartureTime": new_departure_time,
            "GroupSize": group_size,
            "AcceptRejectLink": f"http://localhost:5173/rebooking-offer?offerID={offer_id}",
        },
    }

    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="airline_events", exchange_type="topic", durable=True)
    channel.basic_publish(
        exchange="airline_events",
        routing_key="flight.cancelled.alt",
        body=json.dumps(notification_payload),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()

    logger.info(
        "Path A processed for BookingID=%s PassengerID=%s GroupSize=%s OfferID=%s",
        booking_id,
        passenger_id,
        group_size,
        offer_id,
    )


def run_consumer_loop():
    consumer = KafkaConsumer(
        "passenger.rebook.alt",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="worker-a-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    logger.info("Worker A started. Listening on topic passenger.rebook.alt")

    while True:
        for message in consumer:
            try:
                payload = json.loads(message.value.decode("utf-8"))
                process_path_a_message(payload)
            except Exception as exc:
                logger.error("Worker A failed for one group: %s", str(exc))
            finally:
                consumer.commit()


if __name__ == "__main__":
    run_consumer_loop()
