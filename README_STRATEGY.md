# Wyckoff Strategy Playbook（当前实盘口径）

本文档描述当前仓库实际运行的策略链路（以代码为准），覆盖：
- Step2 漏斗选股（`scripts/wyckoff_funnel.py` + `core/wyckoff_engine.py`）
- Step3 批量 AI 研报（`scripts/step3_batch_report.py`）
- Step4 私人再平衡 OMS（`scripts/step4_rebalancer.py`）

## 1. 运行时序与交易日口径

### 1.1 定时任务
- GitHub Actions：工作日北京时间 18:30 触发（UTC `10:30`）
- 工作流文件：`.github/workflows/wyckoff_funnel.yml`
- 并发策略：`concurrency.cancel-in-progress=true`（同分支新任务会取消旧任务）

### 1.2 目标交易日（统一规则）
统一由 `utils/trading_clock.py::resolve_end_calendar_day()` 计算：
- 北京时间 `17:00-23:59` -> 目标日 `T`
- 北京时间 `00:00-16:59` -> 目标日 `T-1`

### 1.3 强对齐与快照补偿
默认开启 `ENFORCE_TARGET_TRADE_DATE=1`：
- 个股最新交易日必须等于目标交易日
- 若仅落后 1 天且目标日是“今天”，会尝试用实时快照补一根当日 bar
- 仍不对齐则剔除（计入 `date_mismatch`）

---

## 2. Step2：Wyckoff Funnel（全市场筛选）

## 2.1 股票池
- 来源：主板 + 创业板
- 预处理：去重、去 ST
- 当前默认不包含科创板/北交所（代码层也有主板/创业板代码前缀限制）

## 2.2 数据源与并发
- 批次：`BATCH_SIZE=200`
- 并发：`FUNNEL_MAX_WORKERS`（默认 8）
- 可选执行器：`thread` / `process`
- `process` 模式下自动禁用 baostock 并发登录风险
- 单票超时、批次超时、重试机制均已接入

## 2.3 Step0：大盘总闸（水温 + 广度）

### 宏观水温（benchmark）
基于上证指数（`000001`）计算：
- close / MA50 / MA200
- MA50 5 日斜率
- 近 3 日累计涨跌幅

默认判定：
- `RISK_OFF`：`close < MA200` 且 `MA50 < MA200` 且 `MA50斜率<0` 且 `recent3_cum<=-2%`
- `RISK_ON`：`close > MA50 > MA200` 且 `MA50斜率>0` 且 `recent3_cum>=0`
- 否则 `NEUTRAL`

### 市场广度（breadth）
- 定义：全样本中“收盘价 >= MA20”的占比
- 规则：
  - `breadth <= 20%` 强制 `RISK_OFF`
  - `breadth >= 60%` 且 `delta>=0` 强制 `RISK_ON`

### 动态调参（关键）
- `RISK_OFF` 时上调过滤强度：
  - 成交额门槛提升（至少 1 亿，极弱时 1.5 亿）
  - RS 门槛提高
  - RPS 门槛提高
- `RISK_ON` 时放宽 RPS 下限（更允许进攻）

## 2.4 四层漏斗

### Layer1：剥离垃圾
默认阈值（`FunnelConfig`）：
- 市值 >= 20 亿
- 20 日平均成交额 >= 5000 万
- 剔除 ST / 非主板创业板代码

### Layer2：强弱甄别
入选条件：
- `MA50 > MA200`（多头）或大盘连跌时“守住 MA20”
- RS 过滤（相对大盘 N 日超额收益）
- RPS 过滤：
  - `RPS50 >= 85`
  - `RPS120 >= 80`

### Layer3：板块共振
- 统计行业分布，保留 Top-N 行业（默认 `top_n_sectors=3`）

### Layer4：威科夫触发
三类触发并行：
- Spring（终极震仓）
- LPS（缩量回踩）
- EVR（Effort vs Result，巨量滞涨/抗跌）

EVR 已做高位派发保护与次日确认：
- 高位（`bias_200 > 30%`）默认不按 EVR 看多
- 默认 `evr_confirm_days=1`，避免“一日游”假信号

## 2.5 Step2 输出
- 飞书发送：股票池统计、L1/L2/L3/命中、大盘水温、命中列表
- 给 Step3 的输入：命中股票全量（代码+名称+触发标签）

---

## 3. Step3：批量 AI 研报

## 3.1 输入素材
- 来自 Step2 的命中股票（默认全量）
- 每只股票拉取 500 日 `qfq` 数据 + 特征切片
- 额外注入：benchmark context（regime、breadth 等）

## 3.2 量化压缩器（Step 4.5）
默认开启 `STEP3_ENABLE_COMPRESSION=1`，逻辑：
1. 按水温动态过滤 `bias_200` 区间
2. 构造分数：
   - `rs_score`（越高越好）
   - `dry_score`（近5日最小量比越小越好）
   - `base_score = 0.6*rs + 0.4*dry`
3. 识别“动态主线行业”：
   - 行业内样本 >= 2
   - 取平均 RS 最强前 3 行业
4. 主线加成：`wyckoff_score = base_score * (1 + 0.15)`
5. 行业拥挤控制：每行业最多 `STEP3_MAX_PER_INDUSTRY`（默认 5）
6. 全局上限：`STEP3_MAX_AI_INPUT`（默认 25，0 为不限制）

## 3.3 RAG 防雷（P2）
默认开启 `STEP3_ENABLE_RAG_VETO=1`：
- 在压缩后候选上做新闻检索
- 命中负面关键词（立案/退市/处罚/减持等）即 veto
- 支持 Tavily/SerpAPI

## 3.4 LLM 输出约束
- 强制要求输出“观察池 + 可操作池（固定6只）”
- 若模型结构不完整：
  - 先做一次结构修复
  - 仍不合格则追加系统兜底分层

## 3.5 Step3 输出
- 飞书发送完整研报（自动分片，不做摘要压缩）
- 明确记录使用模型
- 为 Step4 提供外部候选语义输入

---

## 4. Step4：私人再平衡 OMS（确定性执行）

## 4.1 账户来源
- 主路径：Supabase `portfolio_id=USER_LIVE:<SUPABASE_USER_ID>`
- 兜底：`MY_PORTFOLIO_STATE`
- `SUPABASE_USER_ID` 未配置则跳过 Step4
- `TG_BOT_TOKEN/TG_CHAT_ID` 未配置则跳过 Step4

## 4.2 LLM 与 OMS 分工
- LLM：只负责给结构化动作（EXIT/TRIM/HOLD/PROBE/ATTACK）
- Python OMS：负责价格、仓位、风控、拒单、审计

## 4.3 OMS 风控规则（核心）
优先级：`EXIT > TRIM > HOLD > PROBE > ATTACK`

参数：
- 静态滑点：`0.5%`
- 单笔风险上限：
  - PROBE：`0.8%` 总权益
  - ATTACK：`1.2%` 总权益
- 单笔预算上限：
  - PROBE：`8%` 总权益
  - ATTACK：`25%` 总权益

A 股手数约束：
- 买卖统一按 100 股整数倍取整
- 不足 100 股 -> `NO_TRADE`

## 4.4 P1 增强
- ATR 跟踪止损：`STEP4_ATR_PERIOD=14`, `STEP4_ATR_MULTIPLIER=2.0`
- 动态滑点保护：`max(静态滑点, ATR*STEP4_ATR_SLIPPAGE_FACTOR)`
- 拒单审计：每个 NO_TRADE 保留原因与审计字段
- 最新价读取：不复权优先，失败回退到前复权，且可做快照补偿

## 4.5 Step4 输出
- Telegram 工单（分区：卖出/持有/买入/拒单）
- 回写 Supabase：
  - `trade_orders`（模型建议与执行票据）
  - `daily_nav`（每日净值快照）
  - `portfolio_positions.stop_loss`（动态止损更新）
- 幂等：同一 `portfolio_id + trade_date` 已执行则跳过

---

## 5. 数据口径与执行纪律

1. 分析口径：以 `qfq` 结构分析为主
2. 执行口径：以“最新实际收盘（不复权优先）”为锚
3. 严禁单点价格：输出为“结构战区 + 确认条件 + 熔断条件”
4. 动作由 OMS 统一裁决，避免纯文本建议直接变成交易动作

---

## 6. 关键环境变量（实盘最小集）

- 通用：
  - `FEISHU_WEBHOOK_URL`
  - `GEMINI_API_KEY`
  - `GEMINI_MODEL`
  - `TUSHARE_TOKEN`
- Step4：
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`（或 `SUPABASE_KEY`）
  - `SUPABASE_USER_ID`
  - `TG_BOT_TOKEN`
  - `TG_CHAT_ID`
  - `MY_PORTFOLIO_STATE`（仅兜底）
- 可选增强：
  - `TAVILY_API_KEY` / `SERPAPI_API_KEY`（RAG 防雷）

---

## 7. 当前策略定位

- 本策略是“日线级 + 结构化风控 + 人机协同”框架：
  - 用漏斗做广域筛选
  - 用 LLM 做结构语义判断
  - 用 OMS 做确定性风控执行
- 不追求盘中高频；重点是提高 T+1 决策稳定性与可复盘性。

