"""
portfolio_manager.py
Generates trading signals from weekly report conclusions.
Strictly avoids look-ahead bias: signals are generated on signal_date (T)
and recorded as pending orders for execution on T+1.
禁止未来函数（no look-ahead bias）
"""

import json
import os
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any

PORTFOLIO_DIR = "portfolio"
PENDING_ORDERS_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")
WEEKLY_REPORT_DIR = "/root/research_agent/reports/weekly"
WEEKLY_REPORT_FILE = "/root/research_agent/scripts/weekly_report.md"

def find_latest_weekly_report() -> str:
    """
    Find the most recent .md file in WEEKLY_REPORT_DIR,
    or fallback to WEEKLY_REPORT_FILE if the directory is empty/missing.
    Returns the full path, or None if none found.
    """
    # Try directory first
    if os.path.isdir(WEEKLY_REPORT_DIR):
        md_files = glob.glob(os.path.join(WEEKLY_REPORT_DIR, "*.md"))
        if md_files:
            md_files.sort(key=os.path.getmtime, reverse=True)
            return md_files[0]
    # Fallback to single file
    if os.path.isfile(WEEKLY_REPORT_FILE):
        return WEEKLY_REPORT_FILE
    return None

def parse_signals_from_report(report_path: str) -> List[Dict[str, Any]]:
    """
    Parse a weekly report markdown file for buy/sell signals.
    Simple heuristic: look for lines containing "买入" or "卖出" with a ticker.
    Returns a list of signal dicts.
    """
    signals = []
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[portfolio_manager] Error reading report {report_path}: {e}")
        return signals

    for line in lines:
        line = line.strip()
        # Look for patterns like: "买入 上证指数" or "卖出 贵州茅台"
        if "买入" in line:
            # Extract ticker (assume it's the word after "买入")
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "买入" and i + 1 < len(parts):
                    ticker = parts[i + 1].strip()
                    signals.append({
                        "ticker": ticker,
                        "action": "buy",
                        "reason": "weekly report signal",
                        "target_weight": 0.1  # default
                    })
        elif "卖出" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "卖出" and i + 1 < len(parts):
                    ticker = parts[i + 1].strip()
                    signals.append({
                        "ticker": ticker,
                        "action": "sell",
                        "reason": "weekly report signal",
                        "target_weight": 0.0
                    })
    return signals

def generate_test_order(report_date: str) -> List[Dict[str, Any]]:
    """
    Generate a test order when no real signals are available.
    """
    order = {
        "ticker": "上证指数",
        "action": "buy",
        "signal_date": report_date,
        "reason": "weekly_report investment conclusion test",
        "target_weight": 0.3,
        "is_test_order": True,
        "status": "pending"
    }
    return [order]

def generate_pending_orders(report_date: str) -> None:
    """
    Generate pending orders from weekly signals for the given report_date.
    Orders are saved to pending_orders.json with signal_date = report_date.
    Execution will happen on the next trading day (T+1).
    禁止未来函数（no look-ahead bias）
    """
    # Try to get signals from latest weekly report
    latest_report = find_latest_weekly_report()
    signals = []
    if latest_report:
        print(f"[portfolio_manager] Found weekly report: {latest_report}")
        signals = parse_signals_from_report(latest_report)
    else:
        print(f"[portfolio_manager] No weekly report found in {WEEKLY_REPORT_DIR} or {WEEKLY_REPORT_FILE}")

    if not signals:
        print("[portfolio_manager] No signals found in report, generating test order.")
        pending_orders = generate_test_order(report_date)
    else:
        pending_orders = []
        for sig in signals:
            ticker = sig.get("ticker")
            action = sig.get("action", "hold")
            reason = sig.get("reason", "")
            target_weight = sig.get("target_weight", 0.0)
            if action in ("buy", "sell"):
                order = {
                    "ticker": ticker,
                    "action": action,
                    "signal_date": report_date,
                    "reason": reason,
                    "target_weight": target_weight,
                    "is_test_order": False,
                    "status": "pending"
                }
                pending_orders.append(order)

    # Save to file
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    with open(PENDING_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(pending_orders, f, ensure_ascii=False, indent=2)
    print(f"[portfolio_manager] Generated {len(pending_orders)} pending orders for {report_date}")

if __name__ == "__main__":
    import sys
    report_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    generate_pending_orders(report_date)
