#!/usr/bin/env python3
"""
A standalone script to create exchanges and queues on RabbitMQ
for the Notification Service.
"""
import pika

import os
amqp_host = os.environ.get("RABBITMQ_HOST", "localhost")
amqp_port = int(os.environ.get("RABBITMQ_PORT", 5672))

exchange_name = "airline_events"   # must match RABBITMQ_EXCHANGE in .env
exchange_type = "topic"

queues = [
    {
        "name": "notification_booking_queue",  # Scenario 1 — booking confirmation
        "routing_key": "booking.confirmed",
    },
]


def create_exchange(hostname, port, exchange_name, exchange_type):
    print(f"Connecting to AMQP broker {hostname}:{port}...")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=hostname,
            port=port,
            heartbeat=300,
            blocked_connection_timeout=300,
        )
    )
    print("Connected")
    print("Creating channel...")
    channel = connection.channel()

    print(f"Creating exchange: {exchange_name} (type={exchange_type})")
    channel.exchange_declare(
        exchange=exchange_name, exchange_type=exchange_type, durable=True
    )
    return connection, channel


def create_queue(channel, exchange_name, queue_name, routing_key):
    print(f"Creating queue: {queue_name}")
    print(f"  Binding to exchange '{exchange_name}' with routing_key '{routing_key}'")
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(
        exchange=exchange_name, queue=queue_name, routing_key=routing_key
    )


def main():
    connection = None
    try:
        connection, channel = create_exchange(
            hostname=amqp_host,
            port=amqp_port,
            exchange_name=exchange_name,
            exchange_type=exchange_type,
        )
        for queue in queues:
            create_queue(
                channel=channel,
                exchange_name=exchange_name,
                queue_name=queue["name"],
                routing_key=queue["routing_key"],
            )
        print("\nSetup complete!")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Failed to connect to AMQP broker: {e}")
        print("Make sure RabbitMQ is running (docker-compose up -d rabbitmq)")
        raise
    finally:
        if connection and connection.is_open:
            print("Closing connection")
            connection.close()


if __name__ == "__main__":
    main()
