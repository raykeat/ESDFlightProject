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
logger = logging.getLogger("worker-b-composite")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
PASSENGER_SERVICE_URL = os.getenv("PASSENGER_SERVICE_URL", "https://personal-4whagfbm.outsystemscloud.com/Passenger_Srv/rest/PassengerAPI")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:5000")
RECORD_SERVICE_URL = os.getenv("RECORD_SERVICE_URL", "http://record-service:3000")
COUPON_SERVICE_URL = os.getenv("COUPON_SERVICE_URL", "http://coupon-service:5000")
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
        raise RuntimeError(f"Record update failed ({status}): {response.status_code} {response.text}")



def process_path_b_message(msg):
    passenger_id = msg.get("PassengerID")
    booking_id = msg.get("BookingID")
    amount_paid = msg.get("AmountPaid")
    orig_flight_id = msg.get("OrigFlightID")
    hours_until_departure = msg.get("HoursUntilDeparture")

    passenger_endpoint = f"{PASSENGER_SERVICE_URL.rstrip('/')}/getpassenger/{passenger_id}/"
    passenger_response = requests.get(passenger_endpoint, timeout=10)
    if passenger_response.status_code == 404:
        passenger_response = requests.get(passenger_endpoint.rstrip('/'), timeout=10)
    if passenger_response.status_code >= 400:
        raise RuntimeError(f"Passenger lookup failed: {passenger_response.status_code} {passenger_response.text}")
    passenger_data = get_json_or_none(passenger_response) or {}
    passenger_email = passenger_data.get("Email", "")

    refund_response = requests.post(
        f"{PAYMENT_SERVICE_URL}/payments/refund",
        json={
            "BookingID": booking_id,
            "PassengerID": passenger_id,
        },
        timeout=10,
    )

    refund_payload = get_json_or_none(refund_response) or {}
    refund_status = refund_payload.get("Status") or refund_payload.get("status")

    if refund_response.status_code >= 400 or refund_status != "Refunded":
        try:
            update_record_status(booking_id, "Refund Failed")
        except Exception as exc:
            logger.error("Failed to set Refund Failed for BookingID=%s: %s", booking_id, str(exc))

        logger.error(
            "Refund failed for BookingID=%s PassengerID=%s: %s",
            booking_id,
            passenger_id,
            refund_payload or refund_response.text,
        )
        return

    update_record_status(booking_id, "Cancelled")
    refund_amount = refund_payload.get("RefundAmount", amount_paid)

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
    coupon_payload = get_json_or_none(coupon_response) or {}
    coupon_code = coupon_payload.get("CouponCode", "")
    discount_amount = coupon_payload.get("DiscountAmount", 0)

    orig_flight_response = requests.get(f"{FLIGHT_SERVICE_URL}/flights/{orig_flight_id}", timeout=10)
    orig_flight_data = get_json_or_none(orig_flight_response) or {}
    original_flight_number = orig_flight_data.get("FlightNumber", "")
    cancelled_date = orig_flight_data.get("FlightDate", "")

    notification_payload = {
        "type":  "flight.cancelled.noalt",
        "email": passenger_email,
        "data": {
            "PassengerID":    passenger_id,
            "BookingID":      booking_id,
            "OriginalFlight": original_flight_number,
            "CancelledDate":  cancelled_date,
            "RefundAmount":   refund_amount,
            "CouponCode":     coupon_code,
            "DiscountAmount": discount_amount,
        },
    }

    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="airline_events", exchange_type="topic", durable=True)
    channel.basic_publish(
        exchange="airline_events",
        routing_key="flight.cancelled.noalt",
        body=json.dumps(notification_payload),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    connection.close()

    logger.info(
        "Path B processed for BookingID=%s PassengerID=%s RefundID=%s",
        booking_id,
        passenger_id,
        refund_payload.get("RefundID") or refund_payload.get("refundID"),
    )



def run_consumer_loop():
    consumer = KafkaConsumer(
        "passenger.rebook.noalt",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="worker-b-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    logger.info("Worker B started. Listening on topic passenger.rebook.noalt")

    while True:
        for message in consumer:
            try:
                payload = json.loads(message.value.decode("utf-8"))
                process_path_b_message(payload)
            except Exception as exc:
                logger.error("Worker B failed for one passenger: %s", str(exc))
            finally:
                consumer.commit()


if __name__ == "__main__":
    run_consumer_loop()
