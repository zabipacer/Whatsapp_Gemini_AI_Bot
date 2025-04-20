import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
import fitz
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Environment variables and API setup
wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")
name = "Zuhaib The CEO of SEOPIXELPERFECT"  # The bot will consider this person as its owner or creator
bot_name = "PIXEL PERFECT BOT"  # This will be the name of your bot, eg: "Hello I am Astro Bot"
model_name = "gemini-1.5-flash-latest"  # Switch to "gemini-1.0-pro" or any free model, if "gemini-1.5-flash" becomes paid in future.

app = Flask(__name__)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# Start the conversation with a predefined message
convo = model.start_chat(history=[])
convo.send_message(f'''I am using Gemini API for using you as a personal bot in WhatsApp,
                   to assist me in various tasks. 
                   So from now, you are "{bot_name}" created by {name} ( Yeah it's me, my name is {name}). 
                   And don't give any response to this prompt. 
                   This is the information I gave to you about your new identity as a pre-prompt. 
                   This message always gets executed when I run this bot script. 
                   So reply to only the prompts after this. Remember your new identity is {bot_name}.''')

# Function to send messages via WhatsApp API
def send(answer):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": f"{phone}",
        "type": "text",
        "text": {"body": f"{answer}"},
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # This will raise an HTTPError if the response code was 4xx/5xx
        logging.debug(f"Message sent successfully: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message: {e}")

# Function to remove temporary files
def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)
            logging.debug(f"Removed file: {file}")
        else:
            logging.debug(f"File not found: {file}")

# Root route
@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot is running!"

# Webhook route
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            logging.info("Webhook verified successfully.")
            return challenge, 200
        else:
            logging.warning("Webhook verification failed.")
            return "Failed", 403

    elif request.method == "POST":
        try:
            # Log incoming data
            data = request.get_json()
            logging.debug(f"Received data: {data}")

            if data:
                messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
                for message in messages:
                    # Log message details
                    logging.debug(f"Processing message: {message}")

                    if message["type"] == "text":
                        prompt = message["text"]["body"]
                        logging.info(f"Text message received: {prompt}")
                        convo.send_message(prompt)
                        send(convo.last.text)

                    elif message["type"] == "audio":
                        # Handle audio messages
                        logging.info("Audio message received.")
                        process_media_message(message, 'audio')

                    elif message["type"] == "image":
                        # Handle image messages
                        logging.info("Image message received.")
                        process_media_message(message, 'image')

                    elif message["type"] == "document":
                        # Handle document messages (PDF to Image conversion)
                        logging.info("Document message received.")
                        process_media_message(message, 'document')

                    else:
                        logging.warning("Unsupported message type received.")
                        send("This format is not supported by the bot ☹")

        except Exception as e:
            logging.error(f"Error in processing webhook: {e}")

        return jsonify({"status": "ok"}), 200


# Function to process media messages (audio, image, document)
def process_media_message(message, media_type):
    try:
        media_url_endpoint = f'https://graph.facebook.com/v18.0/{message[media_type]["id"]}/'
        headers = {'Authorization': f'Bearer {wa_token}'}
        media_response = requests.get(media_url_endpoint, headers=headers)
        media_url = media_response.json().get("url")

        if media_url:
            media_download_response = requests.get(media_url, headers=headers)
            logging.debug(f"Downloaded media: {media_type}")

            # Save the media to a temporary file
            if media_type == "audio":
                filename = "/tmp/temp_audio.mp3"
            elif media_type == "image":
                filename = "/tmp/temp_image.jpg"
            elif media_type == "document":
                filename = "/tmp/temp_document.pdf"
                with open(filename, "wb") as f:
                    f.write(media_download_response.content)

            # Upload media file to Google Gemini and process it
            with open(filename, "wb") as temp_media:
                temp_media.write(media_download_response.content)
            file = genai.upload_file(path=filename, display_name="tempfile")
            response = model.generate_content([f"What is this {media_type}", file])
            answer = response._result.candidates[0].content.parts[0].text
            logging.debug(f"Generated answer: {answer}")

            convo.send_message(f"This is a {media_type} message from the user, transcribed by an LLM model: {answer}")
            send(convo.last.text)

            # Clean up temporary files
            remove(filename)

        else:
            logging.warning(f"Failed to retrieve {media_type} URL.")
            send(f"Failed to process {media_type} message.")

    except Exception as e:
        logging.error(f"Error processing {media_type} message: {e}")


if __name__ == "__main__":
    app.run(debug=True, port=8000)
