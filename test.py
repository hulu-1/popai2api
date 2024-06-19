import requests

url = "http://127.0.0.1:3000/v1/chat/completions"
headers = {
    "Authorization": "Bearer none",
    "Content-Type": "application/json"
}
data = {
    "model": "gpt-4o",
    "messages": [
        {
            "role": "user",
            "content": "给我讲讲C++的chromium开发，我想修改网页可以调取的API来达到隐藏个人信息的功能"
        }
    ],
    "stream": False
}

response = requests.get(url, headers=headers, json=data)

print(response.status_code)
print(response.json())