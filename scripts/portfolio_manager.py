import os
import json
from datetime import datetime, timedelta

# NO LOOK-AHEAD BIAS:
# signal_date (T) != execution_date (T+1)
# 不允许当天信号当天成交

PORTFOLIO_DIR = "/root/research_agent/portfolio"
PENDING_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")

def ensure_dir():
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)

def generate_test_order():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    return [{
        "symbol": "SH_INDEX",
        "target_weight": 0.3,
        "signal_date": str(today),
        "execution_date": str(tomorrow),
        "reason": "weekly report test order",
        "is_test_order": True
    }]

def main():
    ensure_dir()
    orders = generate_test_order()

    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

    print(f"[portfolio_manager] Generated {len(orders)} pending orders")

if __name__ == "__main__":
    main()
