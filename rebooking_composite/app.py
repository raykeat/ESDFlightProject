import json
import logging
import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from kafka import KafkaConsumer, KafkaProducer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rebooking-composite")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:3000")
SEAT_SERVICE_URL = os.getenv("SEAT_SERVICE_URL", "http://seats-service:5003")
RECORD_SERVICE_URL = os.getenv("RECORD_SERVICE_URL", "http://record-service:3000")

FLIGHT_CANCELLED_TOPIC = "flight.cancelled"
PATH_A_TOPIC = "passenger.rebook.alt"
PATH_B_TOPIC = "passenger.rebook.noalt"



def parse_datetime(date_value, time_value):
    if not date_value or not time_value:
        return None

    date_formats = ["%Y-%m-%d", "%d/%m/%Y"]
    for date_fmt in date_formats:
        try:
            date_obj = datetime.strptime(str(date_value), date_fmt).date()
            break
        except ValueError:
            date_obj = None

    if not date_obj:
        return None

    time_text = str(time_value)
    for time_fmt in ["%H:%M", "%H:%M:%S"]:
        try:
            time_obj = datetime.strptime(time_text, time_fmt).time()
            return datetime.combine(date_obj, time_obj)
        except ValueError:
            continue

    return None



def calculate_hours_until_departure(message):
    departure_dt = parse_datetime(message.get("Date"), message.get("DepartureTime"))
    if not departure_dt:
        return 0.0
    delta = departure_dt - datetime.now()
    return round(delta.total_seconds() / 3600, 2)



def safe_get(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code >= 400:
            logger.error("GET %s failed: %s %s", url, response.status_code, response.text)
            return None
        return response.json()
    except requests.RequestException as exc:
        logger.error("GET %s failed: %s", url, str(exc))
        return None



def get_confirmed_bookings(flight_id):
    payload = safe_get(
        f"{RECORD_SERVICE_URL}/records",
        params={"FlightID": flight_id, "BookingStatus": "Confirmed"},
    )
    if not payload:
        return []

    if isinstance(payload, list):
        bookings = payload
    else:
        bookings = payload.get("records", [])

    bookings.sort(key=lambda item: item.get("CreatedTime") or item.get("createdTime") or item.get("createdAt") or "")
    return bookings



def get_alternative_flight(message, original_flight_id):
    flights = safe_get(
        f"{FLIGHT_SERVICE_URL}/flights",
        params={
            "origin": message.get("Origin"),
            "dest": message.get("Destination"),
            "date": message.get("Date"),
            "status": "Available",
        },
    )
    if not flights or not isinstance(flights, list):
        return None

    for flight in flights:
        if flight.get("FlightID") != original_flight_id:
            return flight
    return None



def get_available_seats(flight_id):
    seats = safe_get(
        f"{SEAT_SERVICE_URL}/seats",
        params={"FlightID": flight_id, "Status": "Available"},
    )
    if not seats or not isinstance(seats, list):
        return []
    return seats



def fan_out_passengers(event_message, producer):
    original_flight_id = event_message.get("FlightID")
    if not original_flight_id:
        logger.error("Missing FlightID in message: %s", event_message)
        return

    bookings = get_confirmed_bookings(original_flight_id)
    if not bookings:
        logger.info("No confirmed bookings for cancelled flight %s", original_flight_id)
        return

    alternative_flight = get_alternative_flight(event_message, original_flight_id)
    available_seats = []
    if alternative_flight:
        available_seats = get_available_seats(alternative_flight.get("FlightID"))

    hours_until_departure = calculate_hours_until_departure(event_message)

    path_a_count = min(len(bookings), len(available_seats))
    path_a_bookings = bookings[:path_a_count]
    path_b_bookings = bookings[path_a_count:]

    for index, booking in enumerate(path_a_bookings):
        seat = available_seats[index]

        passenger_id = booking.get("PassengerID") or booking.get("passengerID")
        booking_id = booking.get("BookingID") or booking.get("bookingID")
        amount_paid = booking.get("AmountPaid") or booking.get("amountPaid") or booking.get("amount")

        payload = {
            "PassengerID": int(passenger_id),
            "BookingID": int(booking_id),
            "AmountPaid": float(amount_paid),
            "OrigFlightID": int(original_flight_id),
            "NewFlightID": int(alternative_flight.get("FlightID")),
            "AssignedSeatID": int(seat.get("SeatID")),
            "AssignedSeatNumber": str(seat.get("SeatNumber")),
            "HoursUntilDeparture": float(hours_until_departure),
        }

        try:
            producer.send(
                PATH_A_TOPIC,
                key=str(payload["PassengerID"]).encode("utf-8"),
                value=json.dumps(payload).encode("utf-8"),
            )
        except Exception as exc:
            logger.error("Failed to publish Path A message for booking %s: %s", booking_id, str(exc))

    for booking in path_b_bookings:
        passenger_id = booking.get("PassengerID") or booking.get("passengerID")
        booking_id = booking.get("BookingID") or booking.get("bookingID")
        amount_paid = booking.get("AmountPaid") or booking.get("amountPaid") or booking.get("amount")

        payload = {
            "PassengerID": int(passenger_id),
            "BookingID": int(booking_id),
            "AmountPaid": float(amount_paid),
            "OrigFlightID": int(original_flight_id),
            "HoursUntilDeparture": float(hours_until_departure),
        }

        try:
            producer.send(
                PATH_B_TOPIC,
                key=str(payload["PassengerID"]).encode("utf-8"),
                value=json.dumps(payload).encode("utf-8"),
            )
        except Exception as exc:
            logger.error("Failed to publish Path B message for booking %s: %s", booking_id, str(exc))

    producer.flush()
    logger.info(
        "Rebooking split completed for flight %s: Path A=%s, Path B=%s",
        original_flight_id,
        len(path_a_bookings),
        len(path_b_bookings),
    )



def run_consumer_loop():
    consumer = KafkaConsumer(
        FLIGHT_CANCELLED_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="rebooking-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)

    logger.info("Rebooking consumer started. Listening on topic: %s", FLIGHT_CANCELLED_TOPIC)

    while True:
        for message in consumer:
            try:
                event = json.loads(message.value.decode("utf-8"))
                fan_out_passengers(event, producer)
            except Exception as exc:
                logger.error("Error processing cancellation event: %s", str(exc))
            finally:
                consumer.commit()


if __name__ == "__main__":
    run_consumer_loop()
