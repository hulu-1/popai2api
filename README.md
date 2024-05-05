# 用户手册



## docker 启动

```bash
docker run --name popai2api --restart=always -d -p 8888:5000 -e AUTHORIZATION=<AUTHORIZATION> -e CHAT_CHANNEL_ID=<CHAT_CHANNEL_ID> -e DALLE3_CHANNEL_ID=<DALLE3_CHANNEL_ID> -e WEB_SEARCH_CHANNEL_ID=<WEB_SEARCH_CHANNEL_ID> hulu365/popai2api:latest
```

## draw

```text
curl --location --request GET 'http://127.0.0.1:3034/v1/chat/completions' \
--header 'Authorization: Bearer none' \
--header 'Content-Type: application/json' \
--data-raw '{
    "model": "dalle3",
    "messages": [
        {
            "role": "user",
            "content": "画一只猫猫"
        }
    ],
    "stream": false
}'
```
## chat

```text
curl --location --request GET 'http://127.0.0.1:3034/v1/chat/completions' \
--header 'Authorization: Bearer none' \
--header 'Content-Type: application/json' \
--data-raw '{
    "model": "gpt-4",
    "messages": [
        {
            "role": "user",
            "content": "say this is a test"
        }
    ],
    "stream": false
}'
```

## webserarch

```text
curl --location --request GET 'http://127.0.0.1:3034/v1/chat/completions' \
--header 'Authorization: Bearer none' \
--header 'Content-Type: application/json' \
--data-raw '{
    "model": "websearch",
    "messages": [
        {
            "role": "user",
            "content": "今日财经新闻"
        }
    ],
    "stream": false
}'
```