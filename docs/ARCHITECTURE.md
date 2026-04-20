# 系统架构

[← 返回 README](../README.md)

## 系统全景

```
                    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                    │  Streamlit   │  │  CLI         │  │  GitHub      │
                    │  Web UI      │  │  Terminal    │  │  Actions     │
                    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                           │                 │                 │
                           ▼                 ▼                 ▼
                    ┌─────────────────────────────────────────────────┐
                    │              Agent Brain                        │
                    │  Web: Google ADK  ·  CLI: 裸写 Agent 循环       │
                    │                                                 │
                    │  10 FunctionTools — LLM 自主编排                 │
                    └────────────────────┬────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
             │ Core Engine │    │ LLM x8       │    │ Cloud Store  │
             │             │    │              │    │              │
             │ Funnel      │    │ Gemini  ★    │    │ Supabase     │
             │ Diagnostic  │    │ OpenAI       │    │  Portfolio   │
             │ Strategy    │    │ DeepSeek     │    │  Settings    │
             │ Signal      │    │ Qwen/Kimi    │    │  Hist Cache  │
             │ Sector      │    │ 智谱/火山    │    │  Recommend   │
             └──────┬──────┘    │ Minimax      │    └──────────────┘
                    │           └──────────────┘
                    ▼
             ┌─────────────┐         ┌──────────────────────┐
             │ Data Sources│         │ Notifications        │
             │             │         │                      │
             │ tushare  ★  │         │ 飞书 · 企微 · 钉钉   │
             │ akshare     │         │ Telegram             │
             │ baostock    │         └──────────────────────┘
             │ efinance    │
             └─────────────┘
```

## 目录结构

```
.
├── cli/                        # 终端 CLI Agent
│   ├── __main__.py             # 入口：wyckoff 命令
│   ├── agent.py                # Agent 循环（think → tool → execute）
│   ├── auth.py                 # Supabase 认证 + session 持久化
│   ├── tools.py                # 工具注册表（复用 chat_tools.py）
│   ├── ui.py                   # TUI（rich + prompt_toolkit）
│   └── providers/              # LLM 适配层
│       ├── base.py             # LLMProvider 抽象接口
│       ├── gemini.py           # google-genai SDK
│       ├── claude.py           # anthropic SDK
│       └── openai.py           # openai SDK（支持兼容端点）
│
├── agents/                     # Web 端 Agent（Google ADK）
│   ├── wyckoff_chat_agent.py   # ADK LlmAgent 定义
│   ├── chat_tools.py           # 10 个 FunctionTool 实现
│   └── session_manager.py      # 会话管理
│
├── core/                       # 核心策略与领域逻辑
│   ├── wyckoff_engine.py       # 五层漏斗引擎（~60 可调参数）
│   ├── holding_diagnostic.py   # 持仓诊断
│   ├── signal_confirmation.py  # 信号确认状态机
│   ├── sector_rotation.py      # 板块轮动
│   ├── prompts.py              # 全部 LLM 提示词
│   ├── stock_cache.py          # 行情缓存
│   ├── constants.py            # 常量
│   ├── funnel_pipeline.py      # 漏斗编排（re-export）
│   ├── batch_report.py         # 研报（re-export）
│   └── strategy.py             # 策略（re-export）
│
├── integrations/               # 外部集成
│   ├── data_source.py          # 数据源（tushare→akshare→baostock→efinance）
│   ├── llm_client.py           # LLM 客户端（8 厂商直连）
│   ├── stock_hist_repository.py# 缓存 + gap-fill
│   ├── supabase_base.py        # Supabase 客户端工厂
│   ├── supabase_client.py      # Web 端 Supabase（用户 session 绑定）
│   ├── supabase_portfolio.py   # 持仓读写
│   ├── supabase_recommendation.py # 推荐跟踪
│   ├── rag_veto.py             # RAG 防雷（负面舆情过滤）
│   └── github_actions.py       # GitHub Actions 触发与结果查询
│
├── tools/                      # 可复用工具函数
│   ├── data_fetcher.py         # 数据拉取辅助
│   ├── report_builder.py       # 研报拼装
│   ├── market_regime.py        # 市场环境判断
│   ├── candidate_ranker.py     # 候选排序
│   └── funnel_config.py        # 漏斗配置
│
├── scripts/                    # 定时 / 批处理任务
│   ├── daily_job.py            # 主编排：Step2→3→4
│   ├── wyckoff_funnel.py       # 全市场漏斗
│   ├── step3_batch_report.py   # AI 研报生成
│   ├── step4_rebalancer.py     # 私人决断 + OMS
│   ├── premarket_risk_job.py   # 盘前风控
│   ├── review_list_replay.py   # 涨停复盘
│   ├── backtest_runner.py      # 日线回测
│   ├── diagnose_holdings.py    # 持仓诊断脚本
│   └── stock_hist_cache_maintenance.py # 缓存维护
│
├── app/                        # Streamlit 组件
│   ├── auth_component.py       # 认证组件
│   ├── layout.py               # 页面布局
│   ├── navigation.py           # 导航
│   └── background_jobs.py      # 后台任务状态
│
├── pages/                      # Streamlit 页面
│   ├── WyckoffScreeners.py     # 漏斗筛选
│   ├── AIAnalysis.py           # AI 分析
│   ├── Portfolio.py            # 持仓管理
│   ├── RecommendationTracking.py # 推荐跟踪
│   ├── Export.py               # 数据导出
│   ├── CustomExport.py         # 自定义导出
│   ├── Settings.py             # 设置
│   └── Changelog.py            # 更新日志
│
├── streamlit_app.py            # Web 入口
├── pyproject.toml              # 包定义
└── requirements.txt            # 依赖
```

## Agent 架构

### 双通道复用

Web 和 CLI 共享同一套工具函数（`agents/chat_tools.py`），通过不同的 Agent 运行时驱动：

- **Web**：Google ADK `LlmAgent`，原生工具绑定
- **CLI**：裸写 Agent 循环（`cli/agent.py`），`think → tool_call → execute → think`

### 决策流

```
用户："帮我看看 000001 和 600519 哪个更值得买"
  │
  ▼
Agent 理解意图 → "对比两只股票"
  │
  ├─→ diagnose_stock("000001") → 吸筹末期
  ├─→ diagnose_stock("600519") → Markup 中段
  ├─→ get_stock_price("000001") → 近期量价
  ├─→ get_stock_price("600519") → 近期量价
  │
  ▼
综合推理 → 对比结构、量价、风险收益比
  │
  ▼
输出结论："000001 处于 Spring 确认阶段，胜率更高..."
```

工具调用顺序和次数由 LLM 实时决策，无需预编排。

### CLI Provider 架构

```
LLMProvider (abstract)
  ├── GeminiProvider   — google-genai SDK
  ├── ClaudeProvider   — anthropic SDK
  └── OpenAIProvider   — openai SDK（支持 base_url 自定义）
```

三者共享统一的消息格式和工具 Schema，通过 `cli/tools.py` 的 `TOOL_SCHEMAS` 定义。

## 五层漏斗引擎

`core/wyckoff_engine.py` 实现，`FunnelConfig` 数据类包含 ~60 个可调参数。

### Layer 1 — 剥离垃圾

- 剔除 ST / *ST / 北交所 / 科创板
- 市值 ≥ 35 亿（`min_market_cap_yi`）
- 近 20 日均成交额 ≥ 5000 万（`min_avg_amount_wan`）

### Layer 2 — 六通道甄选

| 通道 | 逻辑 |
|------|------|
| 主升 | MA50 > MA200 + MA50 斜率向上 |
| 点火 | 近期放量突破 + MA20 拐头 |
| 潜伏 | 低位横盘 + 缩量 + MA20 走平 |
| 吸筹 | 在底部区间 + 量价特征符合 Wyckoff 吸筹 |
| 地量 | 极度缩量 + 价格不再创新低 |
| 护盘 | RS 相对强度分歧 |

### Layer 2.5 — Markup 识别

MA50 上穿 MA200 + 角度验证 → 标注已进入上升趋势。

### Layer 3 — 板块共振

统计 L2 通过股票的行业分布，保留 Top-N 行业的标的。

### Layer 4 — 微观狙击

| 信号 | 含义 |
|------|------|
| Spring | 终极震仓——跌破支撑后快速收回 |
| LPS | 缩量回踩最后支撑点 |
| SOS | 低位放量突破（Sign of Strength） |
| EVR | 放量不跌（Effort vs Result） |

### Layer 5 — 退出信号

止损 -7%、盈利激活 +15% 后回撤 -10% 止盈、派发警告。

## 信号确认状态机

`core/signal_confirmation.py` 实现 L4 触发信号经 1-3 天价格确认：

```
pending ──(价格确认)──→ confirmed（可操作）
   │
   └──(超时)──→ expired（失效）
```

TTL：SOS 2 天、Spring 3 天、LPS 3 天、EVR 2 天。

## Pipeline 执行流

定时任务（`.github/workflows/wyckoff_funnel.yml`）：

```
cron (周日-周四 18:25 北京) / 手动触发
  │
  ├─→ Step 2: 全市场 OHLCV → 五层漏斗 → ~30 候选
  │
  ├─→ Step 3: LLM 三阵营研报 → 飞书推送
  │
  └─→ Step 4: LLM 持仓决策 → OMS 风控 → Telegram 推送
```

| 步骤 | 代码 | 本质 |
|------|------|------|
| Funnel | `scripts/wyckoff_funnel.py` → `core/wyckoff_engine.py` | 确定性量价计算 |
| Report | `scripts/step3_batch_report.py` | 单次 LLM 调用 |
| Rebalance | `scripts/step4_rebalancer.py` | LLM + OMS 风控 |

## 数据源降级

```
tushare(★) → akshare → baostock → efinance
```

- `TUSHARE_TOKEN` 未配置时自动跳过
- baostock 有熔断机制（连续 10 次失败后暂停）
- 指数 / 大盘数据固定走 tushare
- 可通过环境变量禁用：`DATA_SOURCE_DISABLE_AKSHARE=1`

## LLM 支持

### CLI 三选一

| Provider | SDK | 默认模型 |
|----------|-----|---------|
| Gemini | google-genai | gemini-2.5-flash |
| Claude | anthropic | claude-sonnet-4-20250514 |
| OpenAI | openai | gpt-4o |

OpenAI provider 支持 `base_url`，兼容 DeepSeek / Qwen / Kimi 等端点。

### Pipeline 八厂商

Gemini / OpenAI / DeepSeek / Qwen / Kimi / 智谱 / 火山引擎 / Minimax

通过 `integrations/llm_client.py` 直连，无中间层。

### Web Agent

Google ADK 原生 Gemini，可通过 LiteLLM 桥接切换其他模型。

## 云端存储（Supabase）

| 表 | 用途 |
|----|------|
| `portfolios` | 投资组合元数据 |
| `portfolio_positions` | 持仓明细 |
| `trade_orders` | AI 交易建议 |
| `daily_nav` | 每日净值快照 |
| `user_settings` | 用户配置（API Key / Webhook 等） |
| `stock_hist_cache` | 行情缓存（qfq，滚动 400 天） |
| `recommendations` | 推荐跟踪 |
| `signal_pending` | 信号确认池 |

Web 端通过用户 JWT 走 RLS，CLI 通过 `access_token` 走 RLS，脚本通过 `service_role_key` 绕过 RLS。

## 完整配置项

### 环境变量（.env）

| 变量 | 必填 | 说明 |
|------|------|------|
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_KEY` | 是 | Supabase anon key |
| `GEMINI_API_KEY` | 是* | Gemini（或配其他厂商 Key） |
| `TUSHARE_TOKEN` | 否 | 高级数据源 |
| `FEISHU_WEBHOOK_URL` | 否 | 飞书推送 |
| `WECOM_WEBHOOK_URL` | 否 | 企微推送 |
| `DINGTALK_WEBHOOK_URL` | 否 | 钉钉推送 |
| `TG_BOT_TOKEN` | 否 | Telegram Bot |
| `TG_CHAT_ID` | 否 | Telegram Chat ID |
| `TAVILY_API_KEY` | 否 | RAG 防雷 |
| `SUPABASE_SERVICE_ROLE_KEY` | 否 | 脚本侧写库 |

### GitHub Actions Secrets

以上所有变量 + 额外：

| 变量 | 说明 |
|------|------|
| `SUPABASE_USER_ID` | Step4 目标用户 |
| `MY_PORTFOLIO_STATE` | 本地持仓兜底（JSON） |
| `DEFAULT_LLM_PROVIDER` | 定时任务 LLM 厂商 |
| `GEMINI_MODEL` | 模型覆盖 |

### Streamlit Secrets（Web 后台任务）

| 变量 | 说明 |
|------|------|
| `GITHUB_ACTIONS_TOKEN` | 触发 workflow_dispatch |
| `GITHUB_ACTIONS_ALLOWED_USER_IDS` | 白名单 |

## 日线回测

```bash
python -m scripts.backtest_runner \
  --start 2025-01-01 --end 2025-12-31 \
  --hold-days 15 --top-n 3 \
  --exit-mode sltp --stop-loss -9 --take-profit 0
```

输出：`summary_*.md`（收益/风险统计）+ `trades_*.csv`（逐笔明细）

偏差说明：
- 默认关闭当前截面过滤（降低前视偏差）
- 含双边摩擦成本 0.2%
- 仍存在幸存者偏差

## RAG 防雷

基于 akshare 东方财富新闻搜索，自动过滤含负面关键词的股票：

立案、调查、证监会、处罚、退市、减持、造假、质押爆仓、债务违约、业绩预亏等。

## 部署

### Streamlit Cloud

1. Fork 仓库
2. [Streamlit Cloud](https://share.streamlit.io/) 部署，入口 `streamlit_app.py`
3. 配置 Secrets：`SUPABASE_URL`、`SUPABASE_KEY`、`COOKIE_SECRET`

### 自建

```bash
pip install -e ".[streamlit]"
streamlit run streamlit_app.py
```
