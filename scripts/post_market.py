import os
import subprocess
import time
from datetime import datetime
import sys
import traceback

# Determine the absolute path to the scripts directory
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts_dir)

# Check for required dependencies before importing them
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

from openai import OpenAI
import feishu_push

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
        print(f"Warning: mx_data.py returned non-zero exit code {result.returncode}. Skipping.")
        continue
    raw_text += f"\n\n{q}\n{result.stdout[:1000]}"

prompt = f"""
你是一个A股策略分析师，请生成盘后总结（结构化研报格式）：

{raw_text}

请先输出一个表格，包含指标名称、最新值、变化方向（涨/跌/平）。然后输出以下分析：
1. 市场整体表现
2. 资金行为（北向/成交量）
3. 市场结构（谁在涨/谁在跌）
4. 明日预判
要求：简洁、有结论，使用中文。
"""

max_retries = 3
analysis = None
for attempt in range(max_retries):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        analysis = response.choices[0].message.content
        break
    except Exception as e:
        print(f"AI request attempt {attempt+1} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
        else:
            print("All AI attempts failed.")
            sys.exit(0)

if analysis is None:
    sys.exit(0)

with open(report_file, "w", encoding="utf-8") as f:
    f.write(f"# 盘后总结 {today}\n\n")
    f.write(analysis)

print(f"盘后报告生成：{report_file}")

# Verify report file exists before pushing
if not os.path.exists(report_file):
    print(f"Error: Report file {report_file} was not created. Skipping Feishu push.")
else:
    # Push to Feishu using card format
    feishu_push.push_card(analysis)
