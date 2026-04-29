import os
import json
from datetime import datetime

BASE_DIR = "/root/research_agent"
OUTPUT_DIR = "/root/.openclaw/workspace/mx_data/output"
REPORT_DIR = f"{BASE_DIR}/output"

today = datetime.now().strftime("%Y-%m-%d")
report_file = f"{REPORT_DIR}/daily_report_{today}.md"

def extract_price(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        table = data["data"]["dataTableDTOList"][0]["table"]
        latest = list(table.values())[0][-1]
        return latest
    except:
        return "N/A"

results = []

for filename in os.listdir(OUTPUT_DIR):
    if filename.endswith("_raw.json"):
        name = filename.replace("mx_data_", "").replace("_raw.json", "")
        path = os.path.join(OUTPUT_DIR, filename)
        price = extract_price(path)
        results.append((name, price))

with open(report_file, "w", encoding="utf-8") as r:
    r.write(f"# 每日投研简报 {today}\n\n")

    for name, price in results:
        r.write(f"## {name}\n")
        r.write(f"- 最新价格：{price}\n")

        # 简单策略信号
        if price != "N/A":
            try:
                p = float(price)
                if p > 1000:
                    r.write("- 判断：高价股，关注回调风险\n")
                else:
                    r.write("- 判断：低位或中位，关注趋势\n")
            except:
                r.write("- 判断：无法解析\n")

        r.write("\n---\n\n")

print(f"报告已升级生成: {report_file}")
