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
            "content": "收到请回复yessss"
        }
    ],
    "stream": False
}

response = requests.get(url, headers=headers, json=data)

print(response.status_code)
print(response.json())