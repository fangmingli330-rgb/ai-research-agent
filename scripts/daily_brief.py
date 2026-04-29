import os
import subprocess
from datetime import datetime
from openai import OpenAI
import sys
import traceback

# Add the scripts directory to path so we can import feishu_push
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_push

client = OpenAI(
 api_key="sk-35dc549095704b04aa21397911b581dc",
 base_url="https://api.deepseek.com"
)

BASE_DIR = "/root/research_agent"
REPORT_DIR = f"{BASE_DIR}/reports"

os.makedirs(REPORT_DIR, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
report_file = f"{REPORT_DIR}/daily_brief_{today}.md"

queries = [
    "上证指数 最新价",
    "创业板指 最新价",
    "中证红利 最新价",
    "10年期国债收益率",
    "美元指数"
]

raw_text = ""

for q in queries:
    print(f"查询：{q}")
    cmd = f'python3 /root/mx-skills/mx-data/mx_data.py "{q}"'
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    raw_text += f"\n\n{q}\n{result.stdout[:1000]}"

print("开始AI分析...")

prompt = f"""
你是一个A股策略分析师，请生成盘前简报：

{raw_text}

输出：
1. 宏观判断（利率/美元/流动性）
2. 市场情绪（风险偏好）
3. 风格判断（成长/价值）
4. 今日重点关注方向（3个）
要求：简洁、有结论
"""

try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )

    analysis = response.choices[0].message.content

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# 盘前简报 {today}\n\n")
        f.write(analysis)

    print(f"盘前报告生成：{report_file}")

    # Push to Feishu
    feishu_push.push_text(analysis)

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    # Don't exit with error so cron doesn't complain
    sys.exit(0)
