"""
portfolio_manager.py
Generates a test pending order for the portfolio.
Strictly avoids look-ahead bias: signal_date (T) and execution_date (T+1) are separated.
禁止未来函数（no look-ahead bias）
"""

import json
import os
from datetime import datetime, timedelta

PORTFOLIO_DIR = "/root/research_agent/portfolio"
PENDING_ORDERS_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")

def generate_pending_orders(report_date: str) -> None:
    """
    Generate a test pending order for the given report_date.
    The order is saved to pending_orders.json with signal_date = report_date
    and execution_date = report_date + 1 day.
    No look-ahead bias: signal and execution are on different days.
    """
    # Parse report_date to compute execution_date
    signal_date = datetime.strptime(report_date, "%Y-%m-%d")
    execution_date = signal_date + timedelta(days=1)
    execution_date_str = execution_date.strftime("%Y-%m-%d")

    # Build the test order
    test_order = {
        "symbol": "SH_INDEX",
        "target_weight": 0.3,
        "reason": "weekly report test order",
        "is_test_order": True,
        "signal_date": report_date,
        "execution_date": execution_date_str
    }

    # Ensure portfolio directory exists
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)

    # Write the pending orders file (contains only this test order)
    with open(PENDING_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump([test_order], f, ensure_ascii=False, indent=2)

    print(f"[portfolio_manager] Generated 1 test pending order for {report_date}")

if __name__ == "__main__":
    import sys
    report_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    generate_pending_orders(report_date)
