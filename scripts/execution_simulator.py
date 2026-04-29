"""
execution_simulator.py
Reads pending orders from pending_orders.json and executes them using
next-day (T+1) prices obtained from mx_data.py via subprocess.
Strictly avoids look-ahead bias: execution uses only prices available on execution_date.
禁止同日买卖，防止事后诸葛亮（no same-day trade, prevent hindsight bias）
"""

import json
import os
import csv
import subprocess
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

PORTFOLIO_DIR = "portfolio"
PENDING_ORDERS_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")
POSITIONS_FILE = os.path.join(PORTFOLIO_DIR, "positions.json")
TRADES_FILE = os.path.join(PORTFOLIO_DIR, "trades.csv")
PORTFOLIO_VALUE_FILE = os.path.join(PORTFOLIO_DIR, "portfolio_value.csv")

MX_DATA_SCRIPT = "/root/mx-skills/mx-data/mx_data.py"

def load_pending_orders() -> List[Dict[str, Any]]:
    """Load pending orders from file."""
    if not os.path.exists(PENDING_ORDERS_FILE):
        return []
    with open(PENDING_ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_pending_orders(orders: List[Dict[str, Any]]) -> None:
    """Save pending orders back to file."""
    with open(PENDING_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def load_positions() -> Dict[str, Any]:
    """Load current positions from file."""
    if not os.path.exists(POSITIONS_FILE):
        return {}
    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_positions(positions: Dict[str, Any]) -> None:
    """Save positions to file."""
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)

def get_execution_price(ticker: str, execution_date: str) -> Optional[float]:
    """
    Get the opening price for ticker on execution_date.
    Uses subprocess to call /root/mx-skills/mx-data/mx_data.py.
    If that fails, falls back to a mock price (100.0) and prints a warning.
    禁止同日买卖，防止事后诸葛亮
    """
    # Try real data source first
    if os.path.exists(MX_DATA_SCRIPT):
        try:
            result = subprocess.run(
                [sys.executable, MX_DATA_SCRIPT, ticker, execution_date],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    try:
                        price = float(output)
                        return price
                    except ValueError:
                        print(f"[execution_simulator] Could not parse price from mx_data output: {output}")
            else:
                print(f"[execution_simulator] mx_data.py returned error: {result.stderr}")
        except Exception as e:
            print(f"[execution_simulator] Error calling mx_data.py: {e}")
    else:
        print(f"[execution_simulator] mx_data.py not found at {MX_DATA_SCRIPT}")

    # Fallback: mock price
    print(f"[execution_simulator] WARNING: Using mock price 100.0 for {ticker} on {execution_date}")
    return 100.0

def execute_pending_orders(execution_date: str) -> None:
    """
    Execute all pending orders using prices from execution_date.
    Updates positions, records trades, and updates portfolio value.
    禁止同日买卖，防止事后诸葛亮
    """
    pending = load_pending_orders()
    if not pending:
        print("[execution_simulator] No pending orders to execute.")
        return

    positions = load_positions()
    trades = []
    # Read existing trades if any
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            trades = list(reader)

    executed_orders = []
    for order in pending:
        ticker = order["ticker"]
        action = order["action"]
        signal_date = order["signal_date"]
        reason = order.get("reason", "")
        target_weight = order.get("target_weight", 0.0)
        is_test = order.get("is_test_order", False)
        # 读取 shares 字段，若缺失则使用默认值 100（必须为正数）
        shares = order.get("shares", 100)
        if shares <= 0:
            print(f"[execution_simulator] Invalid shares ({shares}) for {ticker}, skipping order.")
            continue

        # 禁止同日买卖：如果 execution_date <= signal_date，则跳过此订单
        if execution_date <= signal_date:
            print(f"[execution_simulator] 禁止同日买卖，等待下一交易日: {ticker} signal_date={signal_date} execution_date={execution_date}")
            continue

        # Get execution price (T+1 open)
        price = get_execution_price(ticker, execution_date)
        if price is None:
            print(f"[execution_simulator] Could not get price for {ticker} on {execution_date}, skipping order.")
            continue

        # Update positions
        if action == "buy":
            if ticker in positions:
                positions[ticker]["shares"] += shares
                # Update average cost
                old_shares = positions[ticker]["shares"] - shares
                old_cost = positions[ticker]["avg_cost"]
                new_cost = (old_cost * old_shares + price * shares) / positions[ticker]["shares"]
                positions[ticker]["avg_cost"] = new_cost
            else:
                positions[ticker] = {"shares": shares, "avg_cost": price}
        elif action == "sell":
            if ticker in positions:
                sell_shares = min(positions[ticker]["shares"], shares)
                positions[ticker]["shares"] -= sell_shares
                if positions[ticker]["shares"] <= 0:
                    del positions[ticker]
            else:
                print(f"[execution_simulator] No position to sell for {ticker}, skipping.")
                continue

        # Record trade
        trade = {
            "ticker": ticker,
            "action": action,
            "signal_date": signal_date,
            "execution_date": execution_date,
            "execution_price": price,
            "shares": shares if action == "buy" else -shares,
            "reason": reason,
            "is_test_order": is_test
        }
        trades.append(trade)
        executed_orders.append(order)

    # Remove executed orders from pending (skipped orders remain)
    for exec_order in executed_orders:
        pending.remove(exec_order)

    # Save updated data
    save_positions(positions)
    save_pending_orders(pending)

    # Write trades CSV
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["ticker", "action", "signal_date", "execution_date", "execution_price", "shares", "reason", "is_test_order"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trades)

    # Update portfolio value
    total_value = 0.0
    for ticker, pos in positions.items():
        p = get_execution_price(ticker, execution_date)
        if p is not None:
            total_value += pos["shares"] * p
    # Read existing value history
    value_history = []
    if os.path.exists(PORTFOLIO_VALUE_FILE):
        with open(PORTFOLIO_VALUE_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            value_history = list(reader)
    value_entry = {"date": execution_date, "total_value": total_value}
    value_history.append(value_entry)
    with open(PORTFOLIO_VALUE_FILE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["date", "total_value"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(value_history)

    print(f"[execution_simulator] Executed {len(executed_orders)} orders on {execution_date}")

if __name__ == "__main__":
    execution_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    execute_pending_orders(execution_date)
