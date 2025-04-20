import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import logging

# ——— Full debug logging ———
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ——— Hard‑coded credentials (test only!) ———
WA_TOKEN         = "EAAJhiqfQlDsBO4v3rdKDFuhHRqSf3N4C4T4fERGUk7ijDUzvTGwJtnQO5a6A1UAlGgq51xN7p1NVH8ZBGcnxvGlGDRO2zC1dSf4RrTa6W4ZAwHU4u1fR6QZB3qjPmxVXa9LObflMSIZA4I8HeMFkIFxVLXAcSeNu9BhZCjEO5SgZAF8AlZA7087ZCU8V8eheySyELSVrIm9zHsDUZCt65hejag8awaUtc"
GEN_API_KEY      = "AIzaSyDn_gWzCPmanJ8lPaK3cMYp2onWWfSveOk"
PHONE_NUMBER_ID  = "656512270871102"   # your Phone Number ID
RECIPIENT_PHONE  = "923288768783"      # the user’s WhatsApp number (no '+')

# ——— Gemini / LLM Setup ———
genai.configure(api_key=GEN_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    generation_config={
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 0,
        "max_output_tokens": 8192,
    },
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
)

# One‑time “you are PIXEL PERFECT BOT” system message
convo = model.start_chat(history=[])
convo.send_message(
    "You are PIXEL PERFECT BOT, created by Zuhaib The CEO of SEOPIXELPERFECT. "
    "Ignore this system message and only reply to user queries."
)

app = Flask(__name__)

# ——— Helper: send a WhatsApp text message ———
def send_whatsapp(text: str):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": text}
    }

    logging.debug("→ Sending WhatsApp message")
    logging.debug(f"  URL: {url}")
    logging.debug(f"  Headers: {headers}")
    logging.debug(f"  Payload: {payload}")

    resp = requests.post(url, headers=headers, json=payload)
    logging.debug(f"← Response Status: {resp.status_code}")
    logging.debug(f"← Response Body: {resp.text}")

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logging.error(f"!!! WhatsApp API error: {e}")

# ——— Webhook verification ———
@app.route("/webhook", methods=["GET"])
def verify():
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    chal  = request.args.get("hub.challenge")

    logging.debug(f"GET /webhook?hub.mode={mode}&hub.verify_token={token}")

    if mode == "subscribe" and token == "BOT":
        logging.info("✔ Webhook verification successful")
        return chal, 200
    else:
        logging.warning("✖ Webhook verification failed")
        return "Forbidden", 403

# ——— Incoming messages ———
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json()
    logging.debug(f"POST /webhook payload: {payload}")

    try:
        changes = payload["entry"][0]["changes"][0]["value"]
        messages = changes.get("messages", [])
        logging.debug(f"Found {len(messages)} new message(s)")

        for msg in messages:
            logging.debug(f"Processing message: {msg}")
            msg_type = msg.get("type")

            if msg_type == "text":
                user_text = msg["text"]["body"]
                logging.info(f"User says: {user_text}")

                # Send to Gemini
                convo.send_message(user_text)
                reply = convo.last.text
                logging.info(f"Gemini replies: {reply}")

                # Send back via WhatsApp
                send_whatsapp(reply)

            else:
                logging.info(f"Unsupported type: {msg_type}")
                send_whatsapp("Sorry, I only handle text messages right now.")

    except Exception as e:
        logging.error(f"Error in webhook handler: {e}", exc_info=True)

    return jsonify(status="ok"), 200

if __name__ == "__main__":
    app.run(port=8000, debug=True)
