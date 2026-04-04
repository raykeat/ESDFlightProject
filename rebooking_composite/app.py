import json
import logging
import os
from datetime import datetime, timedelta

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
FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:3000").rstrip("/")
SEAT_SERVICE_URL = os.getenv("SEAT_SERVICE_URL", "http://seats-service:5003").rstrip("/")
RECORD_SERVICE_URL = os.getenv("RECORD_SERVICE_URL", "http://record-service:3000").rstrip("/")

FLIGHT_CANCELLED_TOPIC = "flight.cancelled"
PATH_A_TOPIC = "passenger.rebook.alt"
PATH_B_TOPIC = "passenger.rebook.noalt"


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


def parse_datetime(date_value, time_value="00:00:00"):
    if not date_value:
        return None

    date_obj = None
    for date_fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            date_obj = datetime.strptime(str(date_value), date_fmt).date()
            break
        except ValueError:
            continue

    if not date_obj:
        return None

    time_text = str(time_value or "00:00:00")
    for time_fmt in ("%H:%M:%S", "%H:%M"):
        try:
            time_obj = datetime.strptime(time_text, time_fmt).time()
            return datetime.combine(date_obj, time_obj)
        except ValueError:
            continue

    return datetime.combine(date_obj, datetime.min.time())


def get_confirmed_bookings(flight_id):
    payload = safe_get(
        f"{RECORD_SERVICE_URL}/records",
        params={"FlightID": flight_id, "BookingStatus": "Confirmed"},
    )
    if not payload:
        return []

    if not isinstance(payload, list):
        payload = payload.get("records", [])

    payload.sort(
        key=lambda item: (
            item.get("CreatedTime")
            or item.get("createdTime")
            or item.get("createdAt")
            or ""
        )
    )
    return payload


def get_booking_group_key(booking):
    booked_by = booking.get("BookedByPassengerID") or booking.get("bookedByPassengerID") or booking.get("PassengerID") or booking.get("passengerID")
    flight_id = booking.get("FlightID") or booking.get("flightID") or ""
    return f"{booked_by}|{flight_id}"


def get_primary_booking(group):
    for booking in group:
        if booking.get("PassengerID") or booking.get("passengerID"):
            return booking
    return group[0] if group else None


def normalize_booking_group(group, original_flight_id):
    primary = get_primary_booking(group)
    booked_by = primary.get("BookedByPassengerID") or primary.get("bookedByPassengerID") or primary.get("PassengerID") or primary.get("passengerID")
    total_amount = sum(float(member.get("AmountPaid") or member.get("amountPaid") or member.get("amount") or 0) for member in group)
    booking_ids = [
        int(member.get("BookingID") or member.get("bookingID"))
        for member in group
        if member.get("BookingID") or member.get("bookingID")
    ]

    return {
        "groupKey": get_booking_group_key(primary),
        "bookedByPassengerID": int(booked_by) if booked_by else None,
        "primaryPassengerID": int(primary.get("PassengerID") or primary.get("passengerID") or booked_by),
        "primaryBookingID": int(primary.get("BookingID") or primary.get("bookingID")),
        "origFlightID": int(original_flight_id),
        "bookingIDs": booking_ids,
        "groupSize": len(group),
        "amountPaid": total_amount,
        "records": group,
    }


def build_booking_groups(bookings, original_flight_id):
    grouped = {}
    for booking in bookings:
        grouped.setdefault(get_booking_group_key(booking), []).append(booking)

    groups = [normalize_booking_group(group, original_flight_id) for group in grouped.values()]
    groups.sort(
        key=lambda item: (
            item["primaryBookingID"],
        )
    )
    return groups


def get_candidate_flights(message, original_flight_id):
    origin = message.get("Origin") or message.get("origin")
    destination = message.get("Destination") or message.get("destination")
    cancelled_date = message.get("Date") or message.get("date")
    departure_time = message.get("DepartureTime") or message.get("departureTime") or "00:00:00"

    cancelled_dt = parse_datetime(cancelled_date, departure_time)
    if not cancelled_dt:
        return []

    search_end = (cancelled_dt + timedelta(days=2)).date().isoformat()
    flights = safe_get(
        f"{FLIGHT_SERVICE_URL}/flight/available",
        params={
            "origin": origin,
            "dest": destination,
            "dateFrom": cancelled_dt.date().isoformat(),
            "dateTo": search_end,
        },
    )

    if not flights or not isinstance(flights, list):
        return []

    candidates = []
    for flight in flights:
        if int(flight.get("FlightID", 0)) == int(original_flight_id):
            continue
        if str(flight.get("Status", "")).lower() == "cancelled":
            continue

        flight_dt = parse_datetime(flight.get("FlightDate") or flight.get("Date"), flight.get("DepartureTime"))
        if not flight_dt:
            continue
        if flight_dt < cancelled_dt or flight_dt > cancelled_dt + timedelta(days=2):
            continue

        candidates.append({
            **flight,
            "_departureDt": flight_dt,
        })

    candidates.sort(key=lambda flight: (flight["_departureDt"], int(flight.get("FlightID", 0))))
    return candidates


def get_available_seats_by_flight(flight_id):
    seats = safe_get(
        f"{SEAT_SERVICE_URL}/seats",
        params={"FlightID": flight_id, "Status": "available"},
    )
    if not seats or not isinstance(seats, list):
        return []

    seats.sort(key=lambda seat: int(seat.get("SeatID", 0)))
    return seats


def assign_groups_to_flights(groups, candidate_flights):
    seat_cache = {
        int(flight.get("FlightID")): get_available_seats_by_flight(flight.get("FlightID"))
        for flight in candidate_flights
    }

    path_a = []
    path_b = []

    for group in groups:
        assigned = None
        for flight in candidate_flights:
            flight_id = int(flight.get("FlightID"))
            available_seats = seat_cache.get(flight_id, [])
            if len(available_seats) >= group["groupSize"]:
                assigned_seats = available_seats[:group["groupSize"]]
                seat_cache[flight_id] = available_seats[group["groupSize"]:]
                assigned = {
                    "group": group,
                    "flight": flight,
                    "seats": assigned_seats,
                }
                break

        if assigned:
            path_a.append(assigned)
        else:
            path_b.append(group)

    return path_a, path_b


def publish_group_rebooking(path_a_assignments, path_b_groups, producer):
    for assignment in path_a_assignments:
        group = assignment["group"]
        flight = assignment["flight"]
        seats = assignment["seats"]

        payload = {
            "PassengerID": group["primaryPassengerID"],
            "BookingID": group["primaryBookingID"],
            "GroupBookingIDs": group["bookingIDs"],
            "GroupSize": group["groupSize"],
            "BookedByPassengerID": group["bookedByPassengerID"],
            "AmountPaid": group["amountPaid"],
            "OrigFlightID": group["origFlightID"],
            "NewFlightID": int(flight.get("FlightID")),
            "AssignedSeatIDs": [int(seat.get("SeatID")) for seat in seats],
            "AssignedSeatNumbers": [str(seat.get("SeatNumber")) for seat in seats],
        }

        producer.send(
            PATH_A_TOPIC,
            key=str(group["primaryPassengerID"]).encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
        )

    for group in path_b_groups:
        payload = {
            "PassengerID": group["primaryPassengerID"],
            "BookingID": group["primaryBookingID"],
            "GroupBookingIDs": group["bookingIDs"],
            "GroupSize": group["groupSize"],
            "BookedByPassengerID": group["bookedByPassengerID"],
            "AmountPaid": group["amountPaid"],
            "OrigFlightID": group["origFlightID"],
        }

        producer.send(
            PATH_B_TOPIC,
            key=str(group["primaryPassengerID"]).encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
        )

    producer.flush()


def fan_out_passengers(event_message, producer):
    original_flight_id = event_message.get("FlightID") or event_message.get("flightID")
    if not original_flight_id:
        logger.error("Missing FlightID in message: %s", event_message)
        return

    bookings = get_confirmed_bookings(original_flight_id)
    if not bookings:
        logger.info("No confirmed bookings for cancelled flight %s", original_flight_id)
        return

    groups = build_booking_groups(bookings, original_flight_id)
    candidate_flights = get_candidate_flights(event_message, original_flight_id)
    path_a_assignments, path_b_groups = assign_groups_to_flights(groups, candidate_flights)

    publish_group_rebooking(path_a_assignments, path_b_groups, producer)

    logger.info(
        "Rebooking split completed for flight %s: Path A groups=%s, Path B groups=%s",
        original_flight_id,
        len(path_a_assignments),
        len(path_b_groups),
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
            processed_ok = False
            try:
                event = json.loads(message.value.decode("utf-8"))
                fan_out_passengers(event, producer)
                processed_ok = True
            except Exception as exc:
                logger.error("Error processing cancellation event: %s", str(exc))
            finally:
                if processed_ok:
                    consumer.commit()
                else:
                    logger.warning("Skipping Kafka commit due to processing failure; message will be retried")


if __name__ == "__main__":
    run_consumer_loop()
