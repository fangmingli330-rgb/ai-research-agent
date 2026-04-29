import os
import sys
import json
import asyncio
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import research_dispatcher
import feishu_push

app = FastAPI()

BASE_DIR = "/root/research_agent"
sys.path.insert(0, BASE_DIR)

@app.post("/feishu/events")
async def feishu_events(request: Request):
    body = await request.json()
    # 1. Print raw body
    print(f"[feishu_event] raw body: {json.dumps(body, ensure_ascii=False)}")

    # Challenge verification
    if "challenge" in body:
        return JSONResponse({"challenge": body["challenge"]})
    
    # Event callback
    event = body.get("event", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {})
    open_id = sender_id.get("open_id", "")
    message = event.get("message", {})
    content_str = message.get("content", "")
    message_id = message.get("message_id", "")
    
    # Parse content JSON
    try:
        content = json.loads(content_str)
        text = content.get("text", "")
    except (json.JSONDecodeError, TypeError):
        text = content_str

    # 2. Print text
    print(f"[feishu_event] text: {text}")
    # 3. Print open_id
    print(f"[feishu_event] open_id: {open_id}")
    
    # Match patterns
    match = re.search(r'(研究公司|公司)\s+(.+)', text)
    if match:
        company_name = match.group(2).strip()
        # 4. Print company_name
        print(f"[feishu_event] company_name: {company_name}")
        # Immediate reply
        reply_text = f"已收到研究任务：{company_name}，正在生成报告。"
        feishu_push.push_text(reply_text, open_id=open_id)
        # Run research in background
        asyncio.create_task(research_dispatcher.dispatch_research(company_name, open_id, message_id))
        return JSONResponse({"msg": "ok"})
    else:
        # 5. Print ignored
        print("[feishu_event] ignored:")
        # Not a research command, ignore
        return JSONResponse({"msg": "ignored"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
