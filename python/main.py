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
ignored_model_names = ["gpt-4", "gpt-3.5", "websearch", "dall-e-3", "gpt-4o"]
image_model = ["dalle3", "dalle-3", "dall-e-3"]

logging.basicConfig(level=logging.INFO)
# 存储map，包含channel_id和到期时间
storage_map = {}


def process_content(msg):
    text_array = []
    image_url_array = []
    if isinstance(msg, str):
        return msg, image_url_array
    elif isinstance(msg, list):
        for message in msg:
            content_type = message.get("type")
            if content_type == "text":
                text_array.append(message.get("text", ""))
            elif content_type == "image_url":
                url = message.get("image_url", {}).get("url", "")
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
        files = {
            'file': (f'image.{image_type}', image_data, mime_type)
        }
        response = requests.post('https://telegra.ph/upload', files=files)

        # 检查响应状态代码
        response.raise_for_status()  # 如果状态码不是200，会引发HTTPError

        # 解析响应的JSON数据
        json_response = response.json()
        if isinstance(json_response, list) and 'src' in json_response[0]:
            # 返回图片的URL
            return 'https://telegra.ph' + json_response[0]['src']
        else:
            raise ValueError(f"Unexpected response format: {json_response}")

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to upload image. Error: {e}")
    except Exception as e:
        raise Exception(f"Failed to upload image. An error occurred: {e}")


def is_base64_image(base64_string):
    return base64_string.startswith('data:image')


def get_assistant_contents(messages, limit=3):
    contents = []
    for message in messages:
        if message.get("role") == "assistant":
            contents.append(message.get("content", ""))
            if len(contents) == limit:
                break
    return contents


def generate_hash(contents, model_name):
    concatenated = ''.join(contents)
    return model_name + hashlib.md5(concatenated.encode('utf-8')).hexdigest()


def get_channel_id(hash_value, token, model_name, content, template_id):
    # 检查缓存中是否存在且未过期
    if hash_value in storage_map:
        channel_id, expiry_time = storage_map[hash_value]
        if expiry_time > datetime.now() and channel_id:
            return channel_id

    # 如果缓存不存在或已过期，调用第三方接口获取新的 channel_id
    channel_id = fetch_channel_id(token, model_name, content, template_id)

    # 将新的 channel_id 存储到缓存中，有效期设置为1天
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
        resp = requests.post(url, headers=headers, json=data)
        # logging.info("fetch_channel_id resp: %s", resp.json())

        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info("fetch_channel_id elapsed_time: %.2f seconds", elapsed_time)
        # logging.info("get channel id: %s", resp.json())

        resp.raise_for_status()
        response_data = resp.json()
        return response_data.get('data', {}).get('channelId')

    except requests.exceptions.RequestException as e:
        end_time = time.time()
        logging.error("fetch_channel_id error: %s, elapsed_time: %.2f seconds", e, end_time - start_time)
        raise Exception(f"Failed to fetch channel_id. Error: {e}")

    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        raise


def send_chat_message(req, auth_token, channel_id, final_user_content, model_name, stream, image_url):
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
        # logging.info("post url= %s headers = %s data = %s", url, headers, data)
        resp = requests.post(url, headers=headers, json=data)
        # logging.info("send_chat_message resp: %s", resp)
        end_time = time.time()
        logging.info("send_chat_message elapsed_time: %.2f seconds", end_time - start_time)
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        # 处理异常，例如打印错误信息
        logging.error("requests error occurred: %s; elapsed_time: %.2f seconds ", e, end_time - start_time)
        return Response(status=500)

    if resp.status_code != 200:
        return Response(status=resp.status_code)

    if stream:
        return stream_response(req, resp, model_name)
    return jsonify(resp.json())


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
    # 按键的长度从长到短排序
    sorted_keys = sorted(model_mapping.keys(), key=len, reverse=True)

    for key in sorted_keys:
        if model_name.lower().startswith(key):
            return model_mapping[key]

    return "GPT-4"


def fetch(req):
    # logging.info("body %s", req.json)
    if req.method == "OPTIONS":
        return Response(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'})
    final_user_content, last_system_content, channel_id = None, None, None
    image_url = []
    body = req.get_json()
    messages = body.get("messages", [])
    model_name = body.get("model")
    prompt = body.get("prompt", False)
    stream = body.get("stream", False)
    auth_token = os.getenv("AUTHORIZATION")
    model_to_use = map_model_name(model_name)
    template_id = 2000000 if model_name in image_model else ''

    if not messages and prompt:
        content = prompt
        final_user_content = prompt
        channel_id = os.getenv("CHAT_CHANNEL_ID")
    elif messages:
        last_message = messages[-1]
        final_user_content, image_url = process_content(last_message.get('content'))

        # 获取前三条role为assistant的content值，并生成hash
        assistant_contents = get_assistant_contents(messages)
        hash_value = generate_hash(assistant_contents, model_to_use)
        # 获取channel_id
        channel_id = get_channel_id(hash_value, auth_token, model_to_use, final_user_content, template_id)

    logging.info("image_url %s", image_url)

    if final_user_content is None:
        return Response("No user message found", status=400)

    logging.info("channelId %s", channel_id)
    logging.info("model_name %s", model_to_use)
    return send_chat_message(req, auth_token, channel_id, final_user_content, model_to_use, stream, image_url)


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
        } for m in ignored_model_names]
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3034)
