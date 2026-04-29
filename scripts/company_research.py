import os
import subprocess
from datetime import datetime
from openai import OpenAI

# ====== API ======
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ====== 路径 ======
BASE_DIR = "/root/research_agent"
MX_DATA = "/root/mx-skills/mx-data/mx_data.py"
REPORT_DIR = f"{BASE_DIR}/reports/company"

os.makedirs(REPORT_DIR, exist_ok=True)

# ====== 输入 ======
company = input("请输入要研究的公司名称：").strip()
today = datetime.now().strftime("%Y-%m-%d")
report_file = f"{REPORT_DIR}/{company}_research_{today}.md"

# ====== 查询列表 ======
queries = [
    f"{company} 最新价",
    f"{company} 市盈率 市净率 市值",
    f"{company} 营业收入 净利润 近三年",
    f"{company} 毛利率 净利率 ROE 近三年",
    f"{company} 主营业务",
    f"{company} 所属行业",
    f"{company} 前十大股东",
]

raw_text = ""

# ====== 数据抓取 ======
for q in queries:
    print(f"查询：{q}")
    cmd = f'python3 {MX_DATA} "{q}"'
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    raw_text += f"\n\n{q}\n{result.stdout[:2000]}"

# ====== AI分析 ======
print("开始AI分析...")

prompt = f"""
你是一个专业基金经理，请分析公司 {company}：

{raw_text}

输出：
1. 公司是干什么的
2. 行业地位
3. 财务质量（好/一般/差 + 原因）
4. 估值（贵/合理/便宜）
5. 投资逻辑（3点）
6. 风险（3点）

要求：简洁、有判断
"""

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": prompt}]
)

analysis = response.choices[0].message.content

# ====== 写报告 ======
with open(report_file, "w", encoding="utf-8") as f:
    f.write(f"# {company} 投研报告 {today}\n\n")
    f.write("## 原始数据\n")
    f.write(raw_text[:5000])
    f.write("\n\n## AI分析\n\n")
    f.write(analysis)

print(f"报告生成：{report_file}")
