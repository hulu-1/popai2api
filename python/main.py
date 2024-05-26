import base64
import hashlib
import imghdr
import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests
from flask import Flask, request, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Constants
IGNORED_MODEL_NAMES = ["gpt-4", "gpt-3.5", "websearch", "dall-e-3", "gpt-4o"]
IMAGE_MODEL_NAMES = ["dalle3", "dalle-3", "dall-e-3"]
AUTH_TOKEN = os.getenv("AUTHORIZATION")

# Storage map containing channel_id and expiration time
storage_map = {}

# Logging configuration
logging.basicConfig(level=logging.INFO)


def process_content(message):
    text_array = []
    image_url_array = []

    if isinstance(message, str):
        return message, image_url_array

    if isinstance(message, list):
        for msg in message:
            content_type = msg.get("type")
            if content_type == "text":
                text_array.append(msg.get("text", ""))
            elif content_type == "image_url":
                url = msg.get("image_url", {}).get("url", "")
                if is_base64_image(url):
                    url = upload_image_to_telegraph(url)
                image_url_array.append(url)

    return '\n'.join(text_array), image_url_array


def upload_image_to_telegraph(base64_string):
    try:
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
        image_data = base64.b64decode(base64_string)

        image_type = imghdr.what(None, image_data)
        if image_type is None:
            raise ValueError("Invalid image data")

        mime_type = f"image/{image_type}"
        files = {'file': (f'image.{image_type}', image_data, mime_type)}
        response = requests.post('https://telegra.ph/upload', files=files)

        response.raise_for_status()
        json_response = response.json()
        if isinstance(json_response, list) and 'src' in json_response[0]:
            return 'https://telegra.ph' + json_response[0]['src']
        else:
            raise ValueError(f"Unexpected response format: {json_response}")

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to upload image. Error: {e}")
    except Exception as e:
        raise Exception(f"Failed to upload image. An error occurred: {e}")


def is_base64_image(base64_string):
    return base64_string.startswith('data:image')


def get_user_contents(messages, limit=3):
    contents = []
    user_content_added = False
    for message in messages:
        if message.get("role") == "user" and not user_content_added:
            contents.append(str(message.get("content", '')))
            user_content_added = True
    return contents


def generate_hash(contents, model_name):
    concatenated = ''.join(contents)
    return model_name + hashlib.md5(concatenated.encode('utf-8')).hexdigest()


def get_channel_id(hash_value, token, model_name, content, template_id):
    if hash_value in storage_map:
        channel_id, expiry_time = storage_map[hash_value]
        if expiry_time > datetime.now() and channel_id:
            return channel_id

    channel_id = fetch_channel_id(token, model_name, content, template_id)
    expiry_time = datetime.now() + timedelta(days=1)
    storage_map[hash_value] = (channel_id, expiry_time)

    return channel_id


def fetch_channel_id(auth_token, model_name, content, template_id):
    url = "https://api.popai.pro/api/v1/chat/getChannel"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "App-Name": "popai-web",
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Device-Info": '{"web_id":"drBt-M9G_I9eKAgB8TdnY","baidu_id":"18f1fd3dc7749443876b69"}',
        "Language": "en",
        "Origin": "https://www.popai.pro",
        "Referer": "https://www.popai.pro/",
        "Pop-Url": "https://www.popai.pro/creation/All/Image",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "Windows",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    data = {
        "model": model_name,
        "templateId": template_id,
        "message": content,
        "language": "English",
        "fileType": None
    }

    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        return response_data.get('data', {}).get('channelId')

    except requests.exceptions.RequestException as e:
        logging.error("fetch_channel_id error: %s", e)
        raise Exception(f"Failed to fetch channel_id. Error: {e}")
    finally:
        elapsed_time = time.time() - start_time
        logging.info("fetch_channel_id elapsed_time: %.2f seconds", elapsed_time)


def stream_2_json(resp, model_name):
    logging.info("Entering stream_2_json function")

    chunks = []
    buffer = ""
    json_object_counter = 0
    merged_content = ""  # Variable to store the merged content
    append_to_chunks = chunks.append  # Store the append function as a local variable
    decode_utf8 = bytes.decode  # Store the decode function as a local variable
    loads = json.loads  # Store the loads function as a local variable
    for chunk in resp.iter_content(chunk_size=None):
        buffer += decode_utf8(chunk, 'utf-8')
        while "\n\n" in buffer:
            json_object, buffer = buffer.split("\n\n", 1)
            if json_object.startswith("data:"):
                json_object = json_object[5:].strip()
                json_object_counter += 1
                if json_object_counter == 1:
                    continue
                try:
                    chunk_json = loads(json_object)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON: {e}")
                    continue
                for message in chunk_json:
                    message_id = message.get("messageId", "")
                    objectid = message.get("chunkId", "")
                    content = message.get("content", "")
                    merged_content += content

                wrapped_chunk = {
                    "id": message_id,
                    "object": objectid,
                    "created": 0,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": merged_content
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    },
                    "system_fingerprint": None
                }
                append_to_chunks(wrapped_chunk)

    logging.info("Exiting stream_2_json function")
    return jsonify(chunks[-1])


def send_chat_message(req, auth_token, channel_id, final_user_content, model_name, stream, image_url):
    logging.info("Channel ID: %s", channel_id)
    # logging.info("Final User Content: %s", final_user_content)
    logging.info("Model Name: %s", model_name)
    logging.info("Image URL: %s", image_url)
    logging.info("Stream: %s", stream)
    url = "https://api.popai.pro/api/v1/chat/send"
    headers = {
        "Accept": "text/event-stream",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "App-Name": "popai-web",
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Device-Info": '{"web_id":"drBt-M9G_I9eKAgB8TdnY","baidu_id":"18f1fd3dc7749443876b69"}',
        "Gtoken": "tgergrehabtdnj",
        "Origin": "https://www.popai.pro",
        "Priority": "u=1, i",
        "Referer": "https://www.popai.pro/",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "Windows",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    data = {
        "isGetJson": True,
        "version": "1.3.6",
        "language": "zh-CN",
        "channelId": channel_id,
        "message": final_user_content,
        "model": model_name,
        "messageIds": [],
        "imageUrls": image_url,
        "improveId": None,
        "richMessageId": None,
        "isNewChat": False,
        "action": None,
        "isGeneratePpt": False,
        "isSlidesChat": False,
        "roleEnum": None,
        "pptCoordinates": "",
        "translateLanguage": None,
        "docPromptTemplateId": None
    }

    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=data)
        if stream:
            return stream_response(req, response, model_name)
        else:
            return stream_2_json(response, model_name)
        # return jsonify(response.json())

    except requests.exceptions.RequestException as e:
        logging.error("send_chat_message error: %s", e)
        return Response(status=500)
    finally:
        elapsed_time = time.time() - start_time
        logging.info("send_chat_message elapsed_time: %.2f seconds", elapsed_time)


def map_model_name(model_name):
    model_mapping = {
        "gpt-4": "GPT-4",
        "dalle3": "GPT-4",
        "dalle-3": "GPT-4",
        "dall-e-3": "GPT-4",
        "gpt-3.5": "Standard",
        "websearch": "Web Search",
        "internet": "Web Search",
        "gpt-4o": "GPT-4o"
    }
    sorted_keys = sorted(model_mapping.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if model_name.lower().startswith(key):
            return model_mapping[key]
    return "GPT-4"


def fetch(req):
    if req.method == "OPTIONS":
        return Response(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'})

    body = req.get_json()
    messages = body.get("messages", [])
    model_name = body.get("model")
    prompt = body.get("prompt", False)
    stream = body.get("stream", True)

    model_to_use = map_model_name(model_name)
    template_id = 2000000 if model_name in IMAGE_MODEL_NAMES else ''

    if not messages and prompt:
        final_user_content = prompt
        channel_id = os.getenv("CHAT_CHANNEL_ID")
    elif messages:
        last_message = messages[-1]
        final_user_content, image_url = process_content(last_message.get('content'))
        user_contents = get_user_contents(messages)
        hash_value = generate_hash(user_contents, model_to_use)
        channel_id = get_channel_id(hash_value, AUTH_TOKEN, model_to_use, final_user_content, template_id)

    if final_user_content is None:
        return Response("No user message found", status=400)

    return send_chat_message(req, AUTH_TOKEN, channel_id, final_user_content, model_to_use, stream, image_url)


def stream_response(req, resp, model_name):
    logging.info("Entering stream_response function")

    def generate():
        buffer = ""
        json_object_counter = 0
        for chunk in resp.iter_content(chunk_size=None):
            buffer += chunk.decode('utf-8')
            while "\n\n" in buffer:
                json_object, buffer = buffer.split("\n\n", 1)
                if json_object.startswith("data:"):
                    json_object = json_object[len("data:"):].strip()
                    json_object_counter += 1
                    if json_object_counter == 1:
                        continue
                    try:
                        chunk_json = json.loads(json_object)
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse JSON: {e}")
                        continue
                    for message in chunk_json:
                        message_id = message.get("messageId", "")
                        objectid = message.get("chunkId", "")
                        content = message.get("content", "")
                        wrapped_chunk = {
                            "id": message_id,
                            "object": objectid,
                            "created": 0,
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "role": "assistant",
                                        "content": content
                                    },
                                    "finish_reason": "stop",
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0
                            },
                            "system_fingerprint": None
                        }
                        # logging.info(f"Wrapped chunk: {wrapped_chunk}")
                        event_data = f"data: {json.dumps(wrapped_chunk, ensure_ascii=False)}\n\n"
                        yield event_data.encode('utf-8')

    logging.info("Exiting stream_response function")
    return Response(generate(), mimetype='text/event-stream; charset=UTF-8')


@app.route("/v1/chat/completions", methods=["GET", "POST", "OPTIONS"])
def onRequest():
    try:
        return fetch(request)
    except Exception as e:
        logging.error("An error occurred: %s", e)
        return 'Internal Server Error', 500


@app.get('/v1/models')
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": m,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "popai"
        } for m in IGNORED_MODEL_NAMES]
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3034)
