# 密钥与本地配置安全

本文记录 Wyckoff-Analysis 的密钥放置原则。当前主分支不维护 Streamlit，配置入口集中在 CLI、React Web、MCP 和 GitHub Actions。

## 放置位置

| 场景 | 建议位置 | 说明 |
|------|----------|------|
| CLI / TUI 本地模型配置 | `~/.wyckoff/wyckoff.json` | 通过 `/model add` 或 `wyckoff model add` 写入，避免提交到仓库 |
| Web 用户配置 | Supabase `user_settings` | 受 RLS 保护，按 `user_id` 隔离 |
| GitHub Actions 定时任务 | GitHub Secrets / Variables | API Key 放 Secrets，非敏感开关可放 Variables |
| 本地开发临时变量 | `.env` | 不提交；只用于本机调试 |

## 基本规则

- 不把 API Key、Webhook、access token、refresh token 写入 README、日志、截图或提交记录。
- GitHub Actions 里只通过 `${{ secrets.NAME }}` 注入敏感变量。
- Web 前端只使用公开 anon key；service role key 只允许在服务端任务或可信 Worker/Actions 环境使用。
- 用户级配置必须带 `user_id` 并依赖 RLS 隔离，不能用共享行存多用户密钥。
- 调试输出需要脱敏，只保留前后少量字符或直接输出是否已配置。

## 常用变量

| 变量 | 用途 | 敏感 |
|------|------|------|
| `SUPABASE_URL` | Supabase 项目地址 | 否 |
| `SUPABASE_KEY` / `SUPABASE_ANON_KEY` | Web/用户态访问 | 低 |
| `SUPABASE_SERVICE_ROLE_KEY` | 管理态绕过 RLS | 是 |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `EFFICIENCY_API_KEY` | 模型调用 | 是 |
| `TICKFLOW_API_KEY` / `TUSHARE_TOKEN` | 行情数据源 | 是 |
| `FEISHU_WEBHOOK_URL` / `TG_BOT_TOKEN` / `TG_CHAT_ID` | 通知推送 | 是 |

## 相关文档

- [架构文档](ARCHITECTURE.md)
- [成本模型](COST_MODEL.md)
- [信号反馈闭环](SIGNAL_FEEDBACK_LOOP.md)
