import os
import time
import threading
import json
import urllib.request
import pika
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import text

app = Flask(__name__)
CORS(app)

# Database Configuration
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'rootpassword')
db_host = os.environ.get('DB_HOST', 'localhost')
db_name = os.environ.get('DB_NAME', 'flightdb')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:3306/{db_name}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

AUTO_LAND_ENABLED = os.environ.get('AUTO_LAND_ENABLED', 'true').lower() == 'true'
AUTO_LAND_INTERVAL_SECONDS = int(os.environ.get('AUTO_LAND_INTERVAL_SECONDS', '60'))
BOOKING_COMPOSITE_URL = os.environ.get('BOOKING_COMPOSITE_URL', 'http://booking-composite-service:3001').rstrip('/')
MILES_AWARDING_COMPOSITE_URL = os.environ.get('MILES_AWARDING_COMPOSITE_URL', 'http://miles-awarding-composite:5013').rstrip('/')
RABBITMQ_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672')
RABBITMQ_EXCHANGE = os.environ.get('RABBITMQ_EXCHANGE', 'airline_events')
FLIGHT_LANDED_KEY = os.environ.get('FLIGHT_LANDED_KEY', 'flight.landed')

DEMO_FLIGHT_ROWS = [
    (70001, 'BA701', 'Dubai', 'Edinburgh', '2026-04-02', '08:15:00', '08:00:00', '16:15:00', 780.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (70002, 'BA702', 'Dubai', 'Edinburgh', '2026-04-04', '19:40:00', '08:05:00', '03:45:00', 760.00, 'available', '1 Hot Meal', '1 Selected', True, '30kg'),
    (70003, 'BA703', 'Dubai', 'Edinburgh', '2026-04-06', '10:05:00', '08:10:00', '18:15:00', 795.00, 'available', '2 Hot Meals', 'Free-flow', True, '35kg'),
    (70004, 'BA704', 'Dubai', 'Edinburgh', '2026-04-08', '22:20:00', '08:00:00', '06:20:00', 745.00, 'available', '1 Snack', '1 Selected', False, '25kg'),
    (70005, 'BA705', 'Edinburgh', 'Dubai', '2026-04-10', '09:30:00', '08:00:00', '17:30:00', 770.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (70006, 'BA706', 'Edinburgh', 'Dubai', '2026-04-12', '18:10:00', '08:05:00', '02:15:00', 755.00, 'available', '1 Hot Meal', '1 Selected', True, '30kg'),
    (71002, 'BA712', 'Bangkok', 'Singapore', '2026-04-03', '18:50:00', '03:00:00', '21:50:00', 360.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
    (72001, 'BA721', 'Singapore', 'Tokyo', '2026-04-09', '09:10:00', '07:00:00', '16:10:00', 840.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (72002, 'BA722', 'Tokyo', 'Singapore', '2026-04-16', '20:25:00', '07:00:00', '03:25:00', 825.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (73001, 'BA731', 'Singapore', 'London', '2026-04-15', '11:30:00', '14:00:00', '01:30:00', 1180.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (73002, 'BA732', 'London', 'Singapore', '2026-04-22', '13:10:00', '13:00:00', '02:10:00', 1160.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (74001, 'BA741', 'Singapore', 'New York', '2026-04-20', '21:45:00', '18:00:00', '15:45:00', 1720.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
    (74002, 'BA742', 'New York', 'Singapore', '2026-04-28', '10:15:00', '18:00:00', '04:15:00', 1690.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
    (75001, 'BA751', 'Singapore', 'Dubai', '2026-04-25', '06:40:00', '07:30:00', '14:10:00', 930.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (75002, 'BA752', 'Dubai', 'Singapore', '2026-05-02', '16:20:00', '07:30:00', '23:50:00', 910.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (76001, 'BA761', 'Singapore', 'Edinburgh', '2026-05-09', '08:55:00', '15:30:00', '00:25:00', 1175.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (76002, 'BA762', 'Edinburgh', 'Singapore', '2026-05-10', '19:15:00', '15:30:00', '10:45:00', 1125.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (10001, 'BA233', 'Singapore', 'Bangkok', '2026-05-03', '00:30:00', '03:00:00', '03:30:00', 385.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (10002, 'BA234', 'Bangkok', 'Singapore', '2026-05-08', '12:00:00', '03:00:00', '15:00:00', 380.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (10003, 'BA245', 'Singapore', 'Bangkok', '2026-05-03', '14:15:00', '03:00:00', '17:15:00', 410.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
    (10004, 'BA246', 'Bangkok', 'Singapore', '2026-05-08', '19:45:00', '03:00:00', '22:45:00', 400.00, 'available', '1 Snack', '1 Selected', False, '20kg'),
    (10005, 'BA247', 'Singapore', 'Bangkok', '2026-05-04', '08:10:00', '03:00:00', '11:10:00', 395.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (20001, 'BA101', 'Singapore', 'Tokyo', '2026-05-04', '08:00:00', '07:00:00', '15:00:00', 850.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (20002, 'BA102', 'Tokyo', 'Singapore', '2026-05-10', '18:00:00', '07:00:00', '01:00:00', 820.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (20003, 'BA111', 'Singapore', 'Tokyo', '2026-05-04', '22:30:00', '07:00:00', '05:30:00', 790.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
    (20004, 'BA112', 'Tokyo', 'Singapore', '2026-05-10', '09:15:00', '07:00:00', '16:15:00', 800.00, 'available', '1 Hot Meal', '1 Selected', False, '30kg'),
    (30001, 'BA322', 'Singapore', 'London', '2026-05-05', '23:30:00', '14:00:00', '13:30:00', 1200.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (30002, 'BA323', 'London', 'Singapore', '2026-05-15', '10:00:00', '13:00:00', '23:00:00', 1150.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (30003, 'BA330', 'Singapore', 'London', '2026-05-05', '08:45:00', '14:00:00', '22:45:00', 1350.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (30004, 'BA331', 'London', 'Singapore', '2026-05-15', '21:20:00', '14:00:00', '11:20:00', 1300.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (40001, 'BA024', 'Singapore', 'New York', '2026-05-06', '10:00:00', '18:00:00', '04:00:00', 1800.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
    (40002, 'BA025', 'New York', 'Singapore', '2026-05-20', '20:00:00', '18:00:00', '14:00:00', 1750.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
    (40003, 'BA030', 'Singapore', 'New York', '2026-05-06', '23:55:00', '18:00:00', '17:55:00', 1650.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
    (40004, 'BA031', 'New York', 'Singapore', '2026-05-20', '08:30:00', '18:00:00', '02:30:00', 1600.00, 'available', '2 Hot Meals', 'Free-flow', True, '30kg'),
    (50001, 'BA405', 'Singapore', 'Dubai', '2026-05-07', '02:00:00', '07:30:00', '09:30:00', 950.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (50002, 'BA406', 'Dubai', 'Singapore', '2026-05-18', '09:00:00', '07:30:00', '16:30:00', 900.00, 'available', '1 Hot Meal', 'Free-flow', True, '30kg'),
    (50003, 'BA415', 'Singapore', 'Dubai', '2026-05-07', '15:45:00', '07:30:00', '23:15:00', 980.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (50004, 'BA416', 'Dubai', 'Singapore', '2026-05-18', '23:10:00', '07:30:00', '06:40:00', 920.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (60001, 'BA800', 'Singapore', 'Edinburgh', '2026-05-05', '00:05:00', '15:30:00', '15:35:00', 1100.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (60002, 'BA801', 'Edinburgh', 'Singapore', '2026-05-15', '14:30:00', '15:30:00', '06:00:00', 1080.00, 'available', '2 Hot Meals', 'Free-flow', True, '40kg'),
    (60003, 'BA810', 'Singapore', 'Edinburgh', '2026-05-05', '13:15:00', '15:30:00', '04:45:00', 1250.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
    (60004, 'BA811', 'Edinburgh', 'Singapore', '2026-05-15', '23:45:00', '15:30:00', '15:15:00', 1150.00, 'available', '3 Hot Meals', 'Free-flow', True, '40kg'),
]


def ensure_status_enum_allows_landed():
    """Best-effort migration for existing DBs so landed can be persisted."""
    try:
        with db.engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE flights MODIFY COLUMN Status "
                "ENUM('available', 'unavailable', 'cancelled', 'landed') "
                "NOT NULL DEFAULT 'available'"
            ))
    except Exception as e:
        print(f"Status enum migration warning: {e}")


def ensure_demo_flights_seeded():
    """Insert demo flights when the DB volume already exists and init.sql will not rerun."""
    try:
        insert_sql = text(
            "INSERT IGNORE INTO flights "
            "(FlightID, FlightNumber, Origin, Destination, FlightDate, DepartureTime, FlightDuration, ArrivalTime, Price, Status, Meals, Beverages, Wifi, Baggage) "
            "VALUES "
            "(:FlightID, :FlightNumber, :Origin, :Destination, :FlightDate, :DepartureTime, :FlightDuration, :ArrivalTime, :Price, :Status, :Meals, :Beverages, :Wifi, :Baggage)"
        )
        payload = [
            {
                "FlightID": flight_id,
                "FlightNumber": flight_number,
                "Origin": origin,
                "Destination": destination,
                "FlightDate": flight_date,
                "DepartureTime": departure_time,
                "FlightDuration": flight_duration,
                "ArrivalTime": arrival_time,
                "Price": price,
                "Status": status,
                "Meals": meals,
                "Beverages": beverages,
                "Wifi": wifi,
                "Baggage": baggage,
            }
            for flight_id, flight_number, origin, destination, flight_date, departure_time, flight_duration, arrival_time, price, status, meals, beverages, wifi, baggage in DEMO_FLIGHT_ROWS
        ]

        with db.engine.begin() as connection:
            connection.execute(insert_sql, payload)
    except Exception as e:
        print(f"Demo flight seed warning: {e}")


def auto_mark_landed_once():
    """Mark flights as landed when scheduled date+arrival time has passed."""
    now = datetime.now()
    flights = Flight.query.filter(Flight.Status.in_(['available', 'unavailable'])).all()

    updated = 0
    landed_flight_ids = []
    for flight in flights:
        try:
            scheduled_arrival = datetime.combine(flight.FlightDate, flight.ArrivalTime)
            if scheduled_arrival <= now:
                flight.Status = 'landed'
                updated += 1
                landed_flight_ids.append(flight.FlightID)
        except Exception:
            continue

    if updated > 0:
        db.session.commit()
        print(f"Auto-landed {updated} flight(s)")
        for flight_id in landed_flight_ids:
            trigger_miles_award_for_flight(flight_id)


def start_auto_landed_scheduler():
    def loop():
        while True:
            try:
                with app.app_context():
                    auto_mark_landed_once()
            except Exception as e:
                print(f"Auto-land scheduler warning: {e}")
            time.sleep(max(AUTO_LAND_INTERVAL_SECONDS, 10))

    worker = threading.Thread(target=loop, daemon=True)
    worker.start()


def trigger_miles_award_for_flight(flight_id):
    published = False

    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange=RABBITMQ_EXCHANGE, exchange_type='topic', durable=True)
        channel.basic_publish(
            exchange=RABBITMQ_EXCHANGE,
            routing_key=FLIGHT_LANDED_KEY,
            body=json.dumps({"flightID": flight_id, "force": False}),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        channel.close()
        connection.close()
        published = True
        print(f"Published flight.landed event for flight {flight_id}")
    except Exception as e:
        print(f"Miles award event publish warning for flight {flight_id}: {e}")

    if published:
        return

    # Fallback path to avoid losing awards if RabbitMQ publish fails.
    try:
        request_obj = urllib.request.Request(
            f"{MILES_AWARDING_COMPOSITE_URL}/award/flight/{flight_id}",
            data=json.dumps({"force": False}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            payload = json.loads(response.read().decode('utf-8') or '{}')
            print(f"Miles awarding fallback response for flight {flight_id}: {payload}")
    except Exception as e:
        print(f"Miles award fallback warning for flight {flight_id}: {e}")


@app.route('/health', methods=['GET'])
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "OK", "service": "flight-service"}), 200
    except Exception as e:
        return jsonify({"status": "ERROR", "service": "flight-service", "error": str(e)}), 503

# Flight Model
class Flight(db.Model):
    __tablename__ = 'flights'
    FlightID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FlightNumber = db.Column(db.String(10), nullable=False)
    Origin = db.Column(db.String(50), nullable=False)
    Destination = db.Column(db.String(50), nullable=False)
    FlightDate = db.Column(db.Date, nullable=False)
    DepartureTime = db.Column(db.Time, nullable=False)
    FlightDuration = db.Column(db.Time, nullable=False)
    ArrivalTime = db.Column(db.Time, nullable=False)
    Price = db.Column(db.Numeric(10, 2), nullable=False)
    Status = db.Column(db.Enum('available', 'unavailable', 'cancelled', 'landed'), default='available')
    CancellationReason = db.Column(db.String(255), nullable=True)
    Meals = db.Column(db.String(50), nullable=False)
    Beverages = db.Column(db.String(50), nullable=False)
    Wifi = db.Column(db.Boolean, nullable=False)
    Baggage = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        # Safely parse date
        date_str = self.FlightDate.strftime('%d/%m/%Y') if hasattr(self.FlightDate, 'strftime') else str(self.FlightDate)

        def format_time(t):
            if not t: return None
            if hasattr(t, 'strftime'): return t.strftime('%H:%M')
            if hasattr(t, 'seconds'):
                h, r = divmod(t.seconds, 3600)
                m, _ = divmod(r, 60)
                return f"{h:02d}:{m:02d}"
            return str(t)[:5]
            
        def format_duration(t):
            if not t: return None
            if hasattr(t, 'seconds'):
                h, r = divmod(t.seconds, 3600)
                m, _ = divmod(r, 60)
                return f"{h}:{m:02d}"
            if hasattr(t, 'hour') and hasattr(t, 'minute'):
                return f"{t.hour}:{t.minute:02d}"
            return str(t)

        return {
            'FlightID': self.FlightID,
            'FlightNumber': self.FlightNumber,
            'Origin': self.Origin,
            'Destination': self.Destination,
            'Date': date_str,
            'FlightDate': self.FlightDate.strftime('%Y-%m-%d') if hasattr(self.FlightDate, 'strftime') else str(self.FlightDate),
            'DepartureTime': format_time(self.DepartureTime),
            'FlightDuration': format_duration(self.FlightDuration),
            'ArrivalTime': format_time(self.ArrivalTime),
            'Price': float(self.Price) if self.Price else None,
            'Status': self.Status.capitalize() if self.Status else None,
            'CancellationReason': self.CancellationReason,
            'Meals': self.Meals,
            'Beverages': self.Beverages,
            'Wifi': self.Wifi,
            'Baggage': self.Baggage
        }


@app.route('/flight', methods=['GET'])
@app.route('/flights', methods=['GET'])
def get_flights():
    try:
        origin = request.args.get('origin')
        dest = request.args.get('dest')
        date = request.args.get('date')
        status = request.args.get('status')

        query = Flight.query

        if origin:
            query = query.filter(Flight.Origin == origin)
        if dest:
            query = query.filter(Flight.Destination == dest)
        if date:
            query = query.filter(Flight.FlightDate == date)
        if status:
            query = query.filter(Flight.Status == status.lower())

        flights = query.order_by(Flight.DepartureTime.asc()).all()
        return jsonify([f.to_dict() for f in flights]), 200
    except Exception as e:
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500


@app.route('/flights/<int:flight_id>', methods=['GET'])
def get_flight_v2(flight_id):
    return get_flight(flight_id)


@app.route('/flight/<int:flight_id>', methods=['PUT'])
@app.route('/flights/<int:flight_id>', methods=['PUT'])
def update_flight_v2(flight_id):
    try:
        data = request.get_json(silent=True) or {}
        status = data.get('Status') or data.get('status')
        cancellation_reason = data.get('CancellationReason')

        if not status:
            return jsonify({"message": "Status is required in request body"}), 400

        status = status.lower()
        if status not in ['available', 'unavailable', 'cancelled', 'landed']:
            return jsonify({"message": "Invalid status value"}), 400

        flight = Flight.query.get(flight_id)
        if not flight:
            return jsonify({"message": "Flight not found"}), 404

        previous_status = (flight.Status or '').lower()
        flight.Status = status
        if status == 'cancelled':
            flight.CancellationReason = cancellation_reason
        elif cancellation_reason is not None:
            flight.CancellationReason = cancellation_reason

        db.session.commit()

        if status == 'landed' and previous_status != 'landed':
            trigger_miles_award_for_flight(flight_id)

        return jsonify({
            "FlightID": flight.FlightID,
            "Status": flight.Status.capitalize(),
            "Origin": flight.Origin,
            "Destination": flight.Destination,
            "Date": flight.FlightDate.strftime('%Y-%m-%d') if hasattr(flight.FlightDate, 'strftime') else str(flight.FlightDate),
            "DepartureTime": flight.DepartureTime.strftime('%H:%M') if hasattr(flight.DepartureTime, 'strftime') else str(flight.DepartureTime)[:5],
            "CancellationReason": flight.CancellationReason
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500

@app.route('/flight/available', methods=['GET'])
def get_available_flights():
    try:
        origin = request.args.get('origin')
        dest = request.args.get('dest')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')

        query = Flight.query.filter(Flight.Status != 'cancelled').filter(Flight.Status != 'landed')

        if origin:
            query = query.filter(Flight.Origin == origin)
        if dest:
            query = query.filter(Flight.Destination == dest)
        if date_from:
            query = query.filter(Flight.FlightDate >= date_from)
        if date_to:
            query = query.filter(Flight.FlightDate <= date_to)

        flights = query.all()
        return jsonify([f.to_dict() for f in flights]), 200
    except Exception as e:
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500

@app.route('/flight/<int:flight_id>', methods=['GET'])
def get_flight(flight_id):
    try:
        flight = Flight.query.get(flight_id)
        if not flight:
            return jsonify({"message": "Flight not found"}), 404
        return jsonify(flight.to_dict()), 200
    except Exception as e:
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500

@app.route('/flight/<int:flight_id>/status', methods=['PUT'])
def update_flight_status(flight_id):
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({"message": "Status is required in request body"}), 400

        status = data['status'].lower() # Gracefully handle 'Cancelled' or 'cancelled'
        if status not in ['available', 'unavailable', 'cancelled', 'landed']:
            return jsonify({"message": "Invalid status value"}), 400

        flight = Flight.query.get(flight_id)
        if not flight:
            return jsonify({"message": "Flight not found"}), 404

        previous_status = (flight.Status or '').lower()
        flight.Status = status
        if status == 'cancelled' and 'CancellationReason' in data:
            flight.CancellationReason = data.get('CancellationReason')
        db.session.commit()

        if status == 'landed' and previous_status != 'landed':
            trigger_miles_award_for_flight(flight_id)

        return jsonify({"message": "Flight status updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500


@app.route('/flight/<int:flight_id>/landed', methods=['PUT'])
def mark_flight_landed(flight_id):
    try:
        flight = Flight.query.get(flight_id)
        if not flight:
            return jsonify({"message": "Flight not found"}), 404

        previous_status = (flight.Status or '').lower()
        flight.Status = 'landed'
        db.session.commit()

        if previous_status != 'landed':
            trigger_miles_award_for_flight(flight_id)

        return jsonify({
            "message": "Flight marked as landed",
            "flightID": flight.FlightID,
            "status": "Landed"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    with app.app_context():
        ensure_status_enum_allows_landed()
        ensure_demo_flights_seeded()
        if AUTO_LAND_ENABLED:
            start_auto_landed_scheduler()
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
