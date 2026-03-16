"""
Email Service — Atomic Microservice
=====================================
Single responsibility: send emails via SendGrid.
Called by the Notification Composite via HTTP POST.
 
Usage:
    python app.py
"""
 
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To
 
load_dotenv()
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
 
app = Flask(__name__)
CORS(app)
 
 
# =============================================================================
# HEALTH CHECK
# =============================================================================
 
@app.get("/health")
def health():
    return {"status": "UP", "service": "email-service"}, 200
 
 
# =============================================================================
# SEND EMAIL ENDPOINT
# =============================================================================
 
@app.post("/send-email")
def send_email():
    """
    Accepts an email request from the Notification Composite
    and sends it via SendGrid.
 
    Body:
        to_email    (str) — recipient email address
        to_name     (str) — recipient display name
        subject     (str) — email subject
        html        (str) — HTML email body
        text        (str) — plain text fallback
    """
    body = request.get_json(force=True) or {}
 
    # Validate required fields
    required = ["to_email", "to_name", "subject", "html", "text"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({
            "success": False,
            "errors": [f"'{f}' is required" for f in missing]
        }), 400
 
    to_email = body["to_email"]
    to_name  = body["to_name"]
    subject  = body["subject"]
    html     = body["html"]
    text     = body["text"]
 
    # Send via SendGrid
    try:
        client = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
        message = Mail(
            from_email=From(
                os.environ["SENDGRID_FROM_EMAIL"],
                os.environ["SENDGRID_FROM_NAME"]
            ),
            to_emails=To(to_email, to_name),
            subject=subject,
            html_content=html,
            plain_text_content=text,
        )
        response = client.send(message)
        message_id = response.headers.get("X-Message-Id", "")
        logger.info("Email sent to %s | status=%s | id=%s", to_email, response.status_code, message_id)
        return jsonify({
            "success": True,
            "message_id": message_id
        }), 200
 
    except Exception as e:
        logger.error("SendGrid error for %s: %s", to_email, str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 502
 
 
# =============================================================================
# ENTRY POINT
# =============================================================================
 
if __name__ == "__main__":
    port  = int(os.environ.get("FLASK_PORT", 3005))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
 