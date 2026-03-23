import json
import logging
import os
from datetime import datetime, timedelta

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
COUPON_SERVICE_URL = os.getenv("COUPON_SERVICE_URL", "http://coupon-service:5000")
OFFER_SERVICE_URL = os.getenv("OFFER_SERVICE_URL", "http://offer-service:5000")
RECORD_SERVICE_URL = os.getenv("RECORD_SERVICE_URL", "http://record-service:3000")



def get_json_or_none(response):
    try:
        return response.json()
    except Exception:
        return None



def process_path_a_message(payload):
    passenger_id = payload.get("PassengerID")
    booking_id = payload.get("BookingID")
    amount_paid = payload.get("AmountPaid")
    orig_flight_id = payload.get("OrigFlightID")
    new_flight_id = payload.get("NewFlightID")
    assigned_seat_id = payload.get("AssignedSeatID")
    assigned_seat_number = payload.get("AssignedSeatNumber")
    hours_until_departure = payload.get("HoursUntilDeparture")

    hold_response = requests.put(
        f"{SEAT_SERVICE_URL}/seats/{assigned_seat_id}/hold",
        timeout=10,
    )
    if hold_response.status_code >= 400:
        raise RuntimeError(f"Seat hold failed: {hold_response.status_code} {hold_response.text}")

    passenger_endpoint = f"{PASSENGER_SERVICE_URL.rstrip('/')}/getpassenger/{passenger_id}/"
    passenger_response = requests.get(passenger_endpoint, timeout=10)
    if passenger_response.status_code == 404:
        passenger_response = requests.get(passenger_endpoint.rstrip('/'), timeout=10)
    if passenger_response.status_code >= 400:
        raise RuntimeError(f"Passenger lookup failed: {passenger_response.status_code} {passenger_response.text}")
    passenger_data = get_json_or_none(passenger_response) or {}

    coupon_response = requests.post(
        f"{COUPON_SERVICE_URL}/coupons",
        json={
            "FlightPrice": amount_paid,
            "HoursUntilDeparture": hours_until_departure,
        },
        timeout=10,
    )
    if coupon_response.status_code >= 400:
        raise RuntimeError(f"Coupon generation failed: {coupon_response.status_code} {coupon_response.text}")
    coupon_data = get_json_or_none(coupon_response) or {}

    expiry_time = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    offer_response = requests.post(
        f"{OFFER_SERVICE_URL}/offers",
        json={
            "BookingID": booking_id,
            "PassengerID": passenger_id,
            "OrigFlightID": orig_flight_id,
            "NewFlightID": new_flight_id,
            "NewSeatID": assigned_seat_id,
            "CouponID": coupon_data.get("CouponID"),
            "ExpiryTime": expiry_time,
        },
        timeout=10,
    )
    if offer_response.status_code >= 400:
        raise RuntimeError(f"Offer creation failed: {offer_response.status_code} {offer_response.text}")
    offer_data = get_json_or_none(offer_response) or {}

    record_response = requests.put(
        f"{RECORD_SERVICE_URL}/records/{booking_id}",
        json={"BookingStatus": "Pending"},
        timeout=10,
    )
    if record_response.status_code >= 400:
        raise RuntimeError(f"Record status update failed: {record_response.status_code} {record_response.text}")

    # TODO: Publish to RabbitMQ exchange
    # Routing Key: flight.cancelled.alt
    # Payload: {
    #   "type": "flight.cancelled.alt",
    #   "email": <passenger email>,
    #   "data": {
    #     "PassengerID": <int>,
    #     "BookingID": <int>,
    #     "OfferID": <int>,
    #     "OriginalFlight": <original flight number>,
    #     "NewFlight": <new flight number>,
    #     "NewDate": <new flight date>,
    #     "NewDepartureTime": <new flight departure time>,
    #     "SeatNumber": <AssignedSeatNumber>,
    #     "CouponCode": <str>,
    #     "DiscountAmount": <float>,
    #     "AcceptRejectLink": "https://blazeair.com/offer?offerID=<OfferID>"
    #   }
    # }
    pass

    logger.info(
        "Path A processed for BookingID=%s PassengerID=%s SeatID=%s OfferID=%s BookingStatus=Pending",
        booking_id,
        passenger_id,
        assigned_seat_id,
        offer_data.get("OfferID") or offer_data.get("offerID"),
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
                logger.error("Worker A failed for one passenger: %s", str(exc))
            finally:
                consumer.commit()


if __name__ == "__main__":
    run_consumer_loop()
