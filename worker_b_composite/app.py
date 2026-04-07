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
VOUCHER_SERVICE_URL = os.getenv("VOUCHER_SERVICE_URL", "http://voucher-service:5005")
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


def restore_vouchers_for_booking(booking_id):
    try:
        response = requests.get(f"{RECORD_SERVICE_URL}/records/{booking_id}", timeout=10)
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to fetch booking record: {response.status_code} {response.text}")

        booking = get_json_or_none(response) or {}
        voucher_ids = []
        travel_credit_voucher_id = booking.get("travelCreditVoucherID") or booking.get("TravelCreditVoucherID")
        in_flight_perks_voucher_id = booking.get("inFlightPerksVoucherID") or booking.get("InFlightPerksVoucherID")

        if travel_credit_voucher_id:
            voucher_ids.append(int(travel_credit_voucher_id))
        if in_flight_perks_voucher_id:
            voucher_ids.append(int(in_flight_perks_voucher_id))

        for voucher_id in voucher_ids:
            voucher_response = requests.put(
                f"{VOUCHER_SERVICE_URL}/vouchers/{voucher_id}/status",
                json={"status": "ACTIVE"},
                timeout=10,
            )
            if voucher_response.status_code >= 400:
                logger.warning(
                    "Could not restore voucher %s for booking %s: %s",
                    voucher_id,
                    booking_id,
                    voucher_response.text,
                )
    except Exception as exc:
        logger.warning("Failed to restore vouchers for booking %s: %s", booking_id, str(exc))


def process_path_b_message(msg):
    passenger_id = msg.get("PassengerID")
    booking_id = msg.get("BookingID")
    amount_paid = msg.get("AmountPaid")
    orig_flight_id = msg.get("OrigFlightID")
    group_booking_ids = msg.get("GroupBookingIDs") or []

    passenger_endpoint = f"{PASSENGER_SERVICE_URL.rstrip('/')}/getpassenger/{passenger_id}/"
    passenger_response = requests.get(passenger_endpoint, timeout=10)
    if passenger_response.status_code == 404:
        passenger_response = requests.get(passenger_endpoint.rstrip('/'), timeout=10)
    if passenger_response.status_code >= 400:
        raise RuntimeError(f"Passenger lookup failed: {passenger_response.status_code} {passenger_response.text}")
    passenger_data = get_json_or_none(passenger_response) or {}
    passenger_email = passenger_data.get("Email", "")
    passenger_name = f"{passenger_data.get('FirstName', '')} {passenger_data.get('LastName', '')}".strip() or "Valued Passenger"

    refund_response = requests.post(
        f"{PAYMENT_SERVICE_URL}/payment/refund",
        json={
            "BookingID": booking_id,
            "PassengerID": passenger_id,
            "Amount": amount_paid,
            "refundType": "full",
        },
        timeout=10,
    )

    refund_payload = get_json_or_none(refund_response) or {}
    refund_status = refund_payload.get("Status") or refund_payload.get("status")

    if refund_response.status_code >= 400 or refund_status != "Refunded":
        try:
            update_record_status(booking_id, "Refund Failed")
            for group_booking_id in group_booking_ids:
                if int(group_booking_id) != int(booking_id):
                    update_record_status(group_booking_id, "Refund Failed")
        except Exception as exc:
            logger.error("Failed to set Refund Failed for BookingID=%s: %s", booking_id, str(exc))

        logger.error(
            "Refund failed for BookingID=%s PassengerID=%s: Status=%s Response=%s Payload=%s",
            booking_id,
            passenger_id,
            refund_response.status_code,
            refund_response.text,
            refund_payload,
        )
        return

    update_record_status(booking_id, "Cancelled")
    for group_booking_id in group_booking_ids:
        if int(group_booking_id) != int(booking_id):
            update_record_status(group_booking_id, "Cancelled")

    restore_vouchers_for_booking(booking_id)
    for group_booking_id in group_booking_ids:
        if int(group_booking_id) != int(booking_id):
            restore_vouchers_for_booking(group_booking_id)

    refund_amount = refund_payload.get("RefundAmount", amount_paid)
    refund_id = refund_payload.get("RefundID") or refund_payload.get("refundID")

    orig_flight_response = requests.get(f"{FLIGHT_SERVICE_URL}/flights/{orig_flight_id}", timeout=10)
    orig_flight_data = get_json_or_none(orig_flight_response) or {}
    original_flight_number = orig_flight_data.get("FlightNumber", "")
    cancelled_date = orig_flight_data.get("FlightDate", "")

    # Build list of all passenger names in the group
    passenger_names = [passenger_name]
    for gid in group_booking_ids:
        if int(gid) == int(booking_id):
            continue
        try:
            record_resp = requests.get(f"{RECORD_SERVICE_URL}/records/{gid}", timeout=10)
            if record_resp.status_code < 400:
                record_data = get_json_or_none(record_resp) or {}
                pax_id = record_data.get("PassengerID") or record_data.get("passengerID")
                if pax_id:
                    pax_endpoint = f"{PASSENGER_SERVICE_URL.rstrip('/')}/getpassenger/{pax_id}/"
                    pax_resp = requests.get(pax_endpoint, timeout=10)
                    if pax_resp.status_code == 404:
                        pax_resp = requests.get(pax_endpoint.rstrip('/'), timeout=10)
                    if pax_resp.status_code < 400:
                        pax_data = get_json_or_none(pax_resp) or {}
                        name = f"{pax_data.get('FirstName', '')} {pax_data.get('LastName', '')}".strip()
                        if name:
                            passenger_names.append(name)
        except Exception as exc:
            logger.warning("Could not fetch passenger name for booking %s: %s", gid, str(exc))

    notification_payload = {
        "type":  "flight.cancelled.noalt",
        "email": passenger_email,
        "data": {
            "PassengerID":    passenger_id,
            "PassengerName":  passenger_name,
            "PassengerNames": passenger_names,
            "BookingID":      booking_id,
            "OriginalFlight": original_flight_number,
            "OriginalOrigin": orig_flight_data.get("Origin", ""),
            "OriginalDestination": orig_flight_data.get("Destination", ""),
            "OriginalDepartureTime": orig_flight_data.get("DepartureTime", ""),
            "CancelledDate":  cancelled_date,
            "RefundAmount":   refund_amount,
            "RefundID":       refund_id,
            "RefundStatus":   refund_status,
            "GroupSize":      len(passenger_names),
        },
    }

    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="airline_events", exchange_type="topic", durable=True)
    channel.queue_declare(queue="notification_booking_queue", durable=True)
    channel.queue_bind(
        queue="notification_booking_queue",
        exchange="airline_events",
        routing_key="flight.cancelled.noalt",
    )
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
