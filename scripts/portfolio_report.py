"""
portfolio_report.py
Generates a report of current positions, trade history, returns, and max drawdown.
禁止未来函数（no look-ahead bias）
"""

import json
import os
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

PORTFOLIO_DIR = "portfolio"
POSITIONS_FILE = os.path.join(PORTFOLIO_DIR, "positions.json")
TRADES_FILE = os.path.join(PORTFOLIO_DIR, "trades.csv")
PORTFOLIO_VALUE_FILE = os.path.join(PORTFOLIO_DIR, "portfolio_value.csv")

def load_positions() -> Dict[str, Any]:
    if not os.path.exists(POSITIONS_FILE):
        return {}
    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_trades() -> List[Dict[str, Any]]:
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def load_value_history() -> List[Dict[str, Any]]:
    if not os.path.exists(PORTFOLIO_VALUE_FILE):
        return []
    with open(PORTFOLIO_VALUE_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def calculate_max_drawdown(value_history: List[Dict[str, Any]]) -> float:
    """
    Calculate maximum drawdown from portfolio value history.
    禁止未来函数（no look-ahead bias）
    """
    if not value_history:
        return 0.0
    peak = float(value_history[0]["total_value"])
    max_dd = 0.0
    for entry in value_history:
        val = float(entry["total_value"])
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd

def calculate_returns(value_history: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate total return and daily returns.
    禁止未来函数（no look-ahead bias）
    """
    if len(value_history) < 2:
        return {"total_return": 0.0, "daily_returns": []}
    initial = float(value_history[0]["total_value"])
    final = float(value_history[-1]["total_value"])
    total_return = (final - initial) / initial if initial != 0 else 0.0
    daily_returns = []
    for i in range(1, len(value_history)):
        prev = float(value_history[i-1]["total_value"])
        curr = float(value_history[i]["total_value"])
        if prev != 0:
            daily_returns.append((curr - prev) / prev)
        else:
            daily_returns.append(0.0)
    return {"total_return": total_return, "daily_returns": daily_returns}

def generate_report() -> str:
    """
    Generate a human-readable portfolio report.
    禁止未来函数（no look-ahead bias）
    """
    positions = load_positions()
    trades = load_trades()
    value_history = load_value_history()

    lines = []
    lines.append("=" * 60)
    lines.append("Portfolio Report")
    lines.append("=" * 60)
    lines.append("")

    # Current positions
    lines.append("--- Current Positions ---")
    if positions:
        for ticker, pos in positions.items():
            lines.append(f"{ticker}: {pos['shares']} shares @ avg cost {pos['avg_cost']:.2f}")
    else:
        lines.append("No positions.")
    lines.append("")

    # Trade history
    lines.append("--- Trade History ---")
    if trades:
        for t in trades[-10:]:  # last 10 trades
            lines.append(f"{t['execution_date']} {t['action']} {t['ticker']} @ {t['execution_price']} ({t['reason']})")
    else:
        lines.append("No trades yet.")
    lines.append("")

    # Returns
    lines.append("--- Returns ---")
    returns = calculate_returns(value_history)
    lines.append(f"Total return: {returns['total_return']*100:.2f}%")
    if returns['daily_returns']:
        avg_daily = sum(returns['daily_returns']) / len(returns['daily_returns'])
        lines.append(f"Average daily return: {avg_daily*100:.2f}%")
    lines.append("")

    # Max drawdown
    lines.append("--- Max Drawdown ---")
    max_dd = calculate_max_drawdown(value_history)
    lines.append(f"Maximum drawdown: {max_dd*100:.2f}%")
    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

if __name__ == "__main__":
    print(generate_report())
