# AI 投研系统

自动生成每日/每周市场报告，并模拟组合管理。

## 快速开始

1. 安装依赖：`pip install -r requirements.txt`
2. 配置飞书机器人（在 `scripts/feishu_push.py` 中设置 APP_ID、APP_SECRET、OPEN_ID）
3. 运行每周报告：`python scripts/weekly_report.py`
4. 运行组合管理器：`python scripts/portfolio_manager.py`
5. 运行执行模拟器：`python scripts/execution_simulator.py`
6. 查看组合报告：`python scripts/portfolio_report.py`

可通过 cron 定时执行上述脚本，实现自动化推送。

## 注意事项

- 所有交易信号均遵循 T+1 规则，禁止未来函数。
- 模拟组合不涉及真实资金。
