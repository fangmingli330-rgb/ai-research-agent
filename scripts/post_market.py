#!/usr/bin/env python3
"""
Strict data-driven A-share post-market report generator.
"""

import contextlib
import datetime
import io
import logging
import os
import re
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in path when executed as python scripts/post_market.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.feishu_push import push_card, push_text

LOG_DIR = "logs"
REPORT_DIR = "reports/post_market"
MX_DATA_SCRIPT = "/root/mx-skills/mx-data/mx_data.py"
MX_DATA_TIMEOUT_SECONDS = 90
MAX_MISSING_DATA = 5

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

logger = logging.getLogger("post_market")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = logging.FileHandler(os.path.join(LOG_DIR, "post_market.log"), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    efh = logging.FileHandler(os.path.join(LOG_DIR, "post_market_error.log"), encoding="utf-8")
    efh.setLevel(logging.ERROR)
    efh.setFormatter(formatter)
    logger.addHandler(efh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

IndicatorRecord = Dict[str, Any]

INDICATORS: List[IndicatorRecord] = [
    {"name": "上证指数 最新价", "ticker": "000001.SH", "type": "price"},
    {"name": "深证成指 最新价", "ticker": "399001.SZ", "type": "price"},
    {"name": "创业板指 最新价", "ticker": "399006.SZ", "type": "price"},
    {"name": "科创50 最新价", "ticker": "000688.SH", "type": "price"},
    {"name": "沪深300 最新价", "ticker": "000300.SH", "type": "price"},
    {"name": "中证红利 最新价", "ticker": "000922.CSI", "type": "price"},
    {"name": "两市成交额 A股", "ticker": "TOTAL_SH_SZ_TURNOVER", "type": "turnover"},
    {"name": "北向资金 净流入", "ticker": "NORTHBOUND_NET", "type": "northbound"},
]

INDEX_VALUE_RANGES = {
    "000001.SH": (1000.0, 10000.0),
    "399001.SZ": (5000.0, 20000.0),
    "399006.SZ": (1000.0, 6000.0),
    "000688.SH": (300.0, 3000.0),
    "000300.SH": (1000.0, 10000.0),
    "000922.CSI": (1000.0, 20000.0),
}

MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
GENERIC_VALUE_COLUMNS = ("最新值", "最新价", "收盘价", "价格", "点位", "成交额", "净流入", "净买入", "金额", "数值")
NON_VALUE_COLUMNS = ("代码", "证券代码", "ticker", "Ticker", "名称", "日期", "时间", "date", "Date", "查询", "ID", "id")
TEMPLATE_OLD_VALUES = ("3,215.62", "3215.62", "9,920.63", "9920.63", "1,931.06", "1931.06", "9,056亿", "9056亿", "+48.2亿")


def _preview(text: str, limit: int) -> str:
    return (text or "").strip().replace("\n", "\\n")[:limit]


def _parse_markdown_tables(text: str) -> List[List[List[str]]]:
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


def _header_has_identifier(header: List[str]) -> bool:
    return any(any(key in cell for key in ("代码", "证券代码", "ticker", "Ticker", "名称")) for cell in header)


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
    if not _header_has_identifier(header) and data_rows:
        return data_rows[:1]
    if len(data_rows) == 1:
        return data_rows
    return []


def _index_sanity_failure(value: float, ticker: str) -> Optional[str]:
    value_range = INDEX_VALUE_RANGES.get(ticker)
    if value_range is None:
        return None
    lower, upper = value_range
    if value < lower:
        return f"parsed value failed sanity check: {value} < {lower}"
    if value > upper:
        return f"parsed value failed sanity check: {value} > {upper}"
    return None


def _extract_latest_price_from_markdown(text: str, indicator: IndicatorRecord) -> Tuple[Optional[float], str]:
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
        failure = _index_sanity_failure(value, indicator["ticker"])
        if failure is None:
            return value, "extracted from markdown table column 最新价"
        sanity_failures.append(failure)
    return None, "；".join(sanity_failures)


def _extract_generic_value_from_markdown(text: str, indicator: IndicatorRecord) -> Tuple[Optional[float], str]:
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
    if "最新价" in indicator["name"]:
        return _extract_latest_price_from_markdown(stdout, indicator)
    return _extract_generic_value_from_markdown(stdout, indicator)


def run_mx_data_query(query: str) -> Dict[str, Any]:
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


def fetch_indicator(indicator: IndicatorRecord) -> IndicatorRecord:
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
        "type": indicator["type"],
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


def fetch_all_indicators() -> List[IndicatorRecord]:
    return [fetch_indicator(indicator) for indicator in INDICATORS]


def missing_data_error(records: List[IndicatorRecord]) -> str:
    missing_count = sum(1 for rec in records if not rec["success"])
    if missing_count > MAX_MISSING_DATA:
        return f"数据缺失数量 {missing_count} 超过 {MAX_MISSING_DATA} 个"
    return ""


def build_data_status_table(records: List[IndicatorRecord]) -> str:
    lines = ["| 指标名称 | 是否成功 | 提取值 | 查询语句 |", "| --- | --- | --- | --- |"]
    for rec in records:
        value = rec["extracted_value"] if rec["success"] else "数据缺失"
        lines.append(f"| {rec['name']} | {'成功' if rec['success'] else '失败'} | {value} | {rec['query']} |")
    return "\n".join(lines)


def build_raw_text(records: List[IndicatorRecord]) -> str:
    lines = []
    for rec in records:
        if rec["success"]:
            lines.append(
                f"{rec['name']}: {rec['extracted_value']} | query: {rec['query']} | 原始摘要: {rec['raw_summary']}"
            )
        else:
            lines.append(
                f"{rec['name']}: 数据缺失 | query: {rec['query']} | failure_reason: {rec['failure_reason']} | 原始摘要: {rec['raw_summary']}"
            )
    return "\n".join(lines)


def has_success(records: List[IndicatorRecord], name_contains: str) -> bool:
    return any(name_contains in rec["name"] and rec["success"] for rec in records)


def call_llm(prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed. Cannot generate report.")
        raise RuntimeError("openai package required")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY or DEEPSEEK_API_KEY environment variable not set.")
        raise RuntimeError("OPENAI_API_KEY or DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            return content.strip()
        except Exception as e:
            last_error = e
            logger.error(f"LLM API call attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM API call failed: {last_error}")


def _looks_like_llm_title(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("# "):
        return True
    return bool(re.match(r"^A股盘后总结\s+\d{4}-\d{2}-\d{2}$", stripped))


def enforce_report_title(report_text: str, date_str: str) -> str:
    expected_title = f"# A股盘后总结 {date_str}"
    body = report_text.strip()
    body = re.sub(r"^```(?:markdown|md)?\s*\n", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\n```\s*$", "", body)

    lines = body.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and _looks_like_llm_title(lines[0]):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)

    body = "\n".join(lines).rstrip()
    if body:
        return f"{expected_title}\n\n{body}\n"
    return f"{expected_title}\n"


def generate_report(date_str: str, records: List[IndicatorRecord]) -> str:
    data_status = build_data_status_table(records)
    raw_text = build_raw_text(records)
    prompt = f"""你是一个A股策略分析师。请根据真实数据生成盘后总结正文。

当前日期：{date_str}

data_status：
{data_status}

raw_text：
{raw_text}

硬性要求：
- 严禁编造任何数据。
- 只能基于 raw_text 和 data_status 表中的成功数据分析。
- 如果数据不足，必须写“不足以判断”。
- 不得生成模板化市场判断。
- 不得写“北向资金净买入”“成交额”“上涨家数”这类没有成功获取的数据。
- 不得自行补充行业涨跌、板块领涨领跌、资金流向细节，除非 raw_text 里确实有。
- 不要输出一级标题，程序会自动添加唯一标题。
- 正文结构必须严格按照以下格式：

## 一、数据获取状态
用表格列出每个指标是否成功、提取值、查询语句。

## 二、市场整体表现
只基于成功获取的指数数据分析。

## 三、资金与成交
只基于成功获取的成交额、北向资金等数据分析；如果缺失，明确写“数据缺失，暂不判断”。

## 四、市场结构
如果没有行业/板块真实数据，不允许编造领涨领跌方向，必须写“行业结构数据不足，暂不判断”。

## 五、明日观察
只基于已成功获取的数据提出观察点；数据不足时写“不足以形成明确预判”。

## 六、数据缺口与风险提示
列出缺失数据及其影响。

请生成报告正文。"""

    logger.info("Calling LLM to generate post-market report...")
    report_text = call_llm(prompt)
    report_text = urllib.parse.unquote(report_text)
    report_text = re.sub(r"\d{4}年\d{2}月\d{2}日", date_str, report_text)
    report_text = re.sub(r"XX月XX日", "", report_text)
    report_text = re.sub(r"2025年XX月XX日", "", report_text)
    return enforce_report_title(report_text, date_str)


def _analysis_sections(report_text: str) -> str:
    sections = re.split(r"^##\s+", report_text, flags=re.MULTILINE)
    kept = []
    for section in sections:
        if section.startswith("一、数据获取状态") or section.startswith("六、数据缺口与风险提示"):
            continue
        kept.append(section)
    return "\n".join(kept)


def _value_backed_by_successful_record(value_text: str, records: List[IndicatorRecord]) -> bool:
    normalized = value_text.replace(",", "").replace("+", "").replace("亿", "")
    value = _to_float(normalized)
    if value is None:
        return False
    for rec in records:
        if rec["success"] and rec["extracted_value"] is not None and abs(rec["extracted_value"] - value) < 0.01:
            return True
    return False


def quality_check(report_text: str, records: List[IndicatorRecord], date_str: str) -> Tuple[bool, str]:
    errors = []
    expected_title = f"# A股盘后总结 {date_str}"
    first_line = report_text.splitlines()[0] if report_text else ""
    if first_line != expected_title:
        errors.append(f"报告标题不是 '{expected_title}'")

    if re.search(r"2025年XX月XX日", report_text):
        errors.append("报告包含占位符 '2025年XX月XX日'")
    if re.search(r"XX月XX日", report_text):
        errors.append("报告包含占位符 'XX月XX日'")
    if re.search(r"%E", report_text):
        errors.append("报告包含 URL 编码残留 '%E'")

    missing_error = missing_data_error(records)
    if missing_error:
        errors.append(missing_error)

    for old_value in TEMPLATE_OLD_VALUES:
        if old_value in report_text and not _value_backed_by_successful_record(old_value, records):
            errors.append(f"报告包含未由本次数据支持的疑似模板旧数据 '{old_value}'")

    analysis_text = _analysis_sections(report_text)
    if "北向资金净买入" in analysis_text and not has_success(records, "北向资金"):
        errors.append("报告在北向资金缺失时提到 '北向资金净买入'")
    if "两市成交额" in analysis_text and not has_success(records, "两市成交额"):
        errors.append("报告在成交额缺失时提到 '两市成交额'")
    if "上涨家数" in analysis_text:
        errors.append("报告提到未获取的 '上涨家数'")
    if "领涨方向" in analysis_text:
        errors.append("报告提到未获取的 '领涨方向'")
    if "领跌方向" in analysis_text:
        errors.append("报告提到未获取的 '领跌方向'")

    if errors:
        return False, "；".join(errors)
    return True, ""


def push_failure_alert(error_msg: str) -> None:
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
    with open(os.path.join(LOG_DIR, "post_market_error.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {error_msg}\n")


def fail_with_alert(detail: str) -> None:
    logger.error(detail)
    write_error_log(detail)
    push_failure_alert("盘后总结生成失败：数据不足或报告质量检查未通过，请查看日志。")
    sys.exit(1)


def main() -> None:
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    report_path = os.path.join(REPORT_DIR, f"post_market_{date_str}.md")
    logger.info(f"Starting post-market report generation for {date_str}")

    records = fetch_all_indicators()
    missing_error = missing_data_error(records)
    if missing_error:
        fail_with_alert(f"盘后总结生成失败：{missing_error}")

    try:
        report_text = generate_report(date_str, records)
    except Exception as e:
        fail_with_alert(f"盘后总结生成失败：{e}")

    passed, error_detail = quality_check(report_text, records, date_str)
    if not passed:
        fail_with_alert(f"盘后总结生成失败：数据不足或报告质量检查未通过。详情：{error_detail}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Post-market report saved to {report_path}")

    try:
        push_card(report_text, open_id=None)
        logger.info("Post-market report pushed to Feishu successfully.")
    except Exception as e:
        logger.error(f"Feishu push failed: {e}")


if __name__ == "__main__":
    main()
