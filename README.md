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
- [x] 支持gpt-4o
- [x] 模拟对话隔离（根据客户前一条消息作为key）
- [x] 支持多账号轮询（AUTHORIZATION = auth1,auth2,auth3 ）
- [x] 支持proxy：HTTPS_PROXIES = proxy1,proxy2
- [x] 新增 “ /v1/images/generations” 路由，兼容OPENAI文生图报文格式
- [x] 尝试过盾：新增环境变量：RECAPTCHA_SECRET 

## 前置条件
- popai 账号
- RECAPTCHA_SECRET： [google网站](https://www.google.com/recaptcha/admin/create)  获取
        ![img.png](app%2Fdocs%2Fimg.png)

## 部署 
### docker

```bash
docker run --name popai2api --restart=always -d -p 3000:3000 -e AUTHORIZATION = {{auth1,auth2,auth3}} hulu365/popai2api:latest
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