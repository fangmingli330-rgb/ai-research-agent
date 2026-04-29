# AI 投研系统

## 项目用途
本项目是一个基于人工智能的投研系统，自动生成每日/每周市场报告，并模拟组合管理。

## 模块结构
- **daily/** — 每日简报生成
- **weekly/** — 每周报告生成（含投资结论模块）
- **portfolio/** — 模拟组合系统（持仓、交易流水、净值）
- **scripts/** — 核心脚本（报告生成、组合管理、执行模拟、组合复盘）

## 使用方法
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
