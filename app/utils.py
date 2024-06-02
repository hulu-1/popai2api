import base64
import hashlib
import imghdr
import json
import logging
import os
from collections import deque

import requests
from flask import Response, jsonify

from app.config import configure_logging, IMAGE_MODEL_NAMES

configure_logging()
current_token_index = 0


def send_http_request(url, headers, data):
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logging.error("HTTP request error: %s", e)
        raise


def get_env_variable(var_name):
    return os.getenv(var_name)


def send_chat_message(req, auth_token, channel_id, final_user_content, model_name, user_stream, image_url,
                      user_model_name):
    logging.info("Channel ID: %s", channel_id)
    # logging.info("Final User Content: %s", final_user_content)
    logging.info("Model Name: %s", model_name)
    logging.info("Image URL: %s", image_url)
    logging.info("User stream: %s", user_stream)
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

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        if response.headers.get('Content-Type') == 'text/event-stream;charset=UTF-8':
            if not user_stream:
                return stream_2_json(response, model_name, user_model_name)
            return stream_response(response, model_name)
        else:
            return stream_2_json(response, model_name, user_model_name)
    except requests.exceptions.RequestException as e:
        logging.error("send_chat_message error: %s", e)
        return handle_error(e)


def stream_response(resp, model_name):
    logging.info("Entering stream_response function")

    def generate():
        for message in handle_http_response(resp):
            message_id = message.get("messageId", "")
            objectid = message.get("chunkId", "")
            content = message.get("content", "")
            wrapped_chunk = {
                "id": message_id,
                "object": "chat.completion",
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
                    "prompt_tokens": 13,
                    "completion_tokens": 7,
                    "total_tokens": 20
                },
                "system_fingerprint": None
            }
            event_data = f"data: {json.dumps(wrapped_chunk, ensure_ascii=False)}\n\n"
            yield event_data.encode('utf-8')

    logging.info("Exiting stream_response function")
    return Response(generate(), mimetype='text/event-stream; charset=UTF-8')


def stream_2_json(resp, model_name, user_model_name):
    logging.info("Entering stream_2_json function")

    chunks = []
    merged_content = ""
    append_to_chunks = chunks.append
    for message in handle_http_response(resp):
        message_id = message.get("messageId", "")
        objectid = message.get("chunkId", "")
        content = message.get("content", "")
        merged_content += content
        if user_model_name in IMAGE_MODEL_NAMES:
            # 如果 model_name 在 IMAGE_MODEL_NAMES 内，转换为包含 URL 的格式
            wrapped_chunk = {
                "created": 0,
                "data": [
                    {"url": merged_content}  # 假设 merged_content 是 URL
                ]
            }
        else:
            wrapped_chunk = {
                "id": message_id,
                "object": "chat.completion",
                "created": 0,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": merged_content
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 13,
                    "completion_tokens": 7,
                    "total_tokens": 20
                },
                "system_fingerprint": None
            }
        append_to_chunks(wrapped_chunk)

    logging.info("Exiting stream_2_json function")
    return jsonify(chunks[-1])


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


def process_msg_content(content):
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return ' '.join(item.get("text") for item in content if item.get("type") == "text")
    return None


def get_user_contents(messages, limit):
    limit = int(limit)
    selected_messages = deque(maxlen=limit)
    first_user_message = None

    # 过滤并处理用户消息
    for message in messages:
        if message.get("role") == "user":
            content = process_msg_content(message.get("content"))
            if content:
                selected_messages.append(content)
                if first_user_message is None:
                    first_user_message = content

    # 检查是否有足够的消息
    if selected_messages:
        end_user_message = selected_messages[-1]
    else:
        end_user_message = None

    # 拼接消息内容
    if selected_messages:
        selected_messages.pop()  # 移除最后一条数据

    concatenated_messages = ' \n'.join(selected_messages)

    return first_user_message, end_user_message, concatenated_messages


# def get_user_contents(messages, limit=3):
#     user_messages = [str(message.get("content", '')) for message in messages if message.get("role") == "user"]
#     end_message = user_messages[-1] if user_messages else None
#     selected_messages = user_messages[-limit-1:-1] if len(user_messages) > limit else user_messages[:-1]
#     concatenated_messages = ' '.join(selected_messages)
#     return end_message, concatenated_messages

# def get_user_contents(messages, limit=3):
#     contents = []
#     user_content_added = False
#     for message in messages:
#         if message.get("role") == "user" and not user_content_added:
#             contents.append(str(message.get("content", '')))
#             user_content_added = True
#     return contents


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

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        return response_data.get('data', {}).get('channelId')

    except requests.exceptions.RequestException as e:
        logging.error("fetch_channel_id error: %s", e)
        raise Exception(f"Failed to fetch channel_id. Error: {e}") from e


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


def generate_hash(contents, model_name, token):
    concatenated = ''.join(contents)
    return token + model_name + hashlib.md5(concatenated.encode('utf-8')).hexdigest()


def handle_http_response(resp):
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
                    yield message


def get_next_auth_token(tokens):
    if not tokens:
        raise ValueError("No tokens provided.")
    auth_tokens = tokens.split(',')
    global current_token_index
    token = auth_tokens[current_token_index]
    current_token_index = (current_token_index + 1) % len(auth_tokens)
    logging.info("Using token: %s", token)
    return token


def handle_error(e):
    error_response = {
        "error": {
            "message": str(e),
            "type": "popai_2_api_error"
        }
    }
    return jsonify(error_response), 500


def get_request_parameters(body):
    messages = body.get("messages", [])
    model_name = body.get("model")
    prompt = body.get("prompt", False)
    stream = body.get("stream", False)
    return messages, model_name, prompt, stream
