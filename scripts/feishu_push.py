import sys, requests, json

APP_ID = "cli_a97be1d34a781ceb"
APP_SECRET = "3HmPPOSa0g9nB1w9Vtftgd6aJaKFKMAx"
OPEN_ID = "ou_516f79447932bb772bae0ffc10bf9e46"

file_path = sys.argv[1]
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

text = text[:3800]

res = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", json={"app_id": APP_ID, "app_secret": APP_SECRET})
token = res.json()["tenant_access_token"]

res = requests.post(
    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "receive_id": OPEN_ID,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }
)

print(res.json())
