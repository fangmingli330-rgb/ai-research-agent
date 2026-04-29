"""
run_daily.py
Daily orchestration script that runs the full pipeline.
禁止未来函数（no look-ahead bias）
"""

import os
import sys
from datetime import datetime, timedelta

def run_daily(date: str = None):
    """
    Execute daily tasks:
    1. Generate weekly report (if today is Monday) and save signals
    2. Generate pending orders from weekly signals
    3. Execute pending orders
    4. Generate portfolio report
    禁止未来函数（no look-ahead bias）
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"=== Running daily pipeline for {date} ===")
    
    # Step 1: Generate weekly report on Mondays
    from scripts.weekly_report import generate_report
    weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
    if weekday == 0:  # Monday
        print("Generating weekly report...")
        signals = generate_report(date)
        print(f"Generated {len(signals)} signals")
        # Save signals for portfolio manager
        os.makedirs("portfolio", exist_ok=True)
        with open("portfolio/weekly_signals.json", "w", encoding="utf-8") as f:
            import json
            json.dump(signals, f, ensure_ascii=False, indent=2)
        # Generate pending orders from signals
        from scripts.portfolio_manager import generate_pending_orders
        generate_pending_orders(date)
    
    # Step 2: Execute pending orders (every day)
    from scripts.execution_simulator import execute_pending_orders
    print("Executing pending orders...")
    execute_pending_orders(date)
    
    # Step 3: Generate portfolio report
    from scripts.portfolio_report import generate_report
    print("Generating portfolio report...")
    report = generate_report()
    print(report)
    
    print(f"=== Daily pipeline completed for {date} ===")

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run_daily(date)
