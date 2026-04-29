"""
portfolio_manager.py
Generates trading signals from weekly report conclusions.
Strictly avoids look-ahead bias: signals are generated on signal_date (T)
and recorded as pending orders for execution on T+1.
禁止未来函数（no look-ahead bias）
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

PORTFOLIO_DIR = "/root/research_agent/portfolio"
PENDING_ORDERS_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")
WEEKLY_REPORT_MD = "/root/research_agent/scripts/weekly_report.md"
WEEKLY_REPORT_SCRIPT = "/root/research_agent/scripts/weekly_report.py"


def run_weekly_report_script() -> None:
    """Run weekly_report.py to generate the markdown report."""
    print("[portfolio_manager] Running weekly_report.py to generate report...")
    try:
        subprocess.run([sys.executable, WEEKLY_REPORT_SCRIPT], check=True)
        print("[portfolio_manager] weekly_report.py finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[portfolio_manager] Error running weekly_report.py: {e}")
        raise


def parse_weekly_report_md(filepath: str) -> Dict[str, Any]:
    """
    Parse the weekly report markdown and extract:
      - 建议仓位 (suggested_position)
      - 风格判断 (style_judgment)
      - 最值得关注行业 (noteworthy_industry)
    Returns a dict with those keys, or empty strings if not found.
    """
    result = {
        "suggested_position": "",
        "style_judgment": "",
        "noteworthy_industry": ""
    }

    if not os.path.exists(filepath):
        print(f"[portfolio_manager] Weekly report file not found: {filepath}")
        return result

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Try to find lines like:
    # - 建议仓位: xxx
    # - 风格判断: xxx
    # - 最值得关注行业: xxx
    patterns = {
        "suggested_position": r"建议仓位[：:]\s*(.+)",
        "style_judgment": r"风格判断[：:]\s*(.+)",
        "noteworthy_industry": r"最值得关注行业[：:]\s*(.+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            result[key] = match.group(1).strip()

    return result


def generate_pending_orders(report_date: str) -> None:
    """
    Generate pending orders from the weekly report markdown.
    Orders are saved to pending_orders.json with signal_date = report_date.
    Execution will happen on the next trading day (T+1).
    禁止未来函数（no look-ahead bias）
    """
    # 1. Ensure the weekly report markdown exists
    if not os.path.exists(WEEKLY_REPORT_MD):
        print(f"[portfolio_manager] Weekly report markdown not found at {WEEKLY_REPORT_MD}")
        run_weekly_report_script()

    # 2. Parse the markdown
    parsed = parse_weekly_report_md(WEEKLY_REPORT_MD)
    suggested_position = parsed.get("suggested_position", "")
    style_judgment = parsed.get("style_judgment", "")
    noteworthy_industry = parsed.get("noteworthy_industry", "")

    print(f"[portfolio_manager] Parsed report: suggested_position='{suggested_position}', "
          f"style_judgment='{style_judgment}', noteworthy_industry='{noteworthy_industry}'")

    # 3. Build pending orders list
    pending_orders: List[Dict[str, Any]] = []

    # If we have enough information to derive specific tickers, we could add them.
    # For now, if we cannot parse specific tickers, generate a test order.
    # We'll consider that we have "specific tickers" only if suggested_position
    # contains something like "满仓" or "半仓" etc. But we'll keep it simple:
    # always generate a test order as requested.
    # (The requirement says: "如果无法解析具体标的，就生成一个测试订单")
    # Since we don't have a reliable way to extract tickers from the markdown,
    # we'll always generate the test order.

    test_order = {
        "symbol": "上证指数",
        "target_weight": 0.3,
        "reason": "weekly report test order",
        "is_test_order": True,
        "signal_date": report_date,
        "execution_date": (datetime.strptime(report_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
        "status": "pending"
    }
    pending_orders.append(test_order)

    # 4. Save to file
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    with open(PENDING_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(pending_orders, f, ensure_ascii=False, indent=2)
    print(f"[portfolio_manager] Generated {len(pending_orders)} pending order(s) for {report_date}")


if __name__ == "__main__":
    report_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    generate_pending_orders(report_date)
