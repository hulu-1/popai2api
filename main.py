from flask import Flask, request, Response, jsonify
from flask_cors import CORS, cross_origin
import json
import uuid
import logging
import requests

app = Flask(__name__)
CORS(app)

def fetch(req):
    if req.method == "OPTIONS":
        return Response(response="", headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}, status=204)

    body = req.json
    messages = body.get("messages", [])
    model_name = body.get("model", "GPT-4")
    stream = body.get("stream", False)
    last_user_content = None
    channelId = None

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "user":
            last_user_content = content
            if "使用四到五个字直接返回这句话的简要主题，不要解释、不要标点、不要语气词、不要多余文本，不要加粗，如果没有主题，请直接返回“闲聊”" in content:
                return Response(status=200)
        elif role == "system":
            if content == "简要总结一下对话内容，用作后续的上下文提示 prompt，控制在 200 字以内":
                return Response(status=200)
            try:
                uuid.UUID(content)
                channelId = content
            except ValueError:
                pass

            try:
                uuid.UUID(content)
                channelId = content
            except ValueError:
                pass

    if last_user_content is None:
        return Response(status=400, text="No user message found")

    auth_header = request.headers.get("Authorization")
    auth_token = auth_header.split(' ')[1] if auth_header and ' ' in auth_header else auth_header

    if model_name in ["dalle3", "websearch"]:
        with open('channelid.txt', 'r') as file:
            lines = file.readlines()
            for line in lines:
                model, ch_id = line.strip().split(":")
                if model == model_name:
                    channelId = ch_id
                    break

    if channelId is None:
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
            "Pop-Url": "https://www.popai.pro/",
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
            "templateId": "",
            "message": content,
            "language": "English",
            "fileType": None
        }
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            return Response(status=resp.status_code)
        response_data = resp.json()
        channelId = response_data.get('data', {}).get('channelId')

        wrapped_chunk_channelId = {
            "id": str(uuid.uuid4()),
            "object": channelId,
            "created": 0,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": channelId
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

        def generate_channelId():
            yield f"data: {json.dumps(wrapped_chunk_channelId, ensure_ascii=False)}\n\n".encode('utf-8')

        return Response(generate_channelId(), mimetype='text/event-stream; charset=UTF-8')

    else:
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

        if model_name in ["GPT-4", "dalle3"]:
            model_to_use = "GPT-4"
        elif model_name == "GPT-3.5":
            model_to_use = "Standard"
        elif model_name == "websearch":
            model_to_use = "Web Search"
        else:
            model_to_use = model_name
        data = {
            "isGetJson": True,
            "version": "1.3.6",
            "language": "zh-CN",
            "channelId": channelId,
            "message": last_user_content,
            "model": model_to_use,
            "messageIds": [],
            "improveId": None,
            "richMessageId": None,
            "isNewChat": False,
            "action": None,
            "isGeneratePpt": False,
            "isSlidesChat": False,
            "imageUrls": [],
            "roleEnum": None,
            "pptCoordinates": "",
            "translateLanguage": None,
            "docPromptTemplateId": None
        }
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            return Response(status=resp.status_code)
        if stream:
            return stream_response(req, resp, model_name)
        else:
            return jsonify(resp.text)

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
                        logging.info(f"Wrapped chunk: {wrapped_chunk}")
                        event_data = f"data: {json.dumps(wrapped_chunk, ensure_ascii=False)}\n\n"
                        yield event_data.encode('utf-8')

    logging.info("Exiting stream_response function")
    return Response(generate(), mimetype='text/event-stream; charset=UTF-8')


@app.route("/v1/chat/completions", methods=["GET", "POST", "OPTIONS"])
def onRequest():
    return fetch(request)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3034)
