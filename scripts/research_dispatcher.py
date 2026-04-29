import os
import sys
import subprocess
from datetime import datetime
import feishu_push

BASE_DIR = "/root/research_agent"
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
COMPANY_RESEARCH_SCRIPT = os.path.join(SCRIPTS_DIR, "company_research.py")
REPORT_DIR = os.path.join(BASE_DIR, "reports", "company")

async def dispatch_research(company_name: str, open_id: str, message_id: str):
    # Run company_research.py as subprocess
    cmd = ["python3", COMPANY_RESEARCH_SCRIPT, company_name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            error_msg = f"研究 {company_name} 失败：{result.stderr[:500]}"
            feishu_push.push_text(error_msg, open_id=open_id)
            return
    except subprocess.TimeoutExpired:
        feishu_push.push_text(f"研究 {company_name} 超时", open_id=open_id)
        return
    
    # Read the generated report
    today = datetime.now().strftime("%Y-%m-%d")
    report_file = os.path.join(REPORT_DIR, f"{company_name}_research_{today}.md")
    if not os.path.exists(report_file):
        feishu_push.push_text(f"报告文件未生成：{report_file}", open_id=open_id)
        return
    
    with open(report_file, "r", encoding="utf-8") as f:
        report_content = f.read()
    
    # Push card with report
    feishu_push.push_card(report_content, open_id=open_id)
    # Also send a text notification
    feishu_push.push_text(f"{company_name} 深度研究报告已生成", open_id=open_id)
