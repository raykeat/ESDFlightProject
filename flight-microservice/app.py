import os
import time
import threading
import json
import urllib.request
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
    try:
        request_obj = urllib.request.Request(
            f"{BOOKING_COMPOSITE_URL}/api/flights/{flight_id}/award-miles",
            data=json.dumps({"force": False}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            payload = json.loads(response.read().decode('utf-8') or '{}')
            print(f"Award miles response for flight {flight_id}: {payload}")
    except Exception as e:
        print(f"Miles award trigger warning for flight {flight_id}: {e}")


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "OK", "service": "flight-service"}), 200

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
        if AUTO_LAND_ENABLED:
            start_auto_landed_scheduler()
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
