# 用户手册
## 项目结构

```text
project-root/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── utils.py
    └── routes.py
```


## 功能
- [x] 支持图片上传
- [x] 支持`gpt-4o`
- [x] 模拟对话隔离（根据客户前一条消息作为key）
- [x] 支持多账号加权轮询`（AUTHORIZATION = auth1-权重,auth2-权重,auth3 ）`，如`（AUTHORIZATION = auth1-1,auth2-2,auth3 ）`，兼容前一个版本的`AUTHORIZATION`，不带默认为1，即`（AUTHORIZATION = auth1,auth2,auth3）`等于`（AUTHORIZATION = auth1-1,auth2-1,auth3-1）`
- [x] 支持proxy：`HTTPS_PROXIES = proxy1,proxy2`
- [x] 新增 `/v1/images/generations` 路由，兼容OPENAI文生图报文格式

## 部署 
### docker

```bash
# 默认权重
docker run --name popai2api --restart=always -d -p 3000:3000 -e AUTHORIZATION = {{auth1,auth2,auth3}} hulu365/popai2api:latest

# 定义权重
docker run --name popai2api --restart=always -d -p 3000:3000 -e AUTHORIZATION = {{auth1-1,auth2-3,auth3-5}} hulu365/popai2api:latest
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
