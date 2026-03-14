import os
import stripe
import pybreaker
import logging
import json
import hashlib
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_event(event, **kwargs):
    logger.info(json.dumps({
        "event":     event,
        "timestamp": get_sgt_now().isoformat(),
        **kwargs
    }))

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

db_user     = os.environ.get('DB_USER', 'root')
db_password = os.environ.get('DB_PASSWORD', 'rootpassword')
db_host     = os.environ.get('DB_HOST', 'localhost')
db_name     = os.environ.get('DB_NAME', 'paymentdb')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:3306/{db_name}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://"
)

stripe_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name="stripe"
)

@stripe_breaker
def stripe_create_charge(amount, currency, source, description, metadata, idempotency_key=None):
    """Wrapper around Stripe charge — protected by circuit breaker"""
    kwargs = dict(amount=amount, currency=currency, source=source,
                  description=description, metadata=metadata)
    if idempotency_key:
        kwargs['idempotency_key'] = idempotency_key
    return stripe.Charge.create(**kwargs)

@stripe_breaker
def stripe_create_refund(charge, amount, reason, metadata, idempotency_key=None):
    """Wrapper around Stripe refund — protected by circuit breaker"""
    kwargs = dict(charge=charge, amount=amount, reason=reason, metadata=metadata)
    if idempotency_key:
        kwargs['idempotency_key'] = idempotency_key
    return stripe.Refund.create(**kwargs)

sgt_tz = timezone(timedelta(hours=8))

def get_sgt_now():
    return datetime.now(sgt_tz)

STRIPE_MIN_AMOUNT = 0.50    # Stripe minimum charge - SGD $0.50
MAX_AMOUNT        = 10000   # Maximum single transaction — SGD $10,000
REFUND_WINDOW     = 180     # Stripe only allows refunds within 180 days

class Payment(db.Model):
    __tablename__ = 'payment'

    paymentID          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bookingID          = db.Column(db.Integer, nullable=False)
    passengerID        = db.Column(db.Integer, nullable=False)
    amount             = db.Column(db.Float, nullable=False)
    status             = db.Column(db.String(50), nullable=False)  # 'Completed', 'Refunded', 'Failed'
    stripeChargeID     = db.Column(db.String(100), nullable=True)
    refundID           = db.Column(db.String(100), nullable=True)
    idempotencyKey     = db.Column(db.String(100), nullable=True, unique=True)
    cancellationReason = db.Column(db.String(255), nullable=True)
    chargedAt          = db.Column(db.DateTime, nullable=True)
    refundedAt         = db.Column(db.DateTime, nullable=True)
    createdAt          = db.Column(db.DateTime, default=get_sgt_now)

    def json(self):
        return {
            "paymentID":          self.paymentID,
            "bookingID":          self.bookingID,
            "passengerID":        self.passengerID,
            "amount":             self.amount,
            "status":             self.status,
            "stripeChargeID":     self.stripeChargeID,
            "refundID":           self.refundID,
            "idempotencyKey":     self.idempotencyKey,
            "cancellationReason": self.cancellationReason,
            "chargedAt":          str(self.chargedAt) if self.chargedAt else None,
            "refundedAt":         str(self.refundedAt) if self.refundedAt else None,
            "createdAt":          str(self.createdAt),
        }


# ==========================================
# HELPERS
# ==========================================
def validate_fields(data, required_fields):
    """Check all required fields exist and are not None or empty string"""
    missing = [
        f for f in required_fields
        if f not in data or data[f] is None or data[f] == ""
    ]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None

def generate_idempotency_key(booking_id, passenger_id, amount, prefix="pay"):
    today = get_sgt_now().strftime("%Y%m%d")
    raw = f"{prefix}-{booking_id}-{passenger_id}-{amount}-{today}"
    return hashlib.md5(raw.encode()).hexdigest()

def to_stripe_cents(amount):
    """Safely convert float amount to Stripe cents, avoiding float precision bugs.
    e.g. 299.99 * 100 can give 29998.999... — round() fixes this."""
    return round(int(round(amount * 100)))

# ==========================================
# GET /payment
# Get all payments
# ==========================================
@app.route('/payment', methods=['GET'])
@limiter.limit("60 per minute")
def get_all_payments():
    payments = Payment.query.order_by(Payment.createdAt.desc()).all()
    return jsonify([p.json() for p in payments]), 200

# ==========================================
# GET /payment/<paymentID>
# Get a specific payment by paymentID
# ==========================================
@app.route('/payment/<int:paymentID>', methods=['GET'])
@limiter.limit("60 per minute")
def get_payment(paymentID):
    payment = Payment.query.filter_by(paymentID=paymentID).first()
    if not payment:
        return jsonify({
            "error":   "Not Found",
            "code":    "PAYMENT_NOT_FOUND",
            "message": f"Payment {paymentID} not found"
        }), 404
    return jsonify(payment.json()), 200

# ==========================================
# POST /payment
# Process a new payment
# Used in: Scenario 1 - Book Flight
# ==========================================
@app.route('/payment', methods=['POST'])
@limiter.limit("10 per minute")
def process_payment():
    try:
        data = request.get_json()

        # Validate required fields — also catches empty strings
        error = validate_fields(data, ['bookingID', 'passengerID', 'amount', 'flightNumber'])
        if error:
            return jsonify({
                "error":   "Bad Request",
                "code":    "MISSING_FIELDS",
                "message": error
            }), 400

        booking_id   = data.get('bookingID')
        passenger_id = data.get('passengerID')
        amount       = data.get('amount')
        stripe_token = data.get('stripeToken', 'tok_visa')

        # Validate field types
        if not isinstance(booking_id, int) or not isinstance(passenger_id, int):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "bookingID and passengerID must be integers"
            }), 400

        if not isinstance(amount, (int, float)):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "amount must be a number"
            }), 400

        # Validate amount range
        # Edge case: amount must be above zero
        if amount <= 0:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_AMOUNT",
                "message": "Amount must be greater than 0"
            }), 400

        # Edge case: Stripe minimum charge is SGD $0.50
        if amount < STRIPE_MIN_AMOUNT:
            return jsonify({
                "error":   "Bad Request",
                "code":    "AMOUNT_TOO_SMALL",
                "message": f"Minimum charge amount is SGD ${STRIPE_MIN_AMOUNT:.2f}"
            }), 400

        # Edge case: cap very large amounts to prevent mistakes
        if amount > MAX_AMOUNT:
            return jsonify({
                "error":   "Bad Request",
                "code":    "AMOUNT_TOO_LARGE",
                "message": f"Maximum charge amount is SGD ${MAX_AMOUNT:.2f}"
            }), 400

        # Auto-generate idempotency key — client sends nothing extra
        idempotency_key = generate_idempotency_key(booking_id, passenger_id, amount, prefix="pay")

        # Edge case: idempotency — same request retried, return original payment
        existing_by_key = Payment.query.filter_by(idempotencyKey=idempotency_key).first()
        if existing_by_key:
            log_event("idempotent_payment_returned", bookingID=booking_id)
            return jsonify({
                **existing_by_key.json(),
                "message": "Payment already completed. No duplicate charge was made."
            }), 200

        # Edge case: prevent duplicate payments for same booking
        existing_payment = Payment.query.filter_by(
            bookingID=booking_id,
            status="Completed"
        ).first()
        if existing_payment:
            return jsonify({
                "error":     "Conflict",
                "code":      "DUPLICATE_PAYMENT",
                "message":   f"BookingID {booking_id} has already been paid",
                "paymentID": existing_payment.paymentID
            }), 409

        flight_number   = data.get('flightNumber', 'N/A')
        charge_time_str = get_sgt_now().strftime("%Y-%m-%d %H:%M:%S SGT")

        log_event("payment_initiated", bookingID=booking_id, amount=amount)

        # Circuit breaker - call Stripe through the breaker
        try:
            stripe_charge = stripe_create_charge(
                amount      = to_stripe_cents(amount),  # edge case: float precision fix
                currency    = 'sgd',
                source      = stripe_token,
                description = f"Flight {flight_number} | Booking {booking_id} | {charge_time_str}",
                metadata    = {
                    "booking_id":    booking_id,
                    "passenger_id":  passenger_id,
                    "flight_number": flight_number,
                    "charged_at":    charge_time_str
                },
                idempotency_key=idempotency_key
            )
        except pybreaker.CircuitBreakerError:
            log_event("circuit_breaker_open", service="stripe")
            return jsonify({
                "error":   "Service Unavailable",
                "code":    "STRIPE_CIRCUIT_OPEN",
                "message": "Payment service is temporarily unavailable. Please try again in 30 seconds."
            }), 503

        # Save payment record
        new_payment = Payment(
            bookingID      = booking_id,
            passengerID    = passenger_id,
            amount         = amount,
            status         = "Completed",
            stripeChargeID = stripe_charge.id,
            idempotencyKey = idempotency_key,
            chargedAt      = get_sgt_now()
        )
        db.session.add(new_payment)
        db.session.commit()

        log_event("payment_completed",
                  bookingID=booking_id,
                  paymentID=new_payment.paymentID,
                  stripeChargeID=stripe_charge.id)

        return jsonify({
            "paymentID":      new_payment.paymentID,
            "stripeChargeID": stripe_charge.id,
            "status":         "Completed"
        }), 201

    except stripe.error.StripeError as e:
        db.session.rollback()
        log_event("payment_stripe_error", bookingID=data.get('bookingID'), error=str(e))
        return jsonify({
            "error":   "Card Declined",
            "code":    "CARD_DECLINED",
            "message": str(e)
        }), 402
    except Exception as e:
        db.session.rollback()
        log_event("payment_error", error=str(e))
        return jsonify({
            "error":   "Internal Server Error",
            "code":    "INTERNAL_ERROR",
            "message": str(e)
        }), 500


# ==========================================
# POST /payment/refund
# Process a full or partial refund
# Used in: Scenario 2 Path B - No Alternative Flight
#          Scenario 3 - Passenger rejects offer (partial)
# ==========================================
@app.route('/payment/refund', methods=['POST'])
@limiter.limit("10 per minute")
def process_refund():
    try:
        data = request.get_json()

        # Validate required fields
        error = validate_fields(data, ['bookingID', 'passengerID', 'amount', 'flightNumber'])
        if error:
            return jsonify({
                "error":   "Bad Request",
                "code":    "MISSING_FIELDS",
                "message": error
            }), 400

        booking_id   = data.get('bookingID')
        passenger_id = data.get('passengerID')
        amount       = data.get('amount')
        reason       = data.get('reason', 'FlightCancelled')
        refund_type  = data.get('refundType', 'full')

        # Validate field types
        if not isinstance(booking_id, int) or not isinstance(passenger_id, int):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "bookingID and passengerID must be integers"
            }), 400

        if not isinstance(amount, (int, float)):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "amount must be a number"
            }), 400

        # Validate amount - no minimum for refunds, only check above zero
        if amount <= 0:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_AMOUNT",
                "message": "Refund amount must be greater than 0"
            }), 400

        # Validate refund type
        if refund_type not in ['full', 'partial']:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_REFUND_TYPE",
                "message": "refundType must be 'full' or 'partial'"
            }), 400

        # For partial refund, validate refundAmount
        if refund_type == 'partial':
            refund_amount = data.get('refundAmount')
            if refund_amount is None or refund_amount == "":
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "MISSING_REFUND_AMOUNT",
                    "message": "refundAmount is required for partial refunds"
                }), 400
            if not isinstance(refund_amount, (int, float)) or refund_amount <= 0:
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "INVALID_REFUND_AMOUNT",
                    "message": "refundAmount must be a number greater than 0"
                }), 400
            # Edge case: partial refund cannot exceed what was originally paid
            if refund_amount > amount:
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "REFUND_EXCEEDS_PAYMENT",
                    "message": f"refundAmount ${refund_amount} cannot exceed original payment ${amount}"
                }), 400
        else:
            refund_amount = amount

        # Auto-generate idempotency key
        idempotency_key = generate_idempotency_key(booking_id, passenger_id, amount, prefix="ref")

        # Edge case: idempotency — same refund request retried, return original
        existing_by_key = Payment.query.filter_by(idempotencyKey=idempotency_key).first()
        if existing_by_key and existing_by_key.status == "Refunded":
            log_event("idempotent_refund_returned", bookingID=booking_id)
            return jsonify({
                "refundID": existing_by_key.refundID,
                "status":   "Refunded",
                "message": "Refund already completed. No duplicate refund was made."
            }), 200

        # Edge case: prevent double refunds
        already_refunded = Payment.query.filter_by(
            bookingID=booking_id,
            status="Refunded"
        ).first()
        if already_refunded:
            return jsonify({
                "error":    "Conflict",
                "code":     "DUPLICATE_REFUND",
                "message":  f"BookingID {booking_id} has already been refunded",
                "refundID": already_refunded.refundID
            }), 409

        # Look up original payment - with row lock to prevent race conditions
        # Edge case: concurrent requests both pass duplicate check before either commits
        original_payment = Payment.query.filter_by(
            bookingID=booking_id,
            status="Completed"
        ).with_for_update().order_by(Payment.paymentID.desc()).first()

        if not original_payment:
            return jsonify({
                "error":   "Not Found",
                "code":    "PAYMENT_NOT_FOUND",
                "message": f"No completed payment found for bookingID {booking_id}"
            }), 404

        if not original_payment.stripeChargeID:
            return jsonify({
                "error":   "Not Found",
                "code":    "STRIPE_CHARGE_NOT_FOUND",
                "message": "No Stripe charge found for this booking"
            }), 404

        # Edge case: passenger ID mismatch
        # Ensure the passenger requesting the refund matches the original payment
        if original_payment.passengerID != passenger_id:
            log_event("passenger_mismatch",
                      bookingID=booking_id,
                      expectedPassengerID=original_payment.passengerID,
                      receivedPassengerID=passenger_id)
            return jsonify({
                "error":   "Forbidden",
                "code":    "PASSENGER_MISMATCH",
                "message": "passengerID does not match the original payment record"
            }), 403

        # Edge case: amount mismatch - refund amount exceeds what was originally paid
        if refund_amount > original_payment.amount:
            return jsonify({
                "error":   "Bad Request",
                "code":    "REFUND_EXCEEDS_ORIGINAL",
                "message": f"Refund amount ${refund_amount:.2f} exceeds original payment ${original_payment.amount:.2f}"
            }), 400

        # Edge case: Stripe only allows refunds within 180 days of original charge
        if original_payment.chargedAt:
            charged_at_aware = original_payment.chargedAt.replace(tzinfo=sgt_tz)
            days_since_charge = (get_sgt_now() - charged_at_aware).days
            if days_since_charge > REFUND_WINDOW:
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "REFUND_WINDOW_EXPIRED",
                    "message": f"Refunds are only allowed within {REFUND_WINDOW} days of payment. This payment was {days_since_charge} days ago."
                }), 400

        refund_time_str = get_sgt_now().strftime("%Y-%m-%d %H:%M:%S SGT")

        log_event("refund_initiated",
                  bookingID=booking_id,
                  amount=refund_amount,
                  refundType=refund_type)

        # Circuit breaker - call Stripe through the breaker
        try:
            stripe_refund = stripe_create_refund(
                charge   = original_payment.stripeChargeID,
                amount   = to_stripe_cents(refund_amount),
                reason   = 'requested_by_customer',
                metadata = {
                    "cancellation_reason": reason,
                    "booking_id":          booking_id,
                    "refund_type":         refund_type,
                    "refunded_at":         refund_time_str
                },
                idempotency_key=idempotency_key
            )
        except pybreaker.CircuitBreakerError:
            log_event("circuit_breaker_open", service="stripe")
            return jsonify({
                "error":   "Service Unavailable",
                "code":    "STRIPE_CIRCUIT_OPEN",
                "message": "Refund service is temporarily unavailable. Please try again in 30 seconds."
            }), 503

        # Update original payment record
        original_payment.status             = "Refunded"
        original_payment.refundID           = stripe_refund.id
        original_payment.refundedAt         = get_sgt_now()
        original_payment.cancellationReason = reason
        original_payment.idempotencyKey     = idempotency_key
        db.session.commit()

        log_event("refund_completed", bookingID=booking_id, refundID=stripe_refund.id)

        return jsonify({
            "refundID":           stripe_refund.id,
            "status":             "Refunded",
            "bookingID":          booking_id,
            "passengerID":        passenger_id,
            "amount":             refund_amount,
            "refundType":         refund_type,
            "cancellationReason": reason,
            "refundedAt":         get_sgt_now().strftime("%Y-%m-%d %H:%M:%S SGT"),
            "stripeStatus":       stripe_refund.status
        }), 200

    except stripe.error.StripeError as e:
        db.session.rollback()
        log_event("refund_stripe_error", bookingID=data.get('bookingID'), error=str(e))
        return jsonify({
            "error":   "Stripe Gateway Error",
            "code":    "STRIPE_ERROR",
            "message": str(e)
        }), 502
    except Exception as e:
        db.session.rollback()
        log_event("refund_error", error=str(e))
        return jsonify({
            "error":   "Internal Server Error",
            "code":    "INTERNAL_ERROR",
            "message": str(e)
        }), 500

# GET /payment/refund/<refundID>
# Get refund details by refundID
@app.route('/payment/refund/<string:refundID>', methods=['GET'])
@limiter.limit("60 per minute")
def get_refund(refundID):
    refund = Payment.query.filter_by(refundID=refundID).first()
    if not refund:
        return jsonify({
            "error":   "Not Found",
            "code":    "REFUND_NOT_FOUND",
            "message": f"Refund {refundID} not found"
        }), 404
    return jsonify(refund.json()), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)