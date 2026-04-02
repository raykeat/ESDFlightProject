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

db_user     = os.environ.get('DB_USER',     'root')
db_password = os.environ.get('DB_PASSWORD', 'rootpassword')
db_host     = os.environ.get('DB_HOST',     'localhost')
db_name     = os.environ.get('DB_NAME',     'paymentdb')

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
def stripe_create_checkout_session(line_items, metadata, success_url, cancel_url, idempotency_key=None):
    """Wrapper around Stripe Checkout Session creation — protected by circuit breaker"""
    kwargs = dict(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata
    )
    if idempotency_key:
        kwargs['idempotency_key'] = idempotency_key
    return stripe.checkout.Session.create(**kwargs)

@stripe_breaker
def stripe_retrieve_session(session_id):
    """Retrieve a Stripe Checkout Session — protected by circuit breaker"""
    return stripe.checkout.Session.retrieve(session_id)

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

STRIPE_MIN_AMOUNT = 0.50
MAX_AMOUNT        = 10000
REFUND_WINDOW     = 180

# ==========================================
# DATABASE MODEL
# ==========================================
class Payment(db.Model):
    __tablename__ = 'payment'

    paymentID          = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    bookingID          = db.Column(db.Integer,     nullable=False)
    passengerID        = db.Column(db.Integer,     nullable=False)
    amount             = db.Column(db.Float,       nullable=False)
    status             = db.Column(db.String(50),  nullable=False)   # 'Pending', 'Completed', 'Refunded', 'Failed'
    stripeSessionID    = db.Column(db.String(200), nullable=True)    # Stripe Checkout Session ID (cs_...)
    stripeChargeID     = db.Column(db.String(100), nullable=True)    # Stripe Charge ID — populated after verify-session
    refundID           = db.Column(db.String(100), nullable=True)    # Stripe Refund ID (re_...)
    idempotencyKey     = db.Column(db.String(100), nullable=True, unique=True)
    cancellationReason = db.Column(db.String(255), nullable=True)
    chargedAt          = db.Column(db.DateTime,    nullable=True)
    refundedAt         = db.Column(db.DateTime,    nullable=True)
    createdAt          = db.Column(db.DateTime,    default=get_sgt_now)

    def json(self):
        return {
            "paymentID":          self.paymentID,
            "bookingID":          self.bookingID,
            "passengerID":        self.passengerID,
            "amount":             self.amount,
            "status":             self.status,
            "stripeSessionID":    self.stripeSessionID,
            "stripeChargeID":     self.stripeChargeID,
            "refundID":           self.refundID,
            "idempotencyKey":     self.idempotencyKey,
            "cancellationReason": self.cancellationReason,
            "chargedAt":          str(self.chargedAt)  if self.chargedAt  else None,
            "refundedAt":         str(self.refundedAt) if self.refundedAt else None,
            "createdAt":          str(self.createdAt),
        }


# ==========================================
# HELPERS
# ==========================================
def validate_fields(data, required_fields):
    if not data:
        return "Request body is missing or not valid JSON"
    missing = [
        f for f in required_fields
        if f not in data or data[f] is None or data[f] == ""
    ]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None

def generate_idempotency_key(booking_id, passenger_id, amount, prefix="pay"):
    # Include seconds to avoid conflicts when retrying with same params on same day
    now = get_sgt_now().strftime("%Y%m%d%H%M%S")
    raw = f"{prefix}-{booking_id}-{passenger_id}-{amount}-{now}"
    return hashlib.md5(raw.encode()).hexdigest()

def to_stripe_cents(amount):
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
# POST /payment/checkout
# Create a Stripe Checkout Session
# Used in: Scenario 1 - Book Flight
#
# Flow:
#   1. Booking Composite calls this endpoint
#   2. Payment Service creates a Stripe Checkout Session
#   3. Returns sessionUrl to Composite → UI
#   4. UI redirects passenger to Stripe's hosted payment page
#   5. Passenger pays on Stripe, gets redirected to successUrl
#   6. BookingSuccess page calls GET /payment/verify-session/<sessionID>
#      to confirm payment and update status to Completed
# ==========================================
@app.route('/payment/checkout', methods=['POST'])
@limiter.limit("10 per minute")
def create_checkout_session():
    try:
        data = request.get_json(silent=True)

        error = validate_fields(data, ['bookingID', 'passengerID', 'amount', 'flightNumber'])
        if error:
            return jsonify({
                "error":   "Bad Request",
                "code":    "MISSING_FIELDS",
                "message": error
            }), 400

        booking_id    = data.get('bookingID')
        user_booking_count = data.get('userBookingCount', booking_id)
        passenger_id  = data.get('passengerID')
        amount        = data.get('amount')
        flight_number = data.get('flightNumber')
        success_url   = data.get('successUrl', f"http://localhost:5173/booking-success/{booking_id}?session_id={{CHECKOUT_SESSION_ID}}")
        cancel_url    = data.get('cancelUrl',  "http://localhost:5173/booking-confirmation")

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

        if amount <= 0:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_AMOUNT",
                "message": "Amount must be greater than 0"
            }), 400

        if amount < STRIPE_MIN_AMOUNT:
            return jsonify({
                "error":   "Bad Request",
                "code":    "AMOUNT_TOO_SMALL",
                "message": f"Minimum charge amount is SGD ${STRIPE_MIN_AMOUNT:.2f}"
            }), 400

        if amount > MAX_AMOUNT:
            return jsonify({
                "error":   "Bad Request",
                "code":    "AMOUNT_TOO_LARGE",
                "message": f"Maximum charge amount is SGD ${MAX_AMOUNT:.2f}"
            }), 400

        idempotency_key = generate_idempotency_key(booking_id, passenger_id, amount, prefix="pay")

        existing_by_key = Payment.query.filter_by(idempotencyKey=idempotency_key).first()
        if existing_by_key and existing_by_key.status == "Completed":
            log_event("idempotent_payment_returned", bookingID=booking_id)
            return jsonify({
                **existing_by_key.json(),
                "message": "Payment already completed. No duplicate charge was made."
            }), 200

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

        log_event("checkout_session_initiated", bookingID=booking_id, amount=amount)

        try:
            session = stripe_create_checkout_session(
                line_items=[{
                    'price_data': {
                        'currency': 'sgd',
                        'unit_amount': to_stripe_cents(amount),
                        'product_data': {
                            'name':        f'Flight {flight_number}',
                            'description': f'Booking #{user_booking_count} — Seat included',
                        },
                    },
                    'quantity': 1,
                }],
                metadata={
                    'booking_id':    str(booking_id),
                    'user_booking_count': str(user_booking_count),
                    'passenger_id':  str(passenger_id),
                    'flight_number': flight_number,
                },
                success_url=success_url,
                cancel_url=cancel_url,
                idempotency_key=idempotency_key
            )
        except pybreaker.CircuitBreakerError:
            log_event("circuit_breaker_open", service="stripe")
            return jsonify({
                "error":   "Service Unavailable",
                "code":    "STRIPE_CIRCUIT_OPEN",
                "message": "Payment service is temporarily unavailable. Please try again in 30 seconds."
            }), 503

        new_payment = Payment(
            bookingID       = booking_id,
            passengerID     = passenger_id,
            amount          = amount,
            status          = "Pending",
            stripeSessionID = session.id,
            idempotencyKey  = idempotency_key,
        )
        db.session.add(new_payment)
        db.session.commit()

        log_event("checkout_session_created",
                  bookingID=booking_id,
                  paymentID=new_payment.paymentID,
                  stripeSessionID=session.id)

        return jsonify({
            "paymentID":       new_payment.paymentID,
            "stripeSessionID": session.id,
            "sessionUrl":      session.url,
            "status":          "Pending"
        }), 201

    except stripe.error.StripeError as e:
        db.session.rollback()
        log_event("checkout_stripe_error", bookingID=data.get('bookingID'), error=str(e))
        return jsonify({
            "error":   "Stripe Error",
            "code":    "STRIPE_ERROR",
            "message": str(e)
        }), 502
    except Exception as e:
        db.session.rollback()
        log_event("checkout_error", error=str(e))
        return jsonify({
            "error":   "Internal Server Error",
            "code":    "INTERNAL_ERROR",
            "message": str(e)
        }), 500


# ==========================================
# GET /payment/verify-session/<sessionID>
# Called by BookingSuccess page after Stripe redirects back.
# Retrieves the Stripe session, confirms payment_status is 'paid',
# then updates our payment record to Completed.
# No webhook needed — passenger's browser triggers this directly.
# ==========================================
@app.route('/payment/verify-session/<string:sessionID>', methods=['GET'])
@limiter.limit("30 per minute")
def verify_session(sessionID):
    try:
        # Check our DB first — avoid unnecessary Stripe API calls
        payment = Payment.query.filter_by(stripeSessionID=sessionID).first()
        if not payment:
            return jsonify({
                "error":   "Not Found",
                "code":    "PAYMENT_NOT_FOUND",
                "message": f"No payment found for session {sessionID}"
            }), 404

        # Already confirmed — return immediately
        if payment.status == "Completed":
            log_event("verify_session_already_completed", stripeSessionID=sessionID)
            return jsonify({
                **payment.json(),
                "message": "Payment already verified"
            }), 200

        # Ask Stripe for the current session status
        try:
            session = stripe_retrieve_session(sessionID)
        except pybreaker.CircuitBreakerError:
            log_event("circuit_breaker_open", service="stripe")
            return jsonify({
                "error":   "Service Unavailable",
                "code":    "STRIPE_CIRCUIT_OPEN",
                "message": "Payment verification temporarily unavailable. Please try again shortly."
            }), 503

        if session.payment_status != 'paid':
            # Payment not completed yet — return current status
            return jsonify({
                "paymentID":      payment.paymentID,
                "bookingID":      payment.bookingID,
                "status":         "Pending",
                "stripeStatus":   session.payment_status,
                "message":        "Payment not yet completed"
            }), 202

        # Payment confirmed — get charge ID from payment intent
        charge_id = None
        if session.payment_intent:
            try:
                intent    = stripe.PaymentIntent.retrieve(session.payment_intent)
                charge_id = intent.get('latest_charge')
            except Exception:
                pass  # Charge ID is nice-to-have, not critical

        # Update payment record to Completed
        payment.status         = "Completed"
        payment.stripeChargeID = charge_id
        payment.chargedAt      = get_sgt_now()
        db.session.commit()

        log_event("payment_verified_and_completed",
                  bookingID=payment.bookingID,
                  paymentID=payment.paymentID,
                  stripeSessionID=sessionID)

        return jsonify({
            **payment.json(),
            "message": "Payment verified and confirmed"
        }), 200

    except stripe.error.StripeError as e:
        log_event("verify_session_stripe_error", stripeSessionID=sessionID, error=str(e))
        return jsonify({
            "error":   "Stripe Error",
            "code":    "STRIPE_ERROR",
            "message": str(e)
        }), 502
    except Exception as e:
        db.session.rollback()
        log_event("verify_session_error", stripeSessionID=sessionID, error=str(e))
        return jsonify({
            "error":   "Internal Server Error",
            "code":    "INTERNAL_ERROR",
            "message": str(e)
        }), 500


# ==========================================
# POST /payment/refund
# Process a full or partial refund
# Used in: Scenario 2 Path B - No Alternative Flight
#          Scenario 3 - Passenger rejects offer
# ==========================================
@app.route('/payment/refund', methods=['POST'])
@app.route('/payments/refund', methods=['POST'])
@limiter.limit("10 per minute")
def process_refund():
    try:
        data = request.get_json(silent=True)

        booking_id = data.get('bookingID', data.get('BookingID')) if data else None
        passenger_id = data.get('passengerID', data.get('PassengerID')) if data else None

        error = validate_fields(
            {
                'bookingID': booking_id,
                'passengerID': passenger_id,
            },
            ['bookingID', 'passengerID']
        )
        if error:
            return jsonify({
                "error":   "Bad Request",
                "code":    "MISSING_FIELDS",
                "message": error
            }), 400

        amount       = data.get('amount', data.get('Amount'))
        reason       = data.get('reason', 'FlightCancelled')
        refund_type  = data.get('refundType', 'full')

        if not isinstance(booking_id, int) or not isinstance(passenger_id, int):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "bookingID and passengerID must be integers"
            }), 400

        if refund_type not in ['full', 'partial']:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_REFUND_TYPE",
                "message": "refundType must be 'full' or 'partial'"
            }), 400

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

        original_payment = Payment.query.filter_by(
            bookingID=booking_id,
            status="Completed"
        ).with_for_update().order_by(Payment.paymentID.desc()).first()

        if not original_payment:
            original_payment = Payment.query.filter_by(
                passengerID=passenger_id,
                status="Completed"
            ).with_for_update().order_by(Payment.paymentID.desc()).first()

        if not original_payment:
            return jsonify({
                "error":   "Not Found",
                "code":    "PAYMENT_NOT_FOUND",
                "message": f"No completed payment found for bookingID {booking_id}"
            }), 404

        if amount is None:
            amount = float(original_payment.amount)

        if not isinstance(amount, (int, float)):
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_FIELD_TYPE",
                "message": "amount must be a number"
            }), 400

        if amount <= 0:
            return jsonify({
                "error":   "Bad Request",
                "code":    "INVALID_AMOUNT",
                "message": "Refund amount must be greater than 0"
            }), 400

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
            if refund_amount > amount:
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "REFUND_EXCEEDS_PAYMENT",
                    "message": f"refundAmount ${refund_amount} cannot exceed original payment ${amount}"
                }), 400
        else:
            refund_amount = amount

        idempotency_key = generate_idempotency_key(booking_id, passenger_id, amount, prefix="ref")

        existing_by_key = Payment.query.filter_by(idempotencyKey=idempotency_key).first()
        if existing_by_key and existing_by_key.status == "Refunded":
            log_event("idempotent_refund_returned", bookingID=booking_id)
            return jsonify({
                "refundID": existing_by_key.refundID,
                "status":   "Refunded",
                "message":  "Refund already completed. No duplicate refund was made."
            }), 200

        if not original_payment.stripeChargeID:
            return jsonify({
                "error":   "Not Found",
                "code":    "STRIPE_CHARGE_NOT_FOUND",
                "message": "No Stripe charge found for this booking"
            }), 404

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

        if refund_amount > original_payment.amount:
            return jsonify({
                "error":   "Bad Request",
                "code":    "REFUND_EXCEEDS_ORIGINAL",
                "message": f"Refund amount ${refund_amount:.2f} exceeds original payment ${original_payment.amount:.2f}"
            }), 400

        if original_payment.chargedAt:
            charged_at_aware  = original_payment.chargedAt.replace(tzinfo=sgt_tz)
            days_since_charge = (get_sgt_now() - charged_at_aware).days
            if days_since_charge > REFUND_WINDOW:
                return jsonify({
                    "error":   "Bad Request",
                    "code":    "REFUND_WINDOW_EXPIRED",
                    "message": f"Refunds are only allowed within {REFUND_WINDOW} days of payment. This payment was {days_since_charge} days ago."
                }), 400

        refund_time_str = get_sgt_now().strftime("%Y-%m-%d %H:%M:%S SGT")
        log_event("refund_initiated", bookingID=booking_id, amount=refund_amount, refundType=refund_type)

        try:
            stripe_refund = stripe_create_refund(
                charge          = original_payment.stripeChargeID,
                amount          = to_stripe_cents(refund_amount),
                reason          = 'requested_by_customer',
                metadata        = {
                    "cancellation_reason": reason,
                    "booking_id":          booking_id,
                    "refund_type":         refund_type,
                    "refunded_at":         refund_time_str
                },
                idempotency_key = idempotency_key
            )
        except pybreaker.CircuitBreakerError:
            log_event("circuit_breaker_open", service="stripe")
            return jsonify({
                "error":   "Service Unavailable",
                "code":    "STRIPE_CIRCUIT_OPEN",
                "message": "Refund service is temporarily unavailable. Please try again in 30 seconds."
            }), 503

        refund_timestamp = get_sgt_now()

        if original_payment.bookingID == booking_id and refund_type == 'full':
            original_payment.status             = "Refunded"
            original_payment.refundID           = stripe_refund.id
            original_payment.refundedAt         = refund_timestamp
            original_payment.cancellationReason = reason
            original_payment.idempotencyKey     = idempotency_key
        else:
            refund_record = Payment(
                bookingID=booking_id,
                passengerID=passenger_id,
                amount=refund_amount,
                status="Refunded",
                stripeSessionID=original_payment.stripeSessionID,
                stripeChargeID=original_payment.stripeChargeID,
                refundID=stripe_refund.id,
                idempotencyKey=idempotency_key,
                chargedAt=original_payment.chargedAt,
                refundedAt=refund_timestamp,
                cancellationReason=reason,
            )
            db.session.add(refund_record)
        db.session.commit()

        log_event("refund_completed", bookingID=booking_id, refundID=stripe_refund.id)

        return jsonify({
            "refundID":           stripe_refund.id,
            "status":             "Refunded",
            "bookingID":          booking_id,
            "passengerID":        passenger_id,
            "amount":             refund_amount,
            "PaymentID":          original_payment.paymentID,
            "Status":             "Refunded",
            "RefundID":           stripe_refund.id,
            "RefundAmount":       refund_amount,
            "refundType":         refund_type,
            "cancellationReason": reason,
            "refundedAt":         refund_timestamp.strftime("%Y-%m-%d %H:%M:%S SGT"),
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


# ==========================================
# GET /payment/refund/<refundID>
# Get refund details by refundID
# ==========================================
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


import time

def wait_for_db(retries=10, delay=3):
    for i in range(retries):
        try:
            with app.app_context():
                db.create_all()
            print('✓ Connected to payment-db')
            return
        except Exception as e:
            print(f'DB not ready, retrying in {delay}s... ({retries - i - 1} retries left)')
            time.sleep(delay)
    print('Could not connect to database after multiple retries. Exiting.')
    exit(1)

if __name__ == '__main__':
    wait_for_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
