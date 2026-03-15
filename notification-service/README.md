To run app.py
Run:
    pip install flask python-dotenv pika
    python app.py

notification-service/
├── app.py                  ← entire service (email service, templates, consumers, routes)
├── requirements.txt
├── Dockerfile
├── setup_rabbitmq.py       ← run once to create RabbitMQ exchange and queue
├── test_notification.py    ← manual test script
└── .env

How to run the service:
(1) The notification service is part of the main project at the project root. Run from the project root folder

docker-compose up --build

In a separate terminal, set up RabbitMQ echvnage and queue (run once)
python3 notification-service/setup_rabbitmq.py


