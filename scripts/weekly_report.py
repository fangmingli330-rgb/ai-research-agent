"""
weekly_report.py
Generates a weekly research report for a list of companies.
禁止未来函数（no look-ahead bias）
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 假设的股票池
WATCHLIST = [
    "宁德时代",
    "贵州茅台",
    "腾讯控股",
    "阿里巴巴",
    "美团",
    "比亚迪",
    "中国平安",
    "招商银行",
    "长江电力",
    "海康威视"
]

def get_real_data(ticker: str, date: str) -> Dict[str, Any]:
    """
    获取真实市场数据（模拟实现）
    禁止未来函数（no look-ahead bias）
    """
    # 模拟数据，实际应调用API
    import random
    random.seed(hash(ticker + date))
    return {
        "price": round(random.uniform(10, 500), 2),
        "volume": random.randint(1000000, 10000000),
        "pe": round(random.uniform(10, 50), 2),
        "pb": round(random.uniform(1, 10), 2)
    }

def generate_report(date: str = None) -> List[Dict[str, Any]]:
    """
    生成周报，返回信号列表
    禁止未来函数（no look-ahead bias）
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    signals = []
    for ticker in WATCHLIST:
        data = get_real_data(ticker, date)
        # 简单的信号生成逻辑
        if data["pe"] < 20 and data["pb"] < 3:
            action = "buy"
            reason = f"低估值 (PE={data['pe']}, PB={data['pb']})"
            target_weight = 0.1
        elif data["pe"] > 40 or data["pb"] > 8:
            action = "sell"
            reason = f"高估值 (PE={data['pe']}, PB={data['pb']})"
            target_weight = 0.0
        else:
            action = "hold"
            reason = "估值合理"
            target_weight = 0.05
        
        signals.append({
            "ticker": ticker,
            "action": action,
            "reason": reason,
            "target_weight": target_weight,
            "price": data["price"],
            "date": date
        })
    
    return signals

if __name__ == "__main__":
    report = generate_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
