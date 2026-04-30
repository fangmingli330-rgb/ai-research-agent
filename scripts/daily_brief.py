#!/usr/bin/env python3
"""
Daily Brief Generator – A股盘前简报

Generates a pre‑market briefing report with strict data integrity checks.
"""

import sys
import os
import logging
import datetime
import urllib.parse
import re
import subprocess
import io
import contextlib
from typing import Dict, List, Optional, Any, Tuple

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.feishu_push import push_text, push_card

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = "logs"
REPORT_DIR = "reports/pre_market"
MX_DATA_SCRIPT = "/root/mx-skills/mx-data/mx_data.py"
MX_DATA_TIMEOUT_SECONDS = 90
MAX_MISSING_DATA = 5

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

PRICE_VALUE_RANGES = {
    "000001.SH": (1000.0, 10000.0),
    "399006.SZ": (1000.0, 6000.0),
    "000922.CSI": (1000.0, 20000.0),
}

MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
GENERIC_VALUE_COLUMNS = ("最新价", "最新值", "收盘价", "价格", "点位", "收益率", "汇率", "成交额", "净流入", "数值")
NON_VALUE_COLUMNS = ("代码", "证券代码", "ticker", "Ticker", "名称", "日期", "时间", "查询", "ID", "id")

# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------
def _preview(text: str, limit: int) -> str:
    """Return a single-line log preview without losing the original text."""
    return (text or "").strip().replace("\n", "\\n")[:limit]

def _parse_markdown_tables(text: str) -> List[List[List[str]]]:
    """Parse simple markdown tables into lists of cell rows."""
    tables = []
    current = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            if current:
                tables.append(current)
                current = []
            continue
        if MARKDOWN_TABLE_SEPARATOR_RE.match(stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2:
            current.append(cells)
    if current:
        tables.append(current)
    return tables

def _to_float(value: Any) -> Optional[float]:
    """Convert a structured numeric value or numeric cell text to float."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = NUMBER_RE.search(value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None

def _ticker_variants(ticker: str) -> List[str]:
    variants = [ticker]
    if "." in ticker:
        variants.append(ticker.split(".", 1)[0])
    return [item for item in variants if item]

def _indicator_keyword(indicator: IndicatorRecord) -> str:
    return indicator["name"].replace("最新价", "").strip()

def _row_matches_indicator(row: List[str], header: List[str], indicator: IndicatorRecord) -> bool:
    row_text = " ".join(row)
    if any(variant in row_text for variant in _ticker_variants(indicator["ticker"])):
        return True
    keyword = _indicator_keyword(indicator)
    if keyword and keyword in row_text:
        return True
    code_idx = next(
        (idx for idx, cell in enumerate(header) if any(key in cell for key in ("代码", "证券代码", "ticker", "Ticker"))),
        None,
    )
    if code_idx is not None and code_idx < len(row):
        return any(variant in row[code_idx] for variant in _ticker_variants(indicator["ticker"]))
    return False

def _matching_rows(rows: List[List[str]], header: List[str], indicator: IndicatorRecord) -> List[List[str]]:
    data_rows = rows[1:]
    matched = [row for row in data_rows if _row_matches_indicator(row, header, indicator)]
    if matched:
        return matched
    if len(data_rows) == 1:
        return data_rows
    return []

def _latest_price_sanity_failure(value: float, ticker: str) -> Optional[str]:
    value_range = PRICE_VALUE_RANGES.get(ticker)
    if value_range is None:
        return None
    lower, upper = value_range
    if value < lower:
        return f"parsed value failed sanity check: {value} < {lower}"
    if value > upper:
        return f"parsed value failed sanity check: {value} > {upper}"
    return None

def _extract_latest_price_from_markdown(text: str, indicator: IndicatorRecord) -> Tuple[Optional[float], str]:
    """Extract the value under the markdown table column named 最新价."""
    candidates = []
    saw_latest_column = False
    for rows in _parse_markdown_tables(text):
        if len(rows) < 2:
            continue
        header = rows[0]
        latest_idx = next((idx for idx, cell in enumerate(header) if "最新价" in cell), None)
        if latest_idx is None:
            continue
        saw_latest_column = True
        for row in _matching_rows(rows, header, indicator):
            if latest_idx >= len(row):
                continue
            value = _to_float(row[latest_idx])
            if value is not None:
                candidates.append(value)

    if not candidates:
        if saw_latest_column:
            return None, "markdown table has 最新价 column but no matching numeric row"
        return None, "markdown table does not contain 最新价 column"

    sanity_failures = []
    for value in candidates:
        failure = _latest_price_sanity_failure(value, indicator["ticker"])
        if failure is None:
            return value, "extracted from markdown table column 最新价"
        sanity_failures.append(failure)
    return None, "；".join(sanity_failures)

def _extract_generic_value_from_markdown(text: str, indicator: IndicatorRecord) -> Tuple[Optional[float], str]:
    """Extract non-price values from semantic markdown table columns only."""
    for rows in _parse_markdown_tables(text):
        if len(rows) < 2:
            continue
        header = rows[0]
        preferred_indexes = [
            idx for idx, cell in enumerate(header)
            if any(key in cell for key in GENERIC_VALUE_COLUMNS)
            and not any(key in cell for key in NON_VALUE_COLUMNS)
        ]
        if not preferred_indexes:
            continue
        for row in _matching_rows(rows, header, indicator):
            for idx in preferred_indexes:
                if idx >= len(row):
                    continue
                value = _to_float(row[idx])
                if value is not None:
                    return value, f"extracted from markdown table column {header[idx]}"
    return None, "unable to extract value from semantic markdown table columns"

def extract_indicator_value(indicator: IndicatorRecord, stdout: str) -> Tuple[Optional[float], str]:
    """Extract an indicator value without using arbitrary free-text numbers."""
    if "最新价" in indicator["name"]:
        return _extract_latest_price_from_markdown(stdout, indicator)
    return _extract_generic_value_from_markdown(stdout, indicator)

def run_mx_data_query(query: str) -> Dict[str, Any]:
    """Run the cloud mx_data command and capture its output."""
    try:
        result = subprocess.run(
            [sys.executable, MX_DATA_SCRIPT, query],
            capture_output=True,
            text=True,
            timeout=MX_DATA_TIMEOUT_SECONDS
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "failure_reason": "" if result.returncode == 0 else f"mx_data returned non-zero exit code {result.returncode}",
        }
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return {
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "failure_reason": f"mx_data timed out after {MX_DATA_TIMEOUT_SECONDS} seconds",
        }
    except Exception as e:
        return {
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "failure_reason": f"mx_data subprocess failed: {e}",
        }

def fetch_indicator(indicator: IndicatorRecord, date: str) -> IndicatorRecord:
    """Fetch a single indicator from mx_data.py and return a record with status."""
    query = indicator.get("query") or indicator["name"]
    result = run_mx_data_query(query)
    stdout = result["stdout"]
    stderr = result["stderr"]
    extracted_value, extraction_reason = extract_indicator_value(indicator, stdout)
    failure_reason = result["failure_reason"]
    if result["returncode"] == 0 and extracted_value is None:
        failure_reason = extraction_reason
    success = result["returncode"] == 0 and extracted_value is not None
    raw_summary = stdout.strip() or stderr.strip() or failure_reason

    logger.info(f"mx_data query={query!r} returncode={result['returncode']}")
    logger.info(f"mx_data query={query!r} stderr_preview={_preview(stderr, 500)!r}")
    logger.info(f"mx_data query={query!r} stdout_preview={_preview(stdout, 1000)!r}")
    logger.info(f"mx_data query={query!r} extracted_value={extracted_value}")
    logger.info(f"mx_data query={query!r} success={success}")
    logger.info(f"mx_data query={query!r} failure_reason={failure_reason!r}")
    if failure_reason:
        logger.warning(f"mx_data query={query!r} failure_reason={failure_reason}")

    return {
        "name": indicator["name"],
        "ticker": indicator["ticker"],
        "query": query,
        "success": success,
        "raw_summary": raw_summary,
        "extracted_value": extracted_value,
        "value": extracted_value,
        "returncode": result["returncode"],
        "stderr_preview": _preview(stderr, 500),
        "stdout_preview": _preview(stdout, 1000),
        "failure_reason": "" if success else failure_reason,
        "extraction_reason": extraction_reason,
    }

def fetch_all_indicators(date: str) -> List[IndicatorRecord]:
    """Fetch all indicators once for report generation and quality checks."""
    records = []
    for ind in INDICATORS:
        rec = fetch_indicator(ind, date)
        records.append(rec)
        logger.info(
            "Indicator %s: success=%s, extracted_value=%s",
            rec["name"],
            rec["success"],
            rec["extracted_value"],
        )
    return records

def missing_data_error(records: List[IndicatorRecord]) -> str:
    missing_count = sum(1 for rec in records if not rec["success"])
    if missing_count > MAX_MISSING_DATA:
        return f"数据缺失数量 {missing_count} 超过 {MAX_MISSING_DATA} 个"
    return ""

def push_failure_alert(error_msg: str) -> None:
    """Push a failure alert and copy push_text console output into the logger."""
    output_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_buffer):
            push_text(error_msg, open_id=None)
    except Exception as e:
        logger.error(f"Feishu failure alert raised exception: {e}")
        return

    output = output_buffer.getvalue().strip()
    if output:
        logger.info(f"Feishu failure alert output: {_preview(output, 1000)}")
    if "failed" in output.lower() or "All Feishu push attempts failed" in output:
        logger.error(f"Feishu failure alert may have failed: {_preview(output, 1000)}")

def write_error_log(error_msg: str) -> None:
    with open(os.path.join(LOG_DIR, "daily_brief_error.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {error_msg}\n")

def fail_with_alert(error_msg: str) -> None:
    logger.error(error_msg)
    push_failure_alert(error_msg)
    write_error_log(error_msg)
    sys.exit(1)

def build_raw_text(records: List[IndicatorRecord]) -> str:
    raw_lines = []
    for rec in records:
        if rec["success"]:
            raw_lines.append(
                f"{rec['name']}: {rec['extracted_value']} | query: {rec['query']} | 原始摘要: {rec['raw_summary']}"
            )
        else:
            raw_lines.append(
                f"{rec['name']}: 数据缺失 | query: {rec['query']} | failure_reason: {rec['failure_reason']} | 原始摘要: {rec['raw_summary']}"
            )
    return "\n".join(raw_lines)

# ---------------------------------------------------------------------------
# LLM call (OpenAI-compatible)
# ---------------------------------------------------------------------------
def call_llm(prompt: str) -> str:
    """Call DeepSeek through the OpenAI SDK client API to generate report text."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Cannot generate report.")
        raise RuntimeError("openai package required")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY or DEEPSEEK_API_KEY environment variable not set.")
        raise RuntimeError("OPENAI_API_KEY or DEEPSEEK_API_KEY not set")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        return content.strip()
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(date_str: str, records: List[IndicatorRecord]) -> str:
    """Generate the full report markdown from already-fetched records."""
    raw_text = build_raw_text(records)

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
用表格列出每个指标是否成功、提取值、查询语句、原始返回摘要。

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
def quality_check(report_text: str, records: List[IndicatorRecord], date_str: str) -> Tuple[bool, str]:
    """Return (pass, error_message)."""
    errors = []
    expected_title = f"# A股盘前简报 {date_str}"
    first_line = report_text.strip().splitlines()[0] if report_text.strip() else ""
    if first_line != expected_title:
        errors.append(f"报告标题不是 '{expected_title}'")

    # Check for placeholder dates
    if re.search(r'XX月XX日', report_text):
        errors.append("报告包含占位符 'XX月XX日'")
    if re.search(r'2025年XX月XX日', report_text):
        errors.append("报告包含占位符 '2025年XX月XX日'")
    if re.search(r'%E', report_text):
        errors.append("报告包含 URL 编码残留 '%E'")

    # Count missing data
    missing_error = missing_data_error(records)
    if missing_error:
        errors.append(missing_error)

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

    records = fetch_all_indicators(date_str)
    missing_error = missing_data_error(records)
    if missing_error:
        fail_with_alert(f"盘前报告生成失败：数据不足，不推送正式报告。详情：{missing_error}")

    try:
        report_text = generate_report(date_str, records)
    except Exception as e:
        fail_with_alert(f"盘前报告生成失败：{e}，请查看日志。")

    # Quality check
    passed, error_detail = quality_check(report_text, records, date_str)
    if not passed:
        fail_with_alert(f"盘前报告生成失败：数据不足或报告质量检查未通过，请查看日志。详情：{error_detail}")

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
