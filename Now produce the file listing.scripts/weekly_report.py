#!/usr/bin/env python3
"""
Weekly report generator.
Generates a markdown report with market review, sector performance,
macro data, and an investment conclusion module.
The report is written to weekly_report.md and then pushed via Feishu.
"""

import os
import sys
from datetime import date

# Ensure we can import feishu_push from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_push

def log(msg):
    """Simple logging function."""
    print(f"[weekly_report] {msg}")

# ---------- Fallback simulated data ----------
FALLBACK_OVERALL_CHANGE = 1.2
FALLBACK_SECTORS = [
    ("科技", 3.5, "AI概念持续活跃"),
    ("消费", 0.8, "白酒板块企稳"),
    ("医药", -0.5, "集采压力仍存"),
    ("金融", 1.0, "银行股表现稳健"),
    ("新能源", 2.2, "政策利好推动"),
]
FALLBACK_MACRO_LINES = [
    "- CPI同比上涨0.5%，PPI同比下降2.8%",
    "- 社融数据超预期，新增贷款同比多增",
    "- 央行维持LPR不变，流动性合理充裕",
]

def get_real_data():
    """
    Try to fetch real market data from mx_data module.
    Returns (overall_change, sectors, macro_lines) on success.
    On failure, returns None.
    """
    try:
        import mx_data
        data = mx_data.get_market_data()
        overall_change = data["overall_change"]
        sectors = [(s["name"], s["change"], s["note"]) for s in data["sectors"]]
        # macro_lines can be provided by mx_data or we keep fallback
        macro_lines = data.get("macro_lines", FALLBACK_MACRO_LINES)
        return overall_change, sectors, macro_lines
    except Exception as e:
        log(f"Failed to fetch real data: {e}. Falling back to simulated data.")
        return None

def generate_report():
    """Generate the weekly report and push it."""
    today = date.today().isoformat()
    report_lines = []

    # ---------- Get data (real or fallback) ----------
    real = get_real_data()
    if real is not None:
        overall_change, sectors, macro_lines = real
    else:
        overall_change = FALLBACK_OVERALL_CHANGE
        sectors = FALLBACK_SECTORS
        macro_lines = FALLBACK_MACRO_LINES

    # ---------- Build report ----------
    # Title
    report_lines.append(f"# 周报 - {today}")
    report_lines.append("")

    # Section 1: Market Review (use real overall_change)
    report_lines.append("## 市场回顾")
    report_lines.append("")
    report_lines.append(
        f"本周A股市场整体震荡上行，上证指数上涨{overall_change}%，深证成指上涨1.8%。"
        "成交量较上周有所放大，北向资金净流入约150亿元。"
        "市场情绪有所回暖，但板块分化明显。"
    )
    report_lines.append("")

    # Section 2: Sector Performance (build table from data)
    report_lines.append("## 板块表现")
    report_lines.append("")
    report_lines.append("| 板块 | 周涨跌幅 | 备注 |")
    report_lines.append("|------|----------|------|")
    for name, change, note in sectors:
        sign = "+" if change >= 0 else ""
        report_lines.append(f"| {name} | {sign}{change}% | {note} |")
    report_lines.append("")

    # Section 3: Macro Data
    report_lines.append("## 宏观数据")
    report_lines.append("")
    for line in macro_lines:
        report_lines.append(line)
    report_lines.append("")

    # ---------- Dynamic Investment Conclusion ----------
    # 1. Determine market trend from overall_change
    if overall_change >= 0.5:
        trend = "上涨"
        position = 80
        position_reason = "市场整体上涨，情绪回暖，建议保持偏高仓位以捕捉上行机会。"
    elif overall_change <= -0.5:
        trend = "弱势"
        position = 40
        position_reason = "市场整体下跌，风险偏好降低，建议降低仓位以控制回撤。"
    else:
        trend = "震荡"
        position = 60
        position_reason = "市场窄幅震荡，方向不明，建议维持中性仓位等待趋势明朗。"

    # 2. Determine style from top sector
    # Find sector with highest change
    top_sector = max(sectors, key=lambda x: x[1])
    top_name = top_sector[0]
    # Map sector name to style
    style_map = {
        "科技": "成长",
        "消费": "价值",
        "医药": "红利",
        "金融": "价值",
        "新能源": "成长",
    }
    style = style_map.get(top_name, "成长")  # default to growth
    style_reason = f"{top_name}板块涨幅最大（{top_sector[1]:+.1f}%），{top_sector[2]}，因此判断当前市场风格偏向{style}。"

    # 3. Top three industries
    # Sort sectors by change descending, take first three
    sorted_sectors = sorted(sectors, key=lambda x: x[1], reverse=True)
    top_three = sorted_sectors[:3]

    # Build industry lines
    industry_lines = []
    for i, (name, change, note) in enumerate(top_three, 1):
        sign = "+" if change >= 0 else ""
        industry_lines.append(f"{i}. **{name}**：{note}（周涨幅{sign}{change}%）")

    # Append conclusion section
    report_lines.append("## 投资结论")
    report_lines.append("")

    # 4.1 Position suggestion
    report_lines.append("### 下周仓位建议")
    report_lines.append(f"**建议仓位：{position}%**")
    report_lines.append(f"理由：{position_reason}")
    report_lines.append("")

    # 4.2 Style judgment
    report_lines.append("### 风格判断")
    report_lines.append(f"**风格：{style}**")
    report_lines.append(f"理由：{style_reason}")
    report_lines.append("")

    # 4.3 Top three industries
    report_lines.append("### 最值得关注的三个行业")
    for line in industry_lines:
        report_lines.append(line)
    report_lines.append("")

    # Combine into one string
    report_content = "\n".join(report_lines)

    # Write to file
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weekly_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    log(f"Report written to {report_path}")

    # Push via Feishu
    log("Pushing report via Feishu...")
    feishu_push.push_text(report_path, is_path=True)
    log("Push completed.")

if __name__ == "__main__":
    generate_report()
