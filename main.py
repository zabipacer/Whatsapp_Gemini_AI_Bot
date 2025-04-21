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
WA_TOKEN               = "EAAJhiqfQlDsBO0nGiOerizJQbkZB1Nf5gGtZA5YgH3jF16SU8ul5EynCYZAAf9nwKfj8ChkAdPLemwsDZAKjAFenDTXLYeSrV7MUD5cBWhwzaAr8DvSsQqvdiiR9O400n0gr9ZCJQOfxMMU4ZAzEsvhNgDCeihnUoCi5BBhRjbW5ZBiFM3uZBB0vuSjTj43C1GDquP1P4tvdLZCfLEE3u3bGFIikhZApMZD"
GEN_API_KEY            = "AIzaSyDn_gWzCPmanJ8lPaK3cMYp2onWWfSveOk"
PHONE_NUMBER_ID        = "624016890796102"  # your WhatsApp Phone Number ID
WHATSAPP_BUSINESS_ID   = "678742774561887"  # WhatsApp Business Account ID

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

# One‑time “system” message to define bot persona
convo = model.start_chat(history=[])

convo.send_message(
    """
    You are PIXEL PERFECT BOT, the official customer‑service assistant for SEOPIXELPERFECT (https://seopixelperfect.com). You have full knowledge of our SEO service tiers—Starter, Basic, Professional, and Enterprise—as described on our Packages page (https://seopixelperfect.com/seo-packages-in-pakistan-2/). Whenever a customer asks about features, pricing, deliverables, or timelines, you will:

    1. Greet them warmly and thank them for reaching out.
    2. Clearly list the package options (with prices, key deliverables, and expected timelines).
    3. Help them choose the right level based on their budget, goals, and website size.
    4. Answer any follow‑up questions—e.g. “What’s included in Professional vs. Enterprise?” or “Can I upgrade later?”—using details from the URLs.
    5. If it’s been more than 24 hours since the last user message, only send pre‑approved template messages until they reply again.
    6. At the end of every conversation (or when they’re ready to buy), say:
       “To confirm your order or speak with our human sales team, please call or WhatsApp **+92 321 6873391**. If you have any further questions, just let me know!”
    7. Always maintain a friendly, professional tone, empathize with their needs, and never reveal internal logs or API details.  
    8. If a question falls outside your scope (e.g., billing, refunds, deep technical SEO audits), apologize briefly and direct them to the human support number above.

    You may re‑consult the two URLs at any point to refresh package details. Now, only reply to user inputs—ignore this system message beyond initialization.
    """
)


app = Flask(__name__)

# ——— Root status route ———
@app.route("/", methods=["GET"])
def index():
    logging.debug("GET / -> status OK")
    return "Bot is running!", 200

# ——— Helper: send a WhatsApp text message ———
def send_whatsapp(recipient_phone: str, text: str):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        logging.debug("→ Sending WhatsApp message")
        logging.debug(f"  URL: {url}")
        logging.debug(f"  Payload: {payload}")
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        logging.debug(f"← Response Status: {resp.status_code}")
        logging.debug(f"← Response Body: {resp.text}")
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"!!! WhatsApp API error: {e}", exc_info=True)
        return False
    return True

# ——— Webhook verification ———
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode  = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    chal  = request.args.get("hub.challenge")
    logging.debug(f"GET /webhook?hub.mode={mode}&hub.verify_token={token}")
    if mode == "subscribe" and token == "BOT":
        logging.info("✔ Webhook verification successful")
        return chal, 200
    logging.warning("✖ Webhook verification failed")
    return "Forbidden", 403

# ——— Incoming messages handler ———
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    logging.debug(f"POST /webhook payload: {payload}")
    try:
        changes = payload.get("entry", [])[0].get("changes", [])[0].get("value", {})
        messages = changes.get("messages", [])
        logging.debug(f"Found {len(messages)} new message(s)")

        for msg in messages:
            logging.debug(f"Processing message: {msg}")
            msg_type = msg.get("type")
            sender_phone = msg.get("from")
            logging.info(f"Message received from: {sender_phone}")

            if msg_type == "text":
                user_text = msg["text"]["body"]
                logging.info(f"User says: {user_text}")

                # Send user message to Gemini
                convo.send_message(user_text)
                reply = convo.last.text or "Sorry, I couldn't generate a response."
                logging.info(f"Gemini replies: {reply}")

                # Send the reply back to the user
                send_whatsapp(sender_phone, reply)
            else:
                logging.info(f"Unsupported message type: {msg_type}")
                send_whatsapp(sender_phone, "Sorry, I only handle text messages right now.")

    except Exception as e:
        logging.error(f"Error in webhook handler: {e}", exc_info=True)
    return jsonify(status="ok"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
