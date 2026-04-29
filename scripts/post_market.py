import os
import subprocess
from datetime import datetime
from openai import OpenAI
import sys
import traceback

# Determine the absolute path to the scripts directory
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts_dir)

import feishu_push

# Check for required dependencies
try:
    import requests
except ImportError:
    print("Error: 'requests' library is not installed. Please run: pip install requests")
    sys.exit(0)

try:
    import openai
except ImportError:
    print("Error: 'openai' library is not installed. Please run: pip install openai")
    sys.exit(0)

client = OpenAI(
 api_key="sk-35dc549095704b04aa21397911b581dc",
 base_url="https://api.deepseek.com"
)

BASE_DIR = "/root/research_agent"
REPORT_DIR = f"{BASE_DIR}/reports"

os.makedirs(REPORT_DIR, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
report_file = f"{REPORT_DIR}/post_market_{today}.md"

queries = [
    "上证指数 今日涨跌幅",
    "创业板指 今日涨跌幅",
    "北向资金 净流入",
    "成交额 A股",
]

raw_text = ""

for q in queries:
    print(f"查询：{q}")
    # Use sys.executable to ensure same Python interpreter
    mx_data_path = "/root/mx-skills/mx-data/mx_data.py"
    if not os.path.exists(mx_data_path):
        print(f"Warning: {mx_data_path} does not exist. Skipping query.")
        continue
    cmd = f'{sys.executable} {mx_data_path} "{q}"'
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    if result.returncode != 0:
        print(f"Warning: mx_data.py returned non-zero exit code {result.returncode}")
        print(f"stderr: {result.stderr[:500]}")
    raw_text += f"\n\n{q}\n{result.stdout[:1000]}"

prompt = f"""
你是一个A股策略分析师，请生成盘后总结：

{raw_text}

输出：
1. 市场整体表现
2. 资金行为（北向/成交量）
3. 市场结构（谁在涨/谁在跌）
4. 明日预判
要求：简洁、有结论
"""

try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )

    analysis = response.choices[0].message.content

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# 盘后总结 {today}\n\n")
        f.write(analysis)

    print(f"盘后报告生成：{report_file}")

    # Push to Feishu using the report file path
    feishu_push.push_text(report_file, is_path=True)

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    # Don't exit with error so cron doesn't complain
    sys.exit(0)
