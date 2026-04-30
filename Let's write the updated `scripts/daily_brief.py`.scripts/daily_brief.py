#!/usr/bin/env python3
"""
Daily Brief Generator – A股盘前简报

Generates a pre‑market briefing report with strict data integrity checks.
"""

import sys
import os
import json
import logging
import datetime
import urllib.parse
import re
from typing import Dict, List, Optional, Any, Tuple

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.mx_data import get_price, get_historical_prices
from scripts.feishu_push import push_text, push_card

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = "logs"
REPORT_DIR = "reports/pre_market"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

logger = logging.getLogger("daily_brief")
logger.setLevel(logging.DEBUG)

# File handler for main log
fh = logging.FileHandler(os.path.join(LOG_DIR, "daily_brief.log"), encoding="utf-8")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# File handler for error log
efh = logging.FileHandler(os.path.join(LOG_DIR, "daily_brief_error.log"), encoding="utf-8")
efh.setLevel(logging.ERROR)
efh.setFormatter(formatter)
logger.addHandler(efh)

# Also log to console
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# ---------------------------------------------------------------------------
# Indicator definitions
# ---------------------------------------------------------------------------
IndicatorRecord = Dict[str, Any]

INDICATORS = [
    {"name": "上证指数 最新价", "ticker": "000001.SH", "type": "price"},
    {"name": "创业板指 最新价", "ticker": "399006.SZ", "type": "price"},
    {"name": "中证红利 最新价", "ticker": "000922.CSI", "type": "price"},
    {"name": "10年期国债收益率", "ticker": "CN10YR", "type": "yield"},
    {"name": "美元指数", "ticker": "USDX", "type": "index"},
    {"name": "离岸人民币", "ticker": "USDCNH", "type": "forex"},
    {"name": "两市成交额 A股", "ticker": "TOTAL_SH_SZ_TURNOVER", "type": "turnover"},
    {"name": "北向资金 净流入", "ticker": "NORTHBOUND_NET", "type": "northbound"},
]

# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------
def fetch_price(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Fetch latest price for a stock index."""
    try:
        price = get_price(ticker, date)
        if price is not None:
            return price, f"get_price({ticker}, {date}) -> {price}"
        else:
            return None, f"get_price({ticker}, {date}) returned None"
    except Exception as e:
        return None, f"get_price({ticker}, {date}) raised {e}"

def fetch_yield(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Placeholder for bond yield fetch. In production, replace with real API."""
    # For now, simulate failure to demonstrate error handling
    return None, f"Yield API not implemented for {ticker}"

def fetch_index(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Placeholder for USD index fetch."""
    return None, f"Index API not implemented for {ticker}"

def fetch_forex(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Placeholder for forex fetch."""
    return None, f"Forex API not implemented for {ticker}"

def fetch_turnover(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Placeholder for turnover fetch."""
    return None, f"Turnover API not implemented for {ticker}"

def fetch_northbound(ticker: str, date: str) -> Tuple[Optional[float], str]:
    """Placeholder for northbound flow fetch."""
    return None, f"Northbound API not implemented for {ticker}"

FETCH_MAP = {
    "price": fetch_price,
    "yield": fetch_yield,
    "index": fetch_index,
    "forex": fetch_forex,
    "turnover": fetch_turnover,
    "northbound": fetch_northbound,
}

def fetch_indicator(indicator: IndicatorRecord, date: str) -> IndicatorRecord:
    """Fetch a single indicator and return a record with status."""
    name = indicator["name"]
    ticker = indicator["ticker"]
    fetch_type = indicator["type"]
    fetcher = FETCH_MAP.get(fetch_type)
    if fetcher is None:
        return {
            "name": name,
            "ticker": ticker,
            "success": False,
            "query": f"No fetcher for type {fetch_type}",
            "raw_summary": "",
            "value": None,
        }
    value, raw_summary = fetcher(ticker, date)
    success = value is not None
    return {
        "name": name,
        "ticker": ticker,
        "success": success,
        "query": f"{fetcher.__name__}({ticker}, {date})",
        "raw_summary": raw_summary,
        "value": value,
    }

# ---------------------------------------------------------------------------
# LLM call (OpenAI / DeepSeek)
# ---------------------------------------------------------------------------
def call_llm(prompt: str) -> str:
    """Call DeepSeek (via OpenAI SDK) to generate report text."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Cannot generate report.")
        raise RuntimeError("openai package required")

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY or DEEPSEEK_API_KEY environment variable not set.")
        raise RuntimeError("API key not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的A股市场分析师。请严格按照用户要求生成报告。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        text = response.choices[0].message.content.strip()
        return text
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(date_str: str) -> str:
    """Generate the full report markdown."""
    # 1. Fetch all indicators
    records: List[IndicatorRecord] = []
    for ind in INDICATORS:
        rec = fetch_indicator(ind, date_str)
        records.append(rec)
        logger.info(f"Indicator {rec['name']}: success={rec['success']}, value={rec['value']}")

    # 2. Build raw_text for LLM
    raw_lines = []
    for rec in records:
        if rec["success"]:
            raw_lines.append(f"{rec['name']}: {rec['value']}")
        else:
            raw_lines.append(f"{rec['name']}: 数据缺失")
    raw_text = "\n".join(raw_lines)

    # 3. Build prompt
    prompt = f"""你是一个A股市场分析师。请根据以下真实数据生成一份盘前简报。

当前日期：{date_str}

数据获取状态：
{raw_text}

要求：
- 严禁编造任何数据。
- 只能基于以上 raw_text 中已有数据分析。
- 如果数据不足，必须说明“不足以判断”。
- 不得使用模板化市场判断。
- 禁止生成没有数据支撑的结论。
- 禁止使用占位符如“XX月XX日”。
- 禁止输出 URL 编码乱码（如 %E9%AB%98）。
- 报告结构必须严格按照以下格式：

# A股盘前简报 {date_str}

## 一、数据获取状态
用表格列出每个指标是否成功、提取值、查询语句。

## 二、核心市场判断
只基于成功获取的数据分析。

## 三、风格判断
只能从上证指数、创业板指、中证红利等真实数据推导。

## 四、今日关注方向
如果数据不足，明确写“暂不生成方向判断”。

## 五、数据缺口与风险提示
列出哪些数据缺失，以及会影响哪些判断。

请生成报告。"""

    # 4. Call LLM
    logger.info("Calling LLM to generate report...")
    report_text = call_llm(prompt)

    # 5. Clean URL-encoded sequences
    report_text = urllib.parse.unquote(report_text)

    # 6. Replace any remaining placeholder patterns
    report_text = re.sub(r'\d{4}年\d{2}月\d{2}日', date_str, report_text)
    report_text = re.sub(r'XX月XX日', '', report_text)
    report_text = re.sub(r'2025年XX月XX日', '', report_text)

    return report_text

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------
def quality_check(report_text: str, records: List[IndicatorRecord]) -> Tuple[bool, str]:
    """Return (pass, error_message)."""
    errors = []

    # Check for placeholder dates
    if re.search(r'XX月XX日', report_text):
        errors.append("报告包含占位符 'XX月XX日'")
    if re.search(r'2025年XX月XX日', report_text):
        errors.append("报告包含占位符 '2025年XX月XX日'")
    if re.search(r'%E', report_text):
        errors.append("报告包含 URL 编码残留 '%E'")

    # Count missing data
    missing_count = sum(1 for rec in records if not rec["success"])
    if missing_count > 5:
        errors.append(f"数据缺失数量 {missing_count} 超过 5 个")

    if errors:
        return False, "；".join(errors)
    return True, ""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")

    logger.info(f"Starting daily brief generation for {date_str}")

    # Generate report
    try:
        report_text = generate_report(date_str)
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        error_msg = f"盘前报告生成失败：{e}，请查看日志。"
        push_text(error_msg, open_id=None)
        # Also write error log
        with open(os.path.join(LOG_DIR, "daily_brief_error.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - {error_msg}\n")
        sys.exit(1)

    # Re-fetch records for quality check (they were already fetched inside generate_report)
    # We'll re-fetch to have them available here (or we could return them from generate_report)
    # For simplicity, re-fetch
    records = []
    for ind in INDICATORS:
        rec = fetch_indicator(ind, date_str)
        records.append(rec)

    # Quality check
    passed, error_detail = quality_check(report_text, records)
    if not passed:
        logger.error(f"Quality check failed: {error_detail}")
        error_msg = f"盘前报告生成失败：数据不足或报告质量检查未通过，请查看日志。详情：{error_detail}"
        push_text(error_msg, open_id=None)
        # Write error log
        with open(os.path.join(LOG_DIR, "daily_brief_error.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - {error_msg}\n")
        sys.exit(1)

    # Save report
    report_path = os.path.join(REPORT_DIR, f"daily_brief_{date_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {report_path}")

    # Push to Feishu
    try:
        push_card(report_text, open_id=None)
        logger.info("Report pushed to Feishu successfully.")
    except Exception as e:
        logger.error(f"Feishu push failed: {e}")
        # Not fatal, continue

if __name__ == "__main__":
    main()
