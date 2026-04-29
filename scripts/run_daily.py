import os
import subprocess
from datetime import datetime

BASE_DIR = "/root/research_agent"
WATCHLIST = f"{BASE_DIR}/config/watchlist.txt"
OUTPUT_DIR = f"{BASE_DIR}/output"
LOG_DIR = f"{BASE_DIR}/logs"
MX_DATA = "/root/mx-skills/mx-data/mx_data.py"

today = datetime.now().strftime("%Y-%m-%d")
log_file = f"{LOG_DIR}/run_{today}.log"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

with open(WATCHLIST, "r", encoding="utf-8") as f:
    queries = [line.strip() for line in f if line.strip()]

with open(log_file, "a", encoding="utf-8") as log:
    log.write(f"\n===== Run at {datetime.now()} =====\n")

    for q in queries:
        log.write(f"\n[QUERY] {q}\n")
        print(f"📊 查询：{q}")

        cmd = f'python3 {MX_DATA} "{q}"'
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        log.write(result.stdout)
        log.write(result.stderr)

        if result.returncode == 0:
            print(f"✅ 成功：{q}")
        else:
            print(f"❌ 失败：{q}")

print("全部查询完成")
