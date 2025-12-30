import logging
from flask import current_app, jsonify
import json
import re
import os
import aiohttp
import asyncio
from dotenv import load_dotenv
import requests
import time
import schedule
import threading
from datetime import datetime, timedelta
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
import redis
import pytz



load_dotenv()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY")
unsplash_api_key = os.getenv("UNSPLASH_API_KEY")
stability_ai_api_key = os.getenv("STABILITY_AI_API_KEY")
imgbb_api_key = os.getenv("IMGBB_API_KEY")


chaitanya_counter_path = (
    r"C:\coding projects\whatsapp_bot\app\utils\chaitanya_counter.txt"
)
image_storage_path = r"C:\1\2\\"

redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"), ssl_cert_reqs=None)

GOOGLE_CLOUD_CREDENTIALS_FILE = "google_cloud.json"
GOOGLE_CLOUD_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

google_cloud_credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_CLOUD_CREDENTIALS_FILE, scopes=GOOGLE_CLOUD_SCOPES
)

google_sheets_service = build("sheets", "v4", credentials=google_cloud_credentials)

import google.generativeai as genai


def run_asyncio_coroutine(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coroutine)
    finally:
        loop.close()


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def schedule_runner():  # This function will run forever checking for scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(1)


my_thread = threading.Thread(
    target=schedule_runner
)  # Create a thread for the schedule_runner function
my_thread.start()


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def get_image_message_input(recipient, img_url):
    data = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "image",
        "image": {
            "link": img_url,
        },
    }
    return data


def gemini_reply(message_body, wa_id):
    load_dotenv()
    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])

    # Set up the model
    generation_config = {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
    ]

    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )

    modified_message_body = (
        message_body.replace("/ai", "").replace("/AI", "").replace("/bard", "").strip()
    )
    response = model.generate_content(modified_message_body)

    if not response.candidates:
        data = get_text_message_input(wa_id, "No response was generated.")
        run_asyncio_coroutine(send_message(data))
        return

    responseprocessed = process_text_for_whatsapp(response.text)
    data = get_text_message_input(wa_id, responseprocessed)

    run_asyncio_coroutine(send_message(data))


def bus_schedule(wa_id):
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    data = get_image_message_input(wa_id, "https://i.ibb.co/PYJXF6k/bus-schedule.jpg")

    response = requests.post(url, headers=headers, json=data)

    print(response.text)


def chaitanya_counter(wa_id, message_body):
    with open(chaitanya_counter_path, "r") as file:
        count = [int(num) for num in file.readline().split()[:3]]

    if message_body == "count":
        run_asyncio_coroutine(
            send_message(
                get_text_message_input(
                    wa_id,
                    f"Cold Drink: {count[0]}\nChips: {count[1]}\nIce Cream: {count[2]}",
                )
            )
        )
        return

    split_message = message_body.rsplit(" ", 1)

    if len(split_message) != 2:
        run_asyncio_coroutine(
            send_message(get_text_message_input(wa_id, "Invalid input."))
        )
        return

    action = split_message[0].lower()
    number = int(split_message[1])

    if action == "colddrink" or action == "cold drink":
        count[0] += number
        with open(chaitanya_counter_path, "w") as file:
            file.write(f"{count[0]} {count[1]} {count[2]}")
    elif action == "chips":
        count[1] += number
        with open(chaitanya_counter_path, "w") as file:
            file.write(f"{count[0]} {count[1]} {count[2]}")
    elif action == "icecream" or action == "ice cream":
        count[2] += number
        with open(chaitanya_counter_path, "w") as file:
            file.write(f"{count[0]} {count[1]} {count[2]}")
    else:
        run_asyncio_coroutine(
            send_message(get_text_message_input(wa_id, "Invalid action."))
        )
        return

    run_asyncio_coroutine(
        send_message(
            get_text_message_input(
                wa_id,
                f"{action} count updated.\nCurrent count-\nCold Drink: {count[0]}\nChips: {count[1]}\nIce Cream: {count[2]}",
            )
        )
    )


def youtube_mp3(message_body, wa_id):
    querystring = {
        "url": message_body.replace("/youtubemp3", "")
        .replace("/youtube", "")
        .replace("/mp3", "")
        .replace("/yt", "")
        .strip()
    }

    url = "https://youtube-mp3-downloader2.p.rapidapi.com/ytmp3/ytmp3/"

    headers = {
        "X-RapidAPI-Key": "RAPID_API_KEY_HERE",
        "X-RapidAPI-Host": "youtube-mp3-downloader2.p.rapidapi.com",
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        data = get_text_message_input(
            wa_id, "Download link: " + response.json()["link"]
        )
        run_asyncio_coroutine(send_message(data))
    else:
        data = get_text_message_input(wa_id, "Error occurred while converting the mp3.")
        run_asyncio_coroutine(send_message(data))


def upload_image_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"

    payload = {
        "key": imgbb_api_key,
        "image": base64.b64encode(open(image_path, "rb").read()),
    }

    response = requests.post(url, payload)
    data = response.json()

    if response.status_code == 200:
        return data["data"]["url"]
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def generate_img(message_body, wa_id):
    prompt = message_body.replace("/generate", "").replace("/gen", "").strip()

    if prompt == "":
        data = get_text_message_input(wa_id, "Please enter a prompt.")
        run_asyncio_coroutine(send_message(data))
        return

    response = requests.post(
        f"https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {stability_ai_api_key}",
        },
        json={
            "text_prompts": [
                {
                    "text": prompt,
                }
            ],
            "cfg_scale": 7,
            "height": 1024,
            "width": 1024,
            "samples": 1,
            "steps": 30,
        },
    )

    if response.status_code != 200:
        raise Exception("Non-200 response: " + str(response.text))

    data = response.json()

    file_name = int(time.time())
    image = data["artifacts"][0]["base64"]

    with open(rf"{image_storage_path}{file_name}.png", "wb") as f:
        f.write(base64.b64decode(image))

    img_url = upload_image_to_imgbb(rf"{image_storage_path}{file_name}.png")

    if img_url is None:
        data = get_text_message_input(wa_id, "Error occurred while uploading.")
        run_asyncio_coroutine(send_message(data))
        return

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    data = get_image_message_input(wa_id, img_url)

    response = requests.post(url, headers=headers, json=data)

    print(response.text)

    os.remove(rf"{image_storage_path}{file_name}.png")


def manage_money(message_body, wa_id):
    message_parts = message_body.replace("/money", "").replace("/m", "").strip().split(" ", 2)
    action = message_parts[0].lower()
    amount = int(message_parts[1])
    message = message_parts[2]

    current_balance = 0

    GOOGLE_SHEET_ID = "Google_Sheet_ID_Here"
    GOOGLE_SHEET_RANGE = "A1:A1"

    google_sheet = google_sheets_service.spreadsheets()
    google_sheet_result = (
        google_sheet.values()
        .get(spreadsheetId=GOOGLE_SHEET_ID, range=GOOGLE_SHEET_RANGE)
        .execute()
    )
    google_sheet_values = google_sheet_result.get("values", [])

    if not google_sheet_values:
        print("No data found.")
    else:
        current_balance = int(google_sheet_values[0][0])

    if int(wa_id) == 919:

        if action == "take":
            current_balance -= amount
        elif action == "give":
            current_balance += amount
        else:
            data = get_text_message_input(wa_id, "Invalid action.")
            run_asyncio_coroutine(send_message(data))
            return

    elif int(wa_id) == 918:
        if action == "take":
            current_balance += amount
        elif action == "give":
            current_balance -= amount
        else:
            data = get_text_message_input(wa_id, "Invalid action.")
            run_asyncio_coroutine(send_message(data))
            return

    else:
        data = get_text_message_input(wa_id, "Not authorized.")
        run_asyncio_coroutine(send_message(data))
        return

    new_google_sheet_value = [[current_balance]]
    google_sheet_body = {
        "range": GOOGLE_SHEET_RANGE,
        "majorDimension": "ROWS",
        "values": new_google_sheet_value,
    }

    google_sheet_update_result = (
        google_sheet.values()
        .update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=GOOGLE_SHEET_RANGE,
            valueInputOption="RAW",
            body=google_sheet_body,
        )
        .execute()
    )

    data = get_text_message_input(wa_id, f"Action successful")

def money_balance(wa_id):
    GOOGLE_SHEET_ID = "Google_Sheet_ID_Here"
    GOOGLE_SHEET_RANGE = "A1:A1"

    google_sheet = google_sheets_service.spreadsheets()
    google_sheet_result = (
        google_sheet.values()
        .get(spreadsheetId=GOOGLE_SHEET_ID, range=GOOGLE_SHEET_RANGE)
        .execute()
    )
    google_sheet_values = google_sheet_result.get("values", [])

    if not google_sheet_values:
        print("No data found.")
    else:
        current_balance = int(google_sheet_values[0][0])

    if int(wa_id) == 919:
        if current_balance < 0:
            message_txt = "You have to take " + str(abs(current_balance)) + " from chaitanya"
        elif current_balance > 0:
            message_txt = "You have to give " + str(abs(current_balance)) + " to chaitanya"
        else:
            message_txt = "You are all settled up with chaitanya"
    elif int(wa_id) == 918:
        if current_balance < 0:
            message_txt = "You have to give " + str(abs(current_balance)) + " to aryan"
        elif current_balance > 0:
            message_txt = "You have to take " + str(abs(current_balance)) + " from aryan"
        else:
            message_txt = "You are all settled up with aryan"

    data = get_text_message_input(wa_id, message_txt)
    run_asyncio_coroutine(send_message(data))

# region reminder functions
def is_valid_time(time):
    try:
        parsed_time = datetime.strptime(time, "%I:%M %p")
        return True
    except ValueError:
        return False


def convert_to_24_hour_clock(time):
    parsed_time = datetime.strptime(time, "%I:%M %p")
    converted_time = parsed_time.strftime("%H:%M")
    return converted_time

def convert_to_server_time(time_str, user_tz='Asia/Kolkata', server_tz='UTC'):
    user_timezone = pytz.timezone(user_tz)
    server_timezone = pytz.timezone(server_tz)
    
    # Parse the input time string into a naive datetime object
    naive_user_time = datetime.strptime(time_str, "%H:%M")
    
    # Localize the naive datetime object to the user's timezone
    user_time = user_timezone.localize(naive_user_time)
    
    # Convert the user's time to the server's timezone
    server_time = user_time.astimezone(server_timezone)
    
    return server_time

def reminder(message_body, wa_id):
    message_parts = message_body.replace("/reminder", "").strip().split(" ", 3)
    date = message_parts[0]
    time = message_parts[1] + " " + message_parts[2]
    message = message_parts[3]

    if is_valid_time(time):
        converted_time = convert_to_24_hour_clock(time)
        user_datetime_str = date + " " + converted_time
        server_datetime = convert_to_server_time(user_datetime_str)

        current_time = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")

        run_asyncio_coroutine(
            send_message_outside_app(
                get_text_message_input(wa_id, "converted_time " + converted_time + " server_time " + server_datetime.strftime("%Y-%m-%d %H:%M:%S") + " current_time " + current_time)
            )
        )

        delay = (server_datetime - datetime.now(pytz.utc)).total_seconds()
        if delay > 0:
            threading.Timer(delay, lambda: send_reminder(wa_id, message)).start()
            run_asyncio_coroutine(
                send_message_outside_app(get_text_message_input(wa_id, "Reminder Set"))
            )
        else:
            run_asyncio_coroutine(
                send_message_outside_app(get_text_message_input(wa_id, "The specified time is in the past."))
            )
    else:
        run_asyncio_coroutine(
            send_message_outside_app(
                get_text_message_input(wa_id, "Invalid time format.")
            )
        )

def send_reminder(wa_id, text):
    data = get_text_message_input(wa_id, text)
    run_asyncio_coroutine(send_message_outside_app(data))


# endregion


def search_image(message_body, wa_id):
    modified_message_body = message_body.replace("/image", "").replace("/img", "").replace("/photo", "").strip()
    url = f"https://api.unsplash.com/search/photos?query={modified_message_body}&client_id={unsplash_api_key}&per_page=1"

    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        if int(response.headers["X-Ratelimit-Remaining"]) == 0:
            reset_time = int(response.headers["X-Ratelimit-Reset"])
            reset_time = datetime.datetime.fromtimestamp(reset_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            run_asyncio_coroutine(
                send_message(
                    get_text_message_input(
                        wa_id,
                        f"Rate limit reached. Please try again after {reset_time}.",
                    )
                )
            )
        else:
            for photo in data["results"]:
                img = photo["urls"]["regular"] + ".jpg"
                url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
                headers = {
                    "Content-type": "application/json",
                    "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
                }
                data = get_image_message_input(wa_id, img)

                response = requests.post(url, headers=headers, json=data)

                print(response.text)
    else:
        send_message("Error occurred while searching for images.")


async def send_message_to_all(text):

    all_mobile_nos = [
        919,
        915,
        911,
        918,
        915,
    ]

    for mobile_no in all_mobile_nos:
        await send_message_outside_app(get_text_message_input(mobile_no, text))
        await asyncio.sleep(0.5)


async def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
        try:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    print("Status:", response.status)
                    print("Content-type:", response.headers["content-type"])

                    html = await response.text()
                    print("Body:", html)
                else:
                    print(response.status)
                    print(response)
        except aiohttp.ClientConnectorError as e:
            print("Connection Error", str(e))


async def send_message_outside_app(data):
    load_dotenv()
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {os.getenv('ACCESS_TOKEN')}",
    }

    async with aiohttp.ClientSession() as session:
        url = f"GRAPH_API_URL_"
        try:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    print("Status:", response.status)
                    print("Content-type:", response.headers["content-type"])

                    html = await response.text()
                    print("Body:", html)
                else:
                    print(response.status)
                    print(response)
        except aiohttp.ClientConnectorError as e:
            print("Connection Error", str(e))


def process_text_for_whatsapp(text):
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()

    pattern = r"\*\*(.*?)\*\*"
    replacement = r"*\1*"
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def blue_tick(message_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        print(response.json())
    else:
        print("Blue tick failed with status code:", response.status_code)


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    # name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]
    message_id = message["id"]

    # use "in message_body" for each string seprarately

    if "/help" in message_body or "/Help" in message_body or "/HELP" in message_body:
        help_text = "Welcome to the WhatsApp Bot!\n\nHere are some available commands:\n/help - Display this help message\n/ai - Activate AI chatbot\n/bus timetable - Get bus timetable\n/image - Search for an image\n/all - Send a message to all users\n/reminder - Set a reminder\n/chaitanya - Counter for Chaitanya\n/youtubemp3 - Convert YouTube video to MP3\n/gen - Generate an image\n/mess - Get today's mess menu\n/tt - Get class timetable\n\nFeel free to explore and interact with the bot!"
        run_asyncio_coroutine(send_message(get_text_message_input(wa_id, help_text)))

    elif "/ai" in message_body or "/AI" in message_body or "/bard" in message_body:
        gemini_reply(message_body, wa_id)

    elif (
        "/bus timetable" in message_body
        or "/bus schedule" in message_body
        or "/bus" in message_body
    ):
        bus_schedule(wa_id)

    elif "/all" in message_body:
        run_asyncio_coroutine(
            send_message_to_all(message_body.replace("/all", "").strip())
        )

    elif "/reminder" in message_body:
        reminder(message_body, wa_id)

    elif "/chaitanya" in message_body:
        chaitanya_counter(wa_id, message_body.replace("/chaitanya", "").strip())

    elif (
        "/youtubemp3" in message_body
        or "/youtube" in message_body
        or "/mp3" in message_body
        or "/yt" in message_body
    ):
        youtube_mp3(message_body, wa_id)

    elif "/generate" in message_body or "/gen" in message_body:
        generate_img(message_body, wa_id)

    elif "/image" in message_body or "/img" in message_body or "/photo" in message_body:
        search_image(message_body, wa_id)

    elif "/money" in message_body or "/m" in message_body:
        manage_money(message_body, wa_id)

    elif "/balance" in message_body:
        money_balance(wa_id)

    blue_tick(message_id)


def is_valid_whatsapp_message(body):
    if (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
    ):
        message_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["id"]

        if not redis_client.exists(message_id):
            redis_client.setex(message_id, 43200, "1")  # expire after 12 hours
            return True
        else:
            return False

    return False
