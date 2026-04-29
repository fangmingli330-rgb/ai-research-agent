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

def generate_report():
    """Generate the weekly report and push it."""
    today = date.today().isoformat()
    report_lines = []

    # Title
    report_lines.append(f"# 周报 - {today}")
    report_lines.append("")

    # Section 1: Market Review (simulated)
    report_lines.append("## 市场回顾")
    report_lines.append("")
    report_lines.append("本周A股市场整体震荡上行，上证指数上涨1.2%，深证成指上涨1.8%。")
    report_lines.append("成交量较上周有所放大，北向资金净流入约150亿元。")
    report_lines.append("市场情绪有所回暖，但板块分化明显。")
    report_lines.append("")

    # Section 2: Sector Performance (simulated)
    report_lines.append("## 板块表现")
    report_lines.append("")
    report_lines.append("| 板块 | 周涨跌幅 | 备注 |")
    report_lines.append("|------|----------|------|")
    report_lines.append("| 科技 | +3.5% | AI概念持续活跃 |")
    report_lines.append("| 消费 | +0.8% | 白酒板块企稳 |")
    report_lines.append("| 医药 | -0.5% | 集采压力仍存 |")
    report_lines.append("| 金融 | +1.0% | 银行股表现稳健 |")
    report_lines.append("| 新能源 | +2.2% | 政策利好推动 |")
    report_lines.append("")

    # Section 3: Macro Data (simulated)
    report_lines.append("## 宏观数据")
    report_lines.append("")
    report_lines.append("- CPI同比上涨0.5%，PPI同比下降2.8%")
    report_lines.append("- 社融数据超预期，新增贷款同比多增")
    report_lines.append("- 央行维持LPR不变，流动性合理充裕")
    report_lines.append("")

    # Section 4: Investment Conclusion Module
    report_lines.append("## 投资结论")
    report_lines.append("")

    # 4.1 Position suggestion
    report_lines.append("### 下周仓位建议")
    report_lines.append("**建议仓位：70%**")
    report_lines.append("理由：当前市场估值处于中等偏低位置，流动性宽松，但外部不确定性仍存，建议保持适度仓位。")
    report_lines.append("")

    # 4.2 Style judgment
    report_lines.append("### 风格判断")
    report_lines.append("**风格：成长**")
    report_lines.append("理由：科技板块持续活跃，政策支持力度大，成长风格有望继续占优。")
    report_lines.append("")

    # 4.3 Top three industries
    report_lines.append("### 最值得关注的三个行业")
    report_lines.append("1. **人工智能**：大模型应用加速落地，算力需求持续增长。")
    report_lines.append("2. **新能源**：政策补贴延续，海外需求回暖。")
    report_lines.append("3. **消费电子**：换机周期来临，折叠屏等新品带动需求。")
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
