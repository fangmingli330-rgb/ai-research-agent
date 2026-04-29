"""
mx_data.py
Provides market data functions with strict no-look-ahead bias.
禁止未来函数（no look-ahead bias）
"""

import os
import json
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 模拟数据缓存
_DATA_CACHE: Dict[str, Dict[str, Any]] = {}

def _load_cache():
    """加载缓存数据（模拟）"""
    global _DATA_CACHE
    # 实际实现中会从数据库或API加载
    pass

def get_price(ticker: str, date: str) -> Optional[float]:
    """
    获取指定股票在指定日期的开盘价。
    只使用 date 当天及之前的数据，禁止未来函数。
    禁止未来函数（no look-ahead bias）
    """
    # 模拟实现：返回随机价格
    import random
    random.seed(hash(ticker + date))
    # 确保价格为正
    price = round(random.uniform(10, 500), 2)
    return price

def get_historical_prices(ticker: str, start_date: str, end_date: str) -> Dict[str, float]:
    """
    获取历史价格序列（仅用于回测，需确保 end_date <= 当前日期）
    禁止未来函数（no look-ahead bias）
    """
    prices = {}
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        prices[date_str] = get_price(ticker, date_str)
        current += timedelta(days=1)
    return prices

if __name__ == "__main__":
    # 接受命令行参数：ticker date
    if len(sys.argv) >= 3:
        ticker = sys.argv[1]
        date = sys.argv[2]
        price = get_price(ticker, date)
        if price is not None:
            print(price)
        else:
            print("ERROR: could not get price")
    else:
        # 测试
        print(get_price("宁德时代", "2026-04-28"))
