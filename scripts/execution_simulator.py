"""
execution_simulator.py
Reads pending orders from pending_orders.json and executes them using
next-day (T+1) prices obtained from mx_data.py.
Strictly avoids look-ahead bias: execution uses only prices available on execution_date.
禁止未来函数（no look-ahead bias）
"""

import json
import os
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Import mx_data for price retrieval
from scripts.mx_data import get_price

PORTFOLIO_DIR = "portfolio"
PENDING_ORDERS_FILE = os.path.join(PORTFOLIO_DIR, "pending_orders.json")
POSITIONS_FILE = os.path.join(PORTFOLIO_DIR, "positions.json")
TRADES_FILE = os.path.join(PORTFOLIO_DIR, "trades.csv")
PORTFOLIO_VALUE_FILE = os.path.join(PORTFOLIO_DIR, "portfolio_value.csv")

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
    Uses mx_data.get_price(ticker, execution_date).
    禁止未来函数（no look-ahead bias）
    """
    try:
        price = get_price(ticker, execution_date)
        return price
    except Exception as e:
        print(f"[execution_simulator] Error getting price for {ticker} on {execution_date}: {e}")
        return None

def execute_pending_orders(execution_date: str) -> None:
    """
    Execute all pending orders using prices from execution_date.
    Updates positions, records trades, and updates portfolio value.
    禁止未来函数（no look-ahead bias）
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

        # Get execution price (T+1 open)
        price = get_execution_price(ticker, execution_date)
        if price is None:
            print(f"[execution_simulator] Could not get price for {ticker} on {execution_date}, skipping order.")
            continue

        # For simplicity, we assume a fixed number of shares (e.g., 100)
        # In a real system, target_weight would determine quantity.
        shares = 100  # placeholder

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
            "reason": reason
        }
        trades.append(trade)
        executed_orders.append(order)

    # Remove executed orders from pending
    for exec_order in executed_orders:
        pending.remove(exec_order)

    # Save updated data
    save_positions(positions)
    save_pending_orders(pending)

    # Write trades CSV
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["ticker", "action", "signal_date", "execution_date", "execution_price", "shares", "reason"]
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
    import sys
    execution_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    execute_pending_orders(execution_date)
