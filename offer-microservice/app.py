import os
import logging
import json
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import exc, text
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "OK", "service": "offer-service"}), 200

# ==========================================
# LOGGING HELPER
# ==========================================
def log_event(event, **kwargs):
    logger.info(json.dumps({
        "event":     event,
        "timestamp": get_sgt_now().isoformat(),
        **kwargs
    }))


# ==========================================
# DATABASE CONFIG
# ==========================================
db_user     = os.environ.get('DB_USER',     'root')
db_password = os.environ.get('DB_PASSWORD', 'rootpassword')
db_host     = os.environ.get('DB_HOST',     'localhost')
db_name     = os.environ.get('DB_NAME',     'offerdb')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:3306/{db_name}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

sgt_tz = timezone(timedelta(hours=8))

def get_sgt_now():
    return datetime.now(sgt_tz)

# ==========================================
# CONSTANTS
# ==========================================
VALID_STATUSES = [
    'Pending Response',
    'Accepted',
    'Rejected',
    'Expired',
]

FINAL_STATUSES    = ['Accepted', 'Rejected', 'Expired']
OFFER_EXPIRY_HOURS = 24   # Path A offers expire after 24 hours

# ==========================================
# DATABASE MODEL
# ==========================================
class Offer(db.Model):
    __tablename__ = 'offer'

    offerID      = db.Column(db.Integer,  primary_key=True, autoincrement=True)
    bookingID    = db.Column(db.Integer,  nullable=False)   # FK → Booking DB
    passengerID  = db.Column(db.Integer,  nullable=False)   # FK → Passenger DB
    origFlightID = db.Column(db.Integer,  nullable=False)   # FK → Flight DB (cancelled)
    newFlightID  = db.Column(db.Integer,  nullable=True)    # FK → Flight DB (alternative); always populated since Offer is Path A only
    newSeatID    = db.Column(db.Integer,  nullable=True)    # logical Seat Service reference
    # fareDiff removed — airline absorbs all fare differences per disruption policy
    status       = db.Column(db.String(50),  nullable=False, default='Pending Response')
    expiryTime   = db.Column(db.DateTime,    nullable=True)  # now+24h for Path A offers
    respondedAt  = db.Column(db.DateTime,    nullable=True)  # timestamp when passenger accepted/rejected; NULL if not yet responded or expired
    isDeleted    = db.Column(db.Boolean,     nullable=False, default=False)  # soft delete — never hard delete for audit trail
    createdTime  = db.Column(db.DateTime,    default=get_sgt_now)
    updatedTime  = db.Column(db.DateTime,    nullable=True,  onupdate=get_sgt_now)

    def json(self):
        return {
            'offerID':      self.offerID,
            'bookingID':    self.bookingID,
            'passengerID':  self.passengerID,
            'origFlightID': self.origFlightID,
            'newFlightID':  self.newFlightID,
            'newSeatID':    self.newSeatID,
            'status':       self.status,
            'expiryTime':   self.expiryTime.strftime("%Y-%m-%d %H:%M:%S SGT")  if self.expiryTime  else None,
            'respondedAt':  self.respondedAt.strftime("%Y-%m-%d %H:%M:%S SGT") if self.respondedAt else None,
            'createdTime':  self.createdTime.strftime("%Y-%m-%d %H:%M:%S SGT") if self.createdTime else None,
            'updatedTime':  self.updatedTime.strftime("%Y-%m-%d %H:%M:%S SGT") if self.updatedTime else None,
        }

# ==========================================
# HELPERS
# ==========================================
def validate_fields(data, required_fields):
    """Check all required fields exist and are not None or empty string"""
    if not data:
        return "Request body is missing or not valid JSON"
    missing = [
        f for f in required_fields
        if f not in data or data[f] is None or data[f] == ''
    ]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None

def check_and_expire(offer):
    """
    Auto-expire offer if expiryTime has passed and status is still Pending Response.
    Commits the change if expired.
    """
    if (
        offer.status == 'Pending Response'
        and offer.expiryTime is not None
    ):
        expiry_aware = offer.expiryTime.replace(tzinfo=sgt_tz)
        if get_sgt_now() > expiry_aware:
            offer.status = 'Expired'
            offer.updatedTime = get_sgt_now()
            db.session.commit()
            log_event("offer_auto_expired", offerID=offer.offerID)
    return offer

# ==========================================
# GET /offer
# Get all offers with optional filters
#
# Query params:
#   passengerID  — filter by passenger
#   bookingID    — filter by booking (Scenario 3)
#   origFlightID — filter by cancelled flight (Rebooking Composite)
#   status        — filter by status
#   limit        — pagination (default 50, max 200)
#   offset       — pagination (default 0)
# ==========================================
@app.route('/offer', methods=['GET'])
@app.route('/offers', methods=['GET'])
def get_all_offers():
    log_event("get_all_offers_request")
    try:
        passenger_id   = request.args.get('passengerID',  type=int)
        booking_id     = request.args.get('bookingID',    type=int)
        orig_flight_id = request.args.get('origFlightID', type=int)
        status         = request.args.get('status')
        limit          = request.args.get('limit',  default=50,  type=int)
        offset         = request.args.get('offset', default=0,   type=int)

        # Validate status filter if provided
        if status and status not in VALID_STATUSES:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_STATUS',
                'message': f"status must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        # Validate pagination
        if limit < 1 or limit > 200:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_PAGINATION',
                'message': 'limit must be between 1 and 200'
            }), 400

        # Build query — exclude soft-deleted
        query = Offer.query.filter_by(isDeleted=False)

        if passenger_id:
            query = query.filter_by(passengerID=passenger_id)
        if booking_id:
            query = query.filter_by(bookingID=booking_id)
        if orig_flight_id:
            query = query.filter_by(origFlightID=orig_flight_id)
        if status:
            query = query.filter_by(status=status)

        offers = query.order_by(Offer.createdTime.desc()).limit(limit).offset(offset).all()

        # Auto-expire any offers that have passed expiryTime
        results = []
        for o in offers:
            o = check_and_expire(o)
            results.append(o.json())

        log_event("get_all_offers_success", count=len(results))
        return jsonify(results), 200

    except exc.OperationalError as e:
        log_event("db_connection_error", error=str(e))
        return jsonify({
            'error':   'Service Unavailable',
            'code':    'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        log_event("get_all_offers_error", error=str(e))
        return jsonify({
            'error':   'Internal Server Error',
            'code':    'INTERNAL_ERROR',
            'message': str(e)
        }), 500

# ==========================================
# GET /offer/<offerID>
# Get a specific offer — auto-expires if past expiryTime
# ==========================================
@app.route('/offer/<int:offerID>', methods=['GET'])
@app.route('/offers/<int:offerID>', methods=['GET'])
def get_offer(offerID):
    log_event("get_offer_request", offerID=offerID)
    try:
        offer = Offer.query.filter_by(offerID=offerID, isDeleted=False).first()

        if not offer:
            return jsonify({
                'error':   'Not Found',
                'code':    'OFFER_NOT_FOUND',
                'message': f'Offer {offerID} not found'
            }), 404

        offer = check_and_expire(offer)

        log_event("get_offer_success", offerID=offerID, status=offer.status)
        return jsonify(offer.json()), 200

    except exc.OperationalError as e:
        log_event("db_connection_error", error=str(e))
        return jsonify({
            'error':   'Service Unavailable',
            'code':    'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        log_event("get_offer_error", offerID=offerID, error=str(e))
        return jsonify({
            'error':   'Internal Server Error',
            'code':    'INTERNAL_ERROR',
            'message': str(e)
        }), 500

# ==========================================
# POST /offer
# Create a new offer record
# Called by: Rebooking Composite (Path A and Path B)
#
# Required: bookingID, passengerID, origFlightID, status
# Optional: newFlightID, expiryTime
#
# Edge cases:
#   - Non-JSON / empty body                          → 400 INVALID_JSON
#   - Missing required fields                        → 400 MISSING_FIELDS
#   - Invalid field types                            → 400 INVALID_FIELD_TYPE
#   - Invalid status                                 → 400 INVALID_STATUS
#   - Pending Response without newFlightID           → 400 MISSING_NEW_FLIGHT

#   - Invalid expiryTime format                      → 400 INVALID_EXPIRY_TIME
#   - Duplicate offer same bookingID + origFlightID  → 409 DUPLICATE_OFFER
#   - FK constraint violation                        → 400 INTEGRITY_ERROR
#   - DB connection failure                          → 503 DB_CONNECTION_ERROR
# ==========================================
@app.route('/offer', methods=['POST'])
@app.route('/offers', methods=['POST'])
def create_offer():
    log_event("create_offer_request")
    try:
        # ── Guard: valid JSON ─────────────────────────────────────────
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_JSON',
                'message': 'Request body must be valid JSON'
            }), 400

        # ── Validate required fields ──────────────────────────────────
        booking_id     = data.get('bookingID', data.get('BookingID'))
        passenger_id   = data.get('passengerID', data.get('PassengerID'))
        orig_flight_id = data.get('origFlightID', data.get('OrigFlightID'))
        new_flight_id  = data.get('newFlightID', data.get('NewFlightID', None))
        new_seat_id    = data.get('newSeatID', data.get('NewSeatID', None))
        status         = data.get('status', data.get('Status', 'Pending Response'))
        expiry_time    = data.get('expiryTime', data.get('ExpiryTime', None))

        payload_for_validation = {
            'bookingID': booking_id,
            'passengerID': passenger_id,
            'origFlightID': orig_flight_id,
            'status': status,
        }

        error = validate_fields(payload_for_validation, ['bookingID', 'passengerID', 'origFlightID', 'status'])
        if error:
            return jsonify({
                'error':   'Bad Request',
                'code':    'MISSING_FIELDS',
                'message': error
            }), 400

        # ── Validate field types ──────────────────────────────────────
        if not isinstance(booking_id, int) or booking_id <= 0:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_FIELD_TYPE',
                'message': 'bookingID must be a positive integer'
            }), 400

        if not isinstance(passenger_id, int) or passenger_id <= 0:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_FIELD_TYPE',
                'message': 'passengerID must be a positive integer'
            }), 400

        if not isinstance(orig_flight_id, int) or orig_flight_id <= 0:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_FIELD_TYPE',
                'message': 'origFlightID must be a positive integer'
            }), 400

        if new_flight_id is not None and (not isinstance(new_flight_id, int) or new_flight_id <= 0):
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_FIELD_TYPE',
                'message': 'newFlightID must be a positive integer'
            }), 400

        if new_seat_id is not None and (not isinstance(new_seat_id, int) or new_seat_id <= 0):
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_FIELD_TYPE',
                'message': 'newSeatID must be a positive integer'
            }), 400

        # ── Validate status ─────────────────────────────────────────
        if status not in VALID_STATUSES:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_STATUS',
                'message': f"status must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        # ── Path A: newFlightID required if Pending Response ──────────
        if status == 'Pending Response' and not new_flight_id:
            return jsonify({
                'error':   'Bad Request',
                'code':    'MISSING_NEW_FLIGHT',
                'message': 'newFlightID is required when status is Pending Response'
            }), 400

        # ── Check for duplicate offer same bookingID + origFlightID ───
        existing = Offer.query.filter_by(
            bookingID=booking_id,
            origFlightID=orig_flight_id,
            isDeleted=False
        ).first()
        if existing:
            return jsonify({
                'error':       'Conflict',
                'code':        'DUPLICATE_OFFER',
                'message':     f'An offer already exists for bookingID {booking_id} and origFlightID {orig_flight_id}',
                'offerID':     existing.offerID,
                'status': existing.status
            }), 409

        # ── Parse / auto-calculate expiryTime ─────────────────────────
        parsed_expiry = None
        if status == 'Pending Response':
            if expiry_time:
                try:
                    parsed_expiry = datetime.fromisoformat(expiry_time)
                except ValueError:
                    return jsonify({
                        'error':   'Bad Request',
                        'code':    'INVALID_EXPIRY_TIME',
                        'message': 'expiryTime must be ISO 8601 format e.g. 2025-03-10T09:15:22'
                    }), 400
            else:
                # Auto-calculate now + 24h in SGT
                parsed_expiry = get_sgt_now() + timedelta(hours=OFFER_EXPIRY_HOURS)
                log_event("expiry_auto_calculated",
                          bookingID=booking_id,
                          expiryTime=str(parsed_expiry))

        # ── Create offer ──────────────────────────────────────────────
        new_offer = Offer(
            bookingID    = booking_id,
            passengerID  = passenger_id,
            origFlightID = orig_flight_id,
            newFlightID  = new_flight_id,
            newSeatID    = new_seat_id,
            status       = status,
            expiryTime   = parsed_expiry
        )

        db.session.add(new_offer)
        db.session.commit()

        log_event("create_offer_success",
                  offerID=new_offer.offerID,
                  bookingID=booking_id,
                  status=status)

        return jsonify({
            **new_offer.json(),
            'OfferID': new_offer.offerID,
            'Status': new_offer.status,
            'message': 'Offer created successfully'
        }), 201

    except exc.IntegrityError as e:
        db.session.rollback()
        log_event("create_offer_integrity_error", error=str(e))
        return jsonify({
            'error':   'Bad Request',
            'code':    'INTEGRITY_ERROR',
            'message': 'One or more FK references are invalid (bookingID, passengerID, origFlightID or newFlightID not found)'
        }), 400

    except exc.OperationalError as e:
        db.session.rollback()
        log_event("db_connection_error", error=str(e))
        return jsonify({
            'error':   'Service Unavailable',
            'code':    'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        db.session.rollback()
        log_event("create_offer_error", error=str(e))
        return jsonify({
            'error':   'Internal Server Error',
            'code':    'INTERNAL_ERROR',
            'message': str(e)
        }), 500

# ==========================================
# PUT /offer/<offerID>
# Update offer status
# Called by: Rebooking Composite (Scenario 3)
#
# Required: status
# Edge cases:
#   - Non-JSON / empty body          → 400 INVALID_JSON
#   - Missing status                 → 400 MISSING_FIELDS
#   - Invalid status                 → 400 INVALID_STATUS
#   - Offer not found / soft-deleted → 404 OFFER_NOT_FOUND
#   - Offer already finalised        → 409 OFFER_ALREADY_FINALISED
#   - Offer auto-expired on read     → 409 OFFER_ALREADY_FINALISED
#   - Concurrent update race         → row lock via with_for_update()
#   - DB connection failure          → 503 DB_CONNECTION_ERROR
# ==========================================
@app.route('/offer/<int:offerID>', methods=['PUT'])
@app.route('/offers/<int:offerID>', methods=['PUT'])
def update_offer(offerID):
    log_event("update_offer_request", offerID=offerID)
    try:
        # ── Guard: valid JSON ─────────────────────────────────────────
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_JSON',
                'message': 'Request body must be valid JSON'
            }), 400

        status = data.get('status')

        # ── Validate status ─────────────────────────────────────────
        if not status:
            return jsonify({
                'error':   'Bad Request',
                'code':    'MISSING_FIELDS',
                'message': 'status is required'
            }), 400

        if status not in VALID_STATUSES:
            return jsonify({
                'error':   'Bad Request',
                'code':    'INVALID_STATUS',
                'message': f"status must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        # ── Row lock — prevent concurrent accept/reject race condition ──
        offer = Offer.query.filter_by(
            offerID=offerID,
            isDeleted=False
        ).with_for_update().first()

        if not offer:
            return jsonify({
                'error':   'Not Found',
                'code':    'OFFER_NOT_FOUND',
                'message': f'Offer {offerID} not found'
            }), 404

        # ── Auto-expire check before updating ────────────────────────
        offer = check_and_expire(offer)

        # ── Cannot update already finalised offer ─────────────────────
        if offer.status in FINAL_STATUSES:
            return jsonify({
                'error':   'Conflict',
                'code':    'OFFER_ALREADY_FINALISED',
                'message': f'Offer {offerID} is already {offer.status} and cannot be updated'
            }), 409

        # ── Update ────────────────────────────────────────────────────
        offer.status      = status
        offer.updatedTime = get_sgt_now()

        # Populate respondedAt when passenger makes a decision
        if status in ['Accepted', 'Rejected']:
            offer.respondedAt = get_sgt_now()

        db.session.commit()

        log_event("update_offer_success", offerID=offerID, status=status)

        return jsonify({
            **offer.json(),
            'message': 'Offer updated successfully'
        }), 200

    except exc.OperationalError as e:
        db.session.rollback()
        log_event("db_connection_error", error=str(e))
        return jsonify({
            'error':   'Service Unavailable',
            'code':    'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        db.session.rollback()
        log_event("update_offer_error", offerID=offerID, error=str(e))
        return jsonify({
            'error':   'Internal Server Error',
            'code':    'INTERNAL_ERROR',
            'message': str(e)
        }), 500

# ==========================================
# DELETE /offer/<offerID>
# Soft delete — marks isDeleted=True
# Does NOT permanently remove (preserves audit trail)
# ==========================================
@app.route('/offer/<int:offerID>', methods=['DELETE'])
@app.route('/offers/<int:offerID>', methods=['DELETE'])
def delete_offer(offerID):
    log_event("delete_offer_request", offerID=offerID)
    try:
        offer = Offer.query.filter_by(offerID=offerID, isDeleted=False).first()

        if not offer:
            return jsonify({
                'error':   'Not Found',
                'code':    'OFFER_NOT_FOUND',
                'message': f'Offer {offerID} not found'
            }), 404

        offer.isDeleted  = True
        offer.updatedTime = get_sgt_now()
        db.session.commit()

        log_event("delete_offer_success", offerID=offerID)

        return jsonify({
            'message': f'Offer {offerID} deleted successfully'
        }), 200

    except exc.OperationalError as e:
        db.session.rollback()
        log_event("db_connection_error", error=str(e))
        return jsonify({
            'error':   'Service Unavailable',
            'code':    'DB_CONNECTION_ERROR',
            'message': 'Could not connect to the database. Please try again later.'
        }), 503

    except Exception as e:
        db.session.rollback()
        log_event("delete_offer_error", offerID=offerID, error=str(e))
        return jsonify({
            'error':   'Internal Server Error',
            'code':    'INTERNAL_ERROR',
            'message': str(e)
        }), 500


import time

def drop_legacy_coupon_column():
    """
    Remove the old coupon-era column from existing local databases.
    """
    legacy_column = db.session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'offer'
              AND COLUMN_NAME = 'couponID'
            LIMIT 1
            """
        )
    ).scalar()

    if legacy_column:
        logger.info("Dropping legacy couponID column from offer table")
        db.session.execute(text("ALTER TABLE offer DROP COLUMN couponID"))
        db.session.commit()

def wait_for_db(retries=10, delay=3):
    for i in range(retries):
        try:
            with app.app_context():
                db.create_all()
                drop_legacy_coupon_column()
            print('✓ Connected to offer-db')
            return
        except Exception as e:
            print(f'DB not ready, retrying in {delay}s... ({retries - i - 1} retries left)')
            time.sleep(delay)
    print('Could not connect to database after multiple retries. Exiting.')
    exit(1)

if __name__ == '__main__':
    wait_for_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
