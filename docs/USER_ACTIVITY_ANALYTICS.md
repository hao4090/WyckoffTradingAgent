# 用户活跃统计

目标：统计 Web 端和 CLI 端真实用户活跃，输出周度 DAU/WAU/留存和月度 MAU/留存，通过飞书汇报。

## 表

表结构：

| 表 | 用途 |
|----|------|
| `user_activity_events` | 原始活跃事件，Web/CLI 写入 |
| `user_daily_activity` | 每日用户聚合结果，定时任务写入 |
| `analytics_excluded_users` | 排除内部测试账号 |

RLS 策略：

| 表 | 策略 |
|----|------|
| `user_activity_events` | 登录用户只能写入/读取自己的事件 |
| `user_daily_activity` | 登录用户只能读取自己的聚合行 |
| `analytics_excluded_users` | 无普通用户策略，仅 service role 定时任务读取 |

## 采集范围

Web 端采集：

| 事件 | 含义 |
|------|------|
| `page_view` | 页面访问 |
| `chat_send` / `chat_finish` / `chat_error` | Agent 对话开始、完成、失败 |
| `tool_run` | Agent 工具调用类型 |
| `portfolio_diagnosis_*` | 持仓诊断开始、完成、失败 |
| `settings_save` | 设置保存结果 |
| `logout` | 退出登录 |

CLI 端采集：

| 事件 | 含义 |
|------|------|
| `cli_command` | 已登录 CLI 用户执行命令 |

采集不包含 prompt、聊天正文、持仓明细、股票池明细、API Key 或通知 Webhook。CLI 可用 `WYCKOFF_TELEMETRY=0` 关闭采集。

## 定时报告

统计报告 GitHub Action：`.github/workflows/user_activity_analytics.yml`

历史清理 GitHub Action：`.github/workflows/db_maintenance.yml`

| 报告 | 触发时间 | 统计周期 |
|------|----------|----------|
| 周报 | 每周一 09:20 北京时间 | 昨天往前 7 个自然日 |
| 月报 | 每月 1 日 09:30 北京时间 | 上一个自然月 |

历史清理由 `db_maintenance.yml` 统一执行，周一至周五 06:20 北京时间删除过期统计明细。

历史清理规则：

| 表 | 保留周期 |
|----|----------|
| `user_activity_events` | 180 天 |
| `user_daily_activity` | 730 天 |

需要 GitHub Secrets：

| Secret | 用途 |
|--------|------|
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | 定时任务聚合和读全量数据 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook |

手动运行：

```bash
python scripts/analytics_report_job.py --mode weekly --no-feishu
python scripts/analytics_report_job.py --mode monthly --no-feishu
python scripts/db_maintenance.py --dry-run
```
