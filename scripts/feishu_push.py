import sys
import requests
import json
import time
import os
import re

APP_ID = "cli_a97be1d34a781ceb"
APP_SECRET = "3HmPPOSa0g9nB1w9Vtftgd6aJaKFKMAx"
OPEN_ID = "ou_516f79447932bb772bae0ffc10bf9e46"

def push_text(text_or_path, max_retries=3, is_path=False, open_id=None):
    """
    Push a text message to Feishu user.
    If is_path is True, text_or_path is treated as a file path and its content is read.
    Retries up to max_retries times on failure.
    open_id: if provided, send to that user; otherwise use the hardcoded OPEN_ID.
    """
    if is_path:
        with open(text_or_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = text_or_path

    # Truncate to 3800 characters as Feishu limit
    text = text[:3800]

    receive_id = open_id if open_id else OPEN_ID

    for attempt in range(max_retries):
        try:
            # Get tenant access token
            res = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": APP_ID, "app_secret": APP_SECRET},
                timeout=10
            )
            res.raise_for_status()
            token = res.json()["tenant_access_token"]

            # Send message
            res = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                },
                timeout=10
            )
            res.raise_for_status()
            print(f"Feishu push succeeded: {res.json()}")
            return
        except Exception as e:
            print(f"Feishu push attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print("All Feishu push attempts failed.")

def push_card(text, max_retries=3, open_id=None):
    """
    Push a card message to Feishu user.
    The text should be a markdown report with a first line starting with '# ' as title.
    open_id: if provided, send to that user; otherwise use the hardcoded OPEN_ID.
    """
    lines = text.split('\n')
    title = "报告"
    body_lines = []
    for i, line in enumerate(lines):
        if line.startswith('# '):
            title = line[2:].strip()
            # skip this line for body
            continue
        body_lines.append(line)
    body = '\n'.join(body_lines).strip()

    # Truncate body to 3800 characters
    body = body[:3800]

    receive_id = open_id if open_id else OPEN_ID

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": body
            }
        ]
    }

    for attempt in range(max_retries):
        try:
            # Get tenant access token
            res = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": APP_ID, "app_secret": APP_SECRET},
                timeout=10
            )
            res.raise_for_status()
            token = res.json()["tenant_access_token"]

            # Send message
            res = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card)
                },
                timeout=10
            )
            res.raise_for_status()
            print(f"Feishu card push succeeded: {res.json()}")
            return
        except Exception as e:
            print(f"Feishu card push attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print("All Feishu card push attempts failed.")

if __name__ == "__main__":
    # Allow running directly with a file path argument (original behavior)
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        push_text(file_path, is_path=True)
    else:
        print("Usage: python feishu_push.py <file_path>")
