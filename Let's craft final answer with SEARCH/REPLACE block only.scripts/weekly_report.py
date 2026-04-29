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
REPORT_DIR = f"{BASE_DIR}/reports/weekly"
LOG_DIR = f"{BASE_DIR}/logs"

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
week_number = datetime.now().isocalendar()[1]
report_file = f"{REPORT_DIR}/weekly_{today}.md"
log_file = f"{LOG_DIR}/weekly_{today}.log"

def log(msg):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {msg}\n")
    print(msg)

log("开始生成周报")

queries = [
    "上证指数 本周涨跌幅",
    "创业板指 本周涨跌幅",
    "中证红利 本周涨跌幅",
    "北向资金 本周净流入",
    "成交额 A股 本周",
    "上证指数 最新价",
    "创业板指 最新价",
    "中证红利 最新价",
    "10年期国债收益率",
    "美元指数",
]

raw_text = ""

mx_data_path = "/root/mx-skills/mx-data/mx_data.py"
if not os.path.exists(mx_data_path):
    log(f"Error: {mx_data_path} does not exist. Exiting.")
    sys.exit(0)

for q in queries:
    log(f"查询：{q}")
    cmd = f'{sys.executable} {mx_data_path} "{q}"'
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    if result.returncode != 0:
        log(f"Warning: mx_data.py returned non-zero exit code {result.returncode}. Skipping query.")
        continue
    raw_text += f"\n\n{q}\n{result.stdout[:1000]}"

log("开始AI分析...")

prompt = f"""
你是一个A股策略分析师，请生成周报（结构化研报格式）：

{raw_text}

请先输出一个表格，包含指标名称、本周值、变化方向（涨/跌/平）。然后输出以下分析：
1. 本周市场整体表现
2. 上证指数、创业板指、中证红利本周表现
3. 市场风格判断：成长 / 价值 / 红利 / 小盘
4. 资金面总结
5. 本周主要变化
6. 下周重点关注方向
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
        log(f"AI request attempt {attempt+1} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
        else:
            log("All AI attempts failed.")
            sys.exit(0)

if analysis is None:
    log("AI analysis returned None. Exiting.")
    sys.exit(0)

with open(report_file, "w", encoding="utf-8") as f:
    f.write(f"# 周报 {today} (第{week_number}周)\n\n")
    f.write(analysis)

log(f"周报生成：{report_file}")

# Verify report file exists before pushing
if not os.path.exists(report_file):
    log(f"Error: Report file {report_file} was not created. Skipping Feishu push.")
else:
    # Push to Feishu using card format
    feishu_push.push_card(analysis)
    log("Feishu push completed.")
