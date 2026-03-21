"""
Flight Search Composite Service
================================
Scenario 1 — Step 2: View selected flight details + seat map (Synchronous)

Orchestrates:
1. GET flight details from Flight Service
2. GET seat map from Seats Service
   (both called in parallel via ThreadPoolExecutor)
3. Return merged response to Passenger UI

Endpoints:
    GET /flight-search/<flightID>  — Fetch flight + seats for selected flight
    GET /health                    — Health check
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, jsonify
from flask_cors import CORS

# ==========================================
# APP SETUP
# ==========================================
app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ==========================================
# SERVICE URLs — from environment variables
# ==========================================
FLIGHT_SERVICE_URL = os.environ.get("FLIGHT_SERVICE_URL", "http://localhost:3003")
SEATS_SERVICE_URL  = os.environ.get("SEATS_SERVICE_URL",  "http://localhost:5003")


# ==========================================
# GET /health
# ==========================================
@app.get("/health")
def health():
    return jsonify({
        "status":  "UP",
        "service": "flight-search-composite",
    }), 200


# ==========================================
# GET /flight-search/<flightID>
#
# Fans out to:
#   - Flight Service: GET /flight/<flightID>
#   - Seats Service:  GET /seats/<flightID>
# Both are called in parallel.
# Returns combined JSON to the UI.
# ==========================================
@app.get("/flight-search/<int:flight_id>")
def flight_search(flight_id):
    logger.info("flight_search requested for flightID=%d", flight_id)

    flight_data = None
    seats_data  = None
    flight_error = None
    seats_error  = None

    def get_flight():
        try:
            res = requests.get(
                f"{FLIGHT_SERVICE_URL}/flight/{flight_id}",
                timeout=10,
            )
            return ("flight", res)
        except requests.exceptions.RequestException as e:
            return ("flight_error", str(e))

    def get_seats():
        try:
            res = requests.get(
                f"{SEATS_SERVICE_URL}/seats/{flight_id}",
                timeout=10,
            )
            return ("seats", res)
        except requests.exceptions.RequestException as e:
            return ("seats_error", str(e))

    # ── Fan-out both requests in parallel ────────────────────
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(get_flight), executor.submit(get_seats)]
        for future in as_completed(futures):
            label, result = future.result()

            if label == "flight":
                if result.status_code == 404:
                    return jsonify({
                        "error":   "Not Found",
                        "code":    "FLIGHT_NOT_FOUND",
                        "message": f"Flight {flight_id} not found",
                    }), 404
                if not result.ok:
                    return jsonify({
                        "error":   "Service Error",
                        "code":    "FLIGHT_SERVICE_ERROR",
                        "message": f"Flight Service returned {result.status_code}",
                    }), 502
                flight_data = result.json()

            elif label == "flight_error":
                flight_error = result

            elif label == "seats":
                if result.ok:
                    seats_data = result.json()
                else:
                    # Non-fatal: return empty seats rather than failing
                    logger.warning(
                        "Seats Service returned %d for flightID=%d",
                        result.status_code, flight_id
                    )
                    seats_data = []

            elif label == "seats_error":
                # Non-fatal: return empty seats rather than failing
                logger.warning(
                    "Seats Service unreachable for flightID=%d: %s",
                    flight_id, result
                )
                seats_data = []

    # If flight service itself was unreachable, fail hard
    if flight_error and flight_data is None:
        return jsonify({
            "error":   "Service Unavailable",
            "code":    "FLIGHT_SERVICE_UNREACHABLE",
            "message": f"Could not reach Flight Service: {flight_error}",
        }), 503

    logger.info(
        "flight_search complete: flightID=%d, seats=%d",
        flight_id, len(seats_data) if seats_data else 0
    )

    return jsonify({
        "flight": flight_data,
        "seats":  seats_data if seats_data is not None else [],
    }), 200


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5011))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
