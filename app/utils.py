import base64
import hashlib
import imghdr
import json
import logging
import os
import re
import tempfile
from collections import deque
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from flask import Response, jsonify
from requests.exceptions import ProxyError

from app.config import IGNORED_MODEL_NAMES, AUTH_TOKEN, HISTORY_MSG_LIMIT
from app.config import configure_logging, IMAGE_MODEL_NAMES, ProxyPool

configure_logging()
proxy_pool = ProxyPool()
current_token_index = 0
storage_map = {}


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
        response = request_with_proxy_chat(url, headers, data, True)
        if response.headers.get('YJ-X-Content'):
            raise Exception(f"Popai response  error . Error: {response.headers.get('YJ-X-Content')}")

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
                    {"url": extract_url_from_content(merged_content)}
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
    if chunks:
        return jsonify(chunks[-1])
    else:
        raise Exception("No data available")


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
                if is_base64(url):
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
        response = request_with_proxy_image('https://telegra.ph/upload', files=files)
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
        response = request_with_proxy_chat(url, headers, data, False)
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


def extract_url_from_content(content):
    # 使用正则表达式从 Markdown 内容中提取 URL
    match = re.search(r'\!\[.*?\]\((.*?)\)', content)
    return match.group(1) if match else content


def request_with_proxy_image(url, files):
    return request_with_proxy(url, None, None, False, files)


def request_with_proxy_chat(url, headers, data, stream):
    return request_with_proxy(url, headers, data, stream, None)


def request_with_proxy(url, headers, data, stream, files):
    try:
        proxies = proxy_pool.get_random_proxy()
        logging.info("Use proxy url %s", proxies)

        if proxies:
            response = requests.post(url, headers=headers, json=data, stream=stream, files=files, proxies=proxies)
        else:
            response = requests.post(url, headers=headers, json=data, stream=stream, files=files)
    except ProxyError as e:
        logging.error(f"Proxy error occurred: {e}")
        raise Exception("Proxy error occurred")
    return response


def get_channel_id(hash_value, token, model_name, content, template_id):
    if hash_value in storage_map:
        channel_id, expiry_time = storage_map[hash_value]
        if expiry_time > datetime.now() and channel_id:
            logging.info("Returning channel id from cache")
            return channel_id
    channel_id = fetch_channel_id(token, model_name, content, template_id)
    expiry_time = datetime.now() + timedelta(days=1)
    storage_map[hash_value] = (channel_id, expiry_time)
    return channel_id


def fetch(req):
    if req.method == "OPTIONS":
        return handle_options_request()
    token = get_next_auth_token(AUTH_TOKEN)
    messages, model_name, prompt, user_stream = get_request_parameters(req.get_json())
    model_to_use = map_model_name(model_name)
    template_id = 2000000 if model_name in IMAGE_MODEL_NAMES else ''

    if not messages and prompt:
        final_user_content = prompt
        first_user_message = final_user_content
        image_url = None
    elif messages:
        last_message = messages[-1]
        first_user_message, end_user_message, concatenated_messages = get_user_contents(messages, HISTORY_MSG_LIMIT)
        final_user_content, image_url = process_content(last_message.get('content'))
        final_user_content = concatenated_messages + '\n' + final_user_content if concatenated_messages else final_user_content

    hash_value = generate_hash(first_user_message, model_to_use, token)
    channel_id = get_channel_id(hash_value, token, model_to_use, final_user_content, template_id)

    if final_user_content is None:
        return Response("No user message found", status=400)

    return send_chat_message(req, token, channel_id, final_user_content, model_to_use, user_stream, image_url,
                             model_name)


def handle_options_request():
    return Response(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'})


def generate_model_data():
    return {
        "object": "list",
        "data": [{
            "id": m,
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "popai"
        } for m in IGNORED_MODEL_NAMES]
    }


def upload_file(file_path, token):
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as file:
        # 分块读取文件内容，避免内存占用过大
        for chunk in iter(lambda: file.read(4096), b""):
            # 更新MD5哈希对象
            md5_hash.update(chunk)
    md5_value = md5_hash.hexdigest()
    logging.info(f'md5_value : {md5_value}')
    headers_step1 = {
        'accept': 'application/json',
        'accept-language': 'zh,en;q=0.9,zh-CN;q=0.8',
        'app-name': 'popai-web',
        'authorization': token,
        'cache-control': 'no-cache',
        'language': 'en',
        'origin': 'https://www.popai.pro',
        'pop-url': 'https://www.popai.pro/',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://www.popai.pro/',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }

    response_step1 = requests.get(f'https://api.popai.pro/py/api/v1/chat/getPresignedPost?md5={md5_value}',
                                  headers=headers_step1)

    if response_step1.status_code == 200:
        presigned_data = response_step1.json()
        print("Presigned data received:")
        print(presigned_data)
    else:
        raise Exception(f"Failed to get presigned post: {response_step1.text}")
    # 第二步: 使用预签名的 URL 上传文件
    fields = response_step1.json()['data']['fields']
    upload_url = presigned_data['data']['url']
    # 构造上传文件的表单数据
    form_data = {
        'key': fields['key'],
        'AWSAccessKeyId': fields['AWSAccessKeyId'],
        'policy': fields['policy'],
        'signature': fields['signature']
    }

    with open(file_path, 'rb') as file:
        files = {'file': (file_path, file, 'application/pdf')}

        headers_step2 = {
            'Accept': 'application/json',
            'Accept-Language': 'zh,en;q=0.9,zh-CN;q=0.8',
            'App-Name': 'popai-web',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': 'https://www.popai.pro',
            'Pop-Url': 'https://www.popai.pro/',
            'Pragma': 'no-cache',
            'Referer': 'https://www.popai.pro/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'language': 'en',
            'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }

        response_step2 = requests.post(upload_url, data=form_data, files=files, headers=headers_step2)

    if response_step2.status_code == 204:
        print("File uploaded successfully")
    else:
        raise Exception(f"Failed to upload file: {response_step2.text}")
    # 第三步
    url = 'https://api.popai.pro/py/api/v1/chat/create'

    headers = {
        'accept': 'application/json',
        'accept-language': 'zh,en;q=0.9,zh-CN;q=0.8',
        'app-name': 'popai-web',
        'authorization': token,
        'content-type': 'application/json',
        'language': 'en',
        'origin': 'https://www.popai.pro',
        'pop-url': 'https://www.popai.pro/',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://www.popai.pro/',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

    data = {
        "model": 'GPT-4',
        "md5": md5_value,
        # "fileName": file_path,
        "fileContentType": 'application/pdf',
        "extract_img_5k": True
    }
    logging.info(f'data: {data}')
    logging.info(f'headers: {headers}')

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        print("Chat created successfully")
        print(response.json())
    else:
        print(f"Failed to create chat: {response.status_code}")
        print(response.text)


# def upload_file(file_path):
#     with open(file_path, 'rb') as file:
#         response = requests.post('https://pixeldrain.com/api/file', files={'file': file})
#         logging.info(response.text)
#         if response.status_code == 201:
#             response_data = response.json()
#             file_id = response_data['id']
#             return f"https://pixeldrain.com/api/file/{file_id}"
#
#         else:
#             raise Exception(f"Failed to upload file: {response.json().get('message')}")


def decode_base64_to_file(base64_data):
    header, encoded = base64_data.split(',', 1)
    # 根据MIME类型确定文件后缀
    mime_type = header.split(';')[0].split(':')[1]
    extension = {
        'application/pdf': '.pdf',
        'image/png': '.png',
        'image/jpeg': '.jpg',
        # 可以根据需要添加更多的 MIME 类型和扩展名
    }.get(mime_type, '')

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        temp_file_path = temp_file.name

    data = base64.b64decode(encoded)
    with open(temp_file_path, 'wb') as file:
        file.write(data)
    return temp_file_path


def is_base64(data):
    try:
        if data.startswith('data:'):
            data = data.split(',', 1)[1]
        base64.b64decode(data)
        return True
    except ValueError:
        return False


def is_url(data):
    try:
        result = urlparse(data)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False
