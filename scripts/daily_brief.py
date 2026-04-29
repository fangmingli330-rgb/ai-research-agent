import os
import subprocess
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

    # Verify report file exists before pushing
    if not os.path.exists(report_file):
        print(f"Error: Report file {report_file} was not created. Skipping Feishu push.")
    else:
        # Push to Feishu using the report file path
        feishu_push.push_text(report_file, is_path=True)

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    # Don't exit with error so cron doesn't complain
    sys.exit(0)
