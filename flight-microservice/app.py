import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    Status = db.Column(db.Enum('available', 'unavailable', 'cancelled'), default='available')
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
            'DepartureTime': format_time(self.DepartureTime),
            'FlightDuration': format_duration(self.FlightDuration),
            'ArrivalTime': format_time(self.ArrivalTime),
            'Price': float(self.Price) if self.Price else None,
            'Status': self.Status.capitalize() if self.Status else None,
            'Meals': self.Meals,
            'Beverages': self.Beverages,
            'Wifi': self.Wifi,
            'Baggage': self.Baggage
        }

@app.route('/flight/available', methods=['GET'])
def get_available_flights():
    try:
        origin = request.args.get('origin')
        dest = request.args.get('dest')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')

        query = Flight.query.filter(Flight.Status != 'cancelled')

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
        if status not in ['available', 'unavailable', 'cancelled']:
            return jsonify({"message": "Invalid status value"}), 400

        flight = Flight.query.get(flight_id)
        if not flight:
            return jsonify({"message": "Flight not found"}), 404

        flight.Status = status
        db.session.commit()

        return jsonify({"message": "Flight status updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
