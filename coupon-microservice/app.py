import os
import json
import logging
import random
import string
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sgt_now():
    sgt_tz = timezone(timedelta(hours=8))
    return datetime.now(sgt_tz)


def log_event(event, **kwargs):
    logger.info(json.dumps({
        "event": event,
        "timestamp": get_sgt_now().isoformat(),
        **kwargs
    }))


# ==========================================
# DATABASE CONFIG
# ==========================================
db_user = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'rootpassword')
db_host = os.environ.get('DB_HOST', 'localhost')
db_name = os.environ.get('DB_NAME', 'coupondb')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:3306/{db_name}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ==========================================
# DATABASE MODEL
# ==========================================
class Coupon(db.Model):
    __tablename__ = 'coupon'

    CouponID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CouponCode = db.Column(db.String(12), nullable=False, unique=True)
    DiscountAmount = db.Column(db.Numeric(10, 2), nullable=False)
    IsUsed = db.Column(db.Boolean, nullable=False, default=False)
    UsedAt = db.Column(db.DateTime, nullable=True)
    ExpiryDate = db.Column(db.DateTime, nullable=False)
    CreatedTime = db.Column(db.DateTime, nullable=False, default=get_sgt_now)

    def json(self):
        return {
            'CouponID': self.CouponID,
            'CouponCode': self.CouponCode,
            'DiscountAmount': float(self.DiscountAmount),
            'IsUsed': self.IsUsed,
            'UsedAt': self.UsedAt.isoformat() if self.UsedAt else None,
            'ExpiryDate': self.ExpiryDate.isoformat() if self.ExpiryDate else None,
            'CreatedTime': self.CreatedTime.isoformat() if self.CreatedTime else None
        }


# ==========================================
# HELPERS
# ==========================================
def validate_fields(data, required_fields):
    if not data:
        return "Request body is missing or not valid JSON"

    missing = [
        f for f in required_fields
        if f not in data or data[f] is None or data[f] == ''
    ]

    if missing:
        return f"Missing required fields: {', '.join(missing)}"

    return None


def calculate_discount_amount(flight_price, hours_until_departure):
    if hours_until_departure > 72:
        discount_rate = 0.05
    elif hours_until_departure > 24:
        discount_rate = 0.10
    else:
        discount_rate = 0.20

    return round(flight_price * discount_rate, 2)


def generate_coupon_code():
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BLAZE-{random_suffix}"


def create_unique_coupon_code(max_attempts=10):
    for _ in range(max_attempts):
        code = generate_coupon_code()
        existing = Coupon.query.filter_by(CouponCode=code).first()
        if not existing:
            return code
    raise RuntimeError("Unable to generate a unique coupon code")


def is_expired(coupon):
    expiry = coupon.ExpiryDate
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone(timedelta(hours=8)))
    return get_sgt_now() > expiry


# ==========================================
# GET /health
# ==========================================
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK', 'service': 'coupon-service'}), 200


# ==========================================
# POST /coupons
# Create a coupon
# Input: flightPrice, hoursUntilDeparture
# ==========================================
@app.route('/coupons', methods=['POST'])
def create_coupon():
    log_event('create_coupon_request')
    try:
        data = request.get_json(silent=True)

        error = validate_fields(data, ['flightPrice', 'hoursUntilDeparture'])
        if error:
            return jsonify({
                'error': 'Bad Request',
                'code': 'MISSING_FIELDS',
                'message': error
            }), 400

        flight_price = data.get('flightPrice')
        hours_until_departure = data.get('hoursUntilDeparture')

        if not isinstance(flight_price, (int, float)):
            return jsonify({
                'error': 'Bad Request',
                'code': 'INVALID_FIELD_TYPE',
                'message': 'flightPrice must be a number'
            }), 400

        if not isinstance(hours_until_departure, (int, float)):
            return jsonify({
                'error': 'Bad Request',
                'code': 'INVALID_FIELD_TYPE',
                'message': 'hoursUntilDeparture must be a number'
            }), 400

        if flight_price <= 0:
            return jsonify({
                'error': 'Bad Request',
                'code': 'INVALID_FLIGHT_PRICE',
                'message': 'flightPrice must be greater than 0'
            }), 400

        if hours_until_departure < 0:
            return jsonify({
                'error': 'Bad Request',
                'code': 'INVALID_HOURS_UNTIL_DEPARTURE',
                'message': 'hoursUntilDeparture cannot be negative'
            }), 400

        now = get_sgt_now()
        expiry_date = now + timedelta(days=730)
        discount_amount = calculate_discount_amount(float(flight_price), float(hours_until_departure))

        retries = 3
        new_coupon = None

        for _ in range(retries):
            coupon_code = create_unique_coupon_code()
            new_coupon = Coupon(
                CouponCode=coupon_code,
                DiscountAmount=discount_amount,
                IsUsed=False,
                UsedAt=None,
                ExpiryDate=expiry_date,
                CreatedTime=now
            )

            db.session.add(new_coupon)
            try:
                db.session.commit()
                break
            except exc.IntegrityError:
                db.session.rollback()
                new_coupon = None
                continue

        if not new_coupon:
            return jsonify({
                'error': 'Internal Server Error',
                'code': 'COUPON_CODE_GENERATION_FAILED',
                'message': 'Unable to generate a unique coupon code. Please retry.'
            }), 500

        log_event('create_coupon_success', couponCode=new_coupon.CouponCode)
        return jsonify(new_coupon.json()), 201

    except exc.OperationalError as e:
        log_event('db_connection_error', error=str(e))
        return jsonify({
            'error': 'Service Unavailable',
            'code': 'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        db.session.rollback()
        log_event('create_coupon_error', error=str(e))
        return jsonify({
            'error': 'Internal Server Error',
            'code': 'INTERNAL_ERROR',
            'message': str(e)
        }), 500


# ==========================================
# GET /coupons/<coupon_code>
# Retrieve coupon details
# ==========================================
@app.route('/coupons/<string:coupon_code>', methods=['GET'])
def get_coupon(coupon_code):
    log_event('get_coupon_request', couponCode=coupon_code)

    try:
        coupon = Coupon.query.filter_by(CouponCode=coupon_code).first()
        if not coupon:
            return jsonify({
                'error': 'Not Found',
                'code': 'COUPON_NOT_FOUND',
                'message': f'Coupon {coupon_code} not found'
            }), 404

        log_event('get_coupon_success', couponCode=coupon_code)
        return jsonify(coupon.json()), 200

    except exc.OperationalError as e:
        log_event('db_connection_error', error=str(e))
        return jsonify({
            'error': 'Service Unavailable',
            'code': 'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        log_event('get_coupon_error', couponCode=coupon_code, error=str(e))
        return jsonify({
            'error': 'Internal Server Error',
            'code': 'INTERNAL_ERROR',
            'message': str(e)
        }), 500


# ==========================================
# PUT /coupons/<coupon_code>/redeem
# Mark coupon as used
# ==========================================
@app.route('/coupons/<string:coupon_code>/redeem', methods=['PUT'])
def redeem_coupon(coupon_code):
    log_event('redeem_coupon_request', couponCode=coupon_code)

    try:
        coupon = Coupon.query.filter_by(CouponCode=coupon_code).first()
        if not coupon:
            return jsonify({
                'error': 'Not Found',
                'code': 'COUPON_NOT_FOUND',
                'message': f'Coupon {coupon_code} not found'
            }), 404

        if coupon.IsUsed:
            return jsonify({
                'error': 'Conflict',
                'code': 'COUPON_ALREADY_USED',
                'message': f'Coupon {coupon_code} has already been used'
            }), 409

        if is_expired(coupon):
            return jsonify({
                'error': 'Bad Request',
                'code': 'COUPON_EXPIRED',
                'message': f'Coupon {coupon_code} has expired'
            }), 400

        coupon.IsUsed = True
        coupon.UsedAt = get_sgt_now()
        db.session.commit()

        log_event('redeem_coupon_success', couponCode=coupon_code)
        return jsonify(coupon.json()), 200

    except exc.OperationalError as e:
        db.session.rollback()
        log_event('db_connection_error', error=str(e))
        return jsonify({
            'error': 'Service Unavailable',
            'code': 'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        db.session.rollback()
        log_event('redeem_coupon_error', couponCode=coupon_code, error=str(e))
        return jsonify({
            'error': 'Internal Server Error',
            'code': 'INTERNAL_ERROR',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
