import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { Loader2, Play } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/stores/auth'
import { loadLLMConfig, type LLMConfig } from '@/lib/chat-agent'
import { MarkdownContent } from '@/components/markdown'
import { KlineChart } from '@/components/kline-chart'
import { usePreferences } from '@/lib/preferences'
import { detectWyckoffAnnotations } from '@/lib/wyckoff-detect'

interface KlineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface AnalysisResult {
  report: string
  symbol: string
  name: string
  klineData: KlineData[]
}

async function getUserDataKeys(userId: string): Promise<{ tickflow: string | null; tushare: string | null }> {
  const { data } = await supabase
    .from('user_settings')
    .select('tickflow_api_key, tushare_token')
    .eq('user_id', userId)
    .single()
  return {
    tickflow: data?.tickflow_api_key || null,
    tushare: data?.tushare_token || null,
  }
}

async function checkWhitelist(userId: string): Promise<boolean> {
  const { data } = await supabase
    .from('whitelist')
    .select('user_id')
    .eq('user_id', userId)
    .limit(1)
  return Array.isArray(data) && data.length > 0
}

function normalizeTushareCode(code: string): string {
  if (code.startsWith('6')) return `${code}.SH`
  if (code.startsWith('4') || code.startsWith('8') || code.startsWith('9')) return `${code}.BJ`
  return `${code}.SZ`
}

async function tusharePost(token: string, api_name: string, params: Record<string, string>, fields: string) {
  const resp = await fetch('/api/llm-proxy/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Target-URL': 'https://api.tushare.pro' },
    body: JSON.stringify({ api_name, token, params, fields }),
  })
  if (!resp.ok) return null
  return (await resp.json()) as { data?: { fields?: string[]; items?: unknown[][] } }
}

async function fetchKlineViaTushare(code: string, token: string, startDate: string, endDate: string): Promise<KlineData[]> {
  const tsCode = normalizeTushareCode(code)
  const [dailyJson, adjJson] = await Promise.all([
    tusharePost(token, 'daily', { ts_code: tsCode, start_date: startDate, end_date: endDate }, 'trade_date,open,high,low,close,vol'),
    tusharePost(token, 'adj_factor', { ts_code: tsCode, start_date: startDate, end_date: endDate }, 'trade_date,adj_factor'),
  ])
  const items = dailyJson?.data?.items
  if (!Array.isArray(items) || items.length === 0) return []

  const adjItems = adjJson?.data?.items
  if (!Array.isArray(adjItems) || adjItems.length === 0) return []
  const adjMap = new Map<string, number>()
  let latestDate = ''
  for (const row of adjItems) {
    const dt = String(row[0])
    adjMap.set(dt, Number(row[1]))
    if (dt > latestDate) latestDate = dt
  }
  const latestFactor = adjMap.get(latestDate) || 1

  return items.map(row => {
    const dt = String(row[0] || '')
    const factor = adjMap.get(dt) || latestFactor
    const ratio = factor / latestFactor
    return {
      date: dt.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'),
      open: Number(row[1] || 0) * ratio, high: Number(row[2] || 0) * ratio,
      low: Number(row[3] || 0) * ratio, close: Number(row[4] || 0) * ratio,
      volume: Number(row[5] || 0),
    }
  }).filter(d => d.date && d.close > 0)
}

async function fetchKlineViaTickFlow(code: string, apiKey: string): Promise<KlineData[]> {
  const params = new URLSearchParams({
    symbol: normalizeTickFlowSymbol(code), period: '1d', count: '320', adjust: 'forward',
  })
  const resp = await fetch(`/api/llm-proxy/v1/klines?${params}`, {
    headers: { 'x-api-key': apiKey, 'X-Target-URL': 'https://api.tickflow.org' },
  })
  if (!resp.ok) return []
  const json = await resp.json()
  return parseKlinePayload(json).sort((a, b) => a.date.localeCompare(b.date)).slice(-320)
}

async function fetchKlineFromCache(code: string, startIso: string, endIso: string): Promise<KlineData[]> {
  const { data } = await supabase
    .from('stock_hist_cache')
    .select('date,open,high,low,close,volume')
    .eq('symbol', code)
    .eq('adjust', 'qfq')
    .gte('date', startIso)
    .lte('date', endIso)
    .order('date', { ascending: false })
    .limit(320)
  if (!data || data.length === 0) return []
  return (data as Record<string, unknown>[]).map(r => ({
    date: String(r.date || ''), open: Number(r.open || 0), high: Number(r.high || 0),
    low: Number(r.low || 0), close: Number(r.close || 0), volume: Number(r.volume || 0),
  })).filter(d => d.date && d.close > 0).reverse()
}

const TICKFLOW_PURCHASE = 'https://tickflow.org/auth/register?ref=5N4NKTCPL4'

async function fetchKline(code: string, keys: { tickflow: string | null; tushare: string | null }, userId: string): Promise<KlineData[]> {
  const end = new Date(); end.setDate(end.getDate() - 1)
  const start = new Date(); start.setDate(start.getDate() - 500)
  const fmtCompact = (d: Date) => d.toISOString().slice(0, 10).replace(/-/g, '')

  if (keys.tickflow) {
    try { const r = await fetchKlineViaTickFlow(code, keys.tickflow); if (r.length) return r } catch { /* */ }
  }
  if (keys.tushare) {
    try {
      const r = await fetchKlineViaTushare(code, keys.tushare, fmtCompact(start), fmtCompact(end))
      if (r.length) return r.sort((a, b) => a.date.localeCompare(b.date)).slice(-320)
    } catch { /* */ }
  }
  if (await checkWhitelist(userId)) {
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    const r = await fetchKlineFromCache(code, fmt(start), fmt(end))
    if (r.length) return r
  }
  throw new Error(`无法获取K线数据。推荐购买 TickFlow 获取实时行情：${TICKFLOW_PURCHASE}`)
}

function parseKlinePayload(payload: unknown): KlineData[] {
  if (!payload || typeof payload !== 'object') return []
  const root = payload as Record<string, unknown>
  const data = root.data
  if (Array.isArray(data)) return parseRowArray(data)
  if (Array.isArray(root.records)) return parseRowArray(root.records)
  if (!data || typeof data !== 'object') return []

  const table = data as Record<string, unknown>
  const timestamps = valueArray(table.timestamp)
  if (timestamps.length === 0) return []

  const open = valueArray(table.open)
  const high = valueArray(table.high)
  const low = valueArray(table.low)
  const close = valueArray(table.close)
  const volume = valueArray(table.volume)

  return timestamps
    .map((ts, index) => ({
      date: formatTimestampDate(ts),
      open: Number(open[index] || 0),
      high: Number(high[index] || 0),
      low: Number(low[index] || 0),
      close: Number(close[index] || 0),
      volume: Number(volume[index] || 0),
    }))
    .filter((d) => d.date && d.close > 0)
}

function parseRowArray(rows: unknown[]): KlineData[] {
  return rows
    .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
    .map((r) => ({
      date: String(r.date || r.trade_date || '').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'),
      open: Number(r.open || 0),
      high: Number(r.high || 0),
      low: Number(r.low || 0),
      close: Number(r.close || 0),
      volume: Number(r.volume || r.vol || 0),
    }))
    .filter((d) => d.date && d.close > 0)
}

function valueArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function normalizeTickFlowSymbol(code: string): string {
  if (code.startsWith('0') || code.startsWith('2') || code.startsWith('3')) return `${code}.SZ`
  if (code.startsWith('4') || code.startsWith('8') || code.startsWith('9')) return `${code}.BJ`
  return `${code}.SH`
}

function formatTimestampDate(value: unknown): string {
  const numeric = Number(value)
  if (Number.isFinite(numeric) && numeric > 0) {
    return new Date(numeric + 8 * 3600_000).toISOString().slice(0, 10)
  }
  return String(value || '').slice(0, 10)
}

export function AnalysisPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const { t } = usePreferences()
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState('')
  const [checkingConfig, setCheckingConfig] = useState(true)
  const [hasModelConfig, setHasModelConfig] = useState(false)
  const [hasDataSource, setHasDataSource] = useState(false)
  const wyckoff = useMemo(() => (result?.klineData ? detectWyckoffAnnotations(result.klineData) : null), [result?.klineData])

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get('code')
    if (code && /^\d{6}$/.test(code)) setSymbol(code)
  }, [])

  useEffect(() => {
    if (!user) return
    void checkPrerequisites(user.id)
  }, [user])

  async function checkPrerequisites(userId: string) {
    setCheckingConfig(true)
    try {
      const [config, dataKeys, wl] = await Promise.all([
        loadLLMConfig(userId),
        getUserDataKeys(userId),
        checkWhitelist(userId),
      ])
      setHasModelConfig(Boolean(config?.api_key && config.model))
      setHasDataSource(Boolean(dataKeys.tickflow || dataKeys.tushare || wl))
    } finally {
      setCheckingConfig(false)
    }
  }

  function getMissingRequirements(modelReady: boolean, dataReady: boolean): string[] {
    const missing: string[] = []
    if (!modelReady) missing.push(t('analysis.modelRequirement'))
    if (!dataReady) missing.push(t('analysis.dataRequirement'))
    return missing
  }

  async function handleAnalyze() {
    const code = symbol.trim().replace(/\D/g, '')
    if (code.length !== 6) { setError(t('common.invalidStockCode')); return }

    setError('')
    setLoading(true)
    setResult(null)

    try {
      const [config, dataKeys] = await Promise.all([
        loadLLMConfig(user!.id),
        getUserDataKeys(user!.id),
      ])
      const modelReady = Boolean(config?.api_key && config?.model)
      setHasModelConfig(modelReady)

      if (!modelReady) {
        const missing = getMissingRequirements(modelReady, true)
        setError(t('analysis.missingPrefix', { items: missing.join('、') }))
        setLoading(false)
        return
      }
      if (!config) {
        setError(t('analysis.configError'))
        setLoading(false)
        return
      }

      const [stockInfoResult, klineData] = await Promise.all([
        supabase.from('recommendation_tracking').select('name').eq('code', parseInt(code)).limit(1).single(),
        fetchKline(code, dataKeys, user!.id),
      ])

      const name = stockInfoResult.data?.name || code
      if (klineData.length === 0) {
        setError(t('analysis.noKlineData'))
        setLoading(false)
        return
      }

      const klinePayload = buildKlinePayload(klineData)
      const report = await callLLM(config, code, name, klinePayload)
      setResult({ report, symbol: code, name, klineData })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('analysis.failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col p-6">
      <h1 className="mb-6 text-xl font-semibold">{t('analysis.title')}</h1>

      {!checkingConfig && (!hasModelConfig || !hasDataSource) && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50/80 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
          <h2 className="mb-2 text-sm font-semibold text-amber-900 dark:text-amber-100">{t('analysis.missingTitle')}</h2>
          <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-amber-800 dark:text-amber-200">
            {!hasModelConfig && <li>{t('analysis.missingModel')}</li>}
            {!hasDataSource && <li>{t('analysis.missingDataSource')}</li>}
          </ul>
          <button
            onClick={() => navigate('/settings')}
            className="rounded-lg bg-amber-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-800"
          >
            {t('analysis.goSettings')}
          </button>
        </div>
      )}

      {/* Input */}
      <div className="mb-6 flex items-end gap-3">
        <div className="flex-1 max-w-xs">
          <label className="mb-1.5 block text-sm font-medium">{t('common.stockCode')}</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder={t('common.exampleCode')}
            maxLength={6}
            className="w-full rounded-lg border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring/20"
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
          />
        </div>
        <button
          onClick={handleAnalyze}
          disabled={loading || !symbol.trim() || checkingConfig || !hasModelConfig || !hasDataSource}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {loading ? t('analysis.analyzing') : t('analysis.start')}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-200">{error}</div>
      )}

      {/* Result */}
      {result && (
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="mb-4 flex items-center gap-2">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              {result.symbol} {result.name}
            </span>
          </div>

          {/* K-line Chart */}
          {result.klineData.length > 0 && (
            <section className="mb-6">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">{t('analysis.chartTitle')}</h2>
                  <p className="mt-1 text-xs text-muted-foreground">{t('analysis.chartSubtitle')}</p>
                </div>
                <span className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
                  {result.klineData.length} {t('common.rows')}
                </span>
              </div>
              <KlineChart data={result.klineData} height={350} wyckoffMarkers={wyckoff?.markers} tradingRange={wyckoff?.tradingRange ?? undefined} stage={wyckoff?.stage} />
            </section>
          )}

          {/* Report */}
          <div className="rounded-lg border border-border p-6">
            <h2 className="mb-4 text-base font-semibold">{t('analysis.reportTitle')}</h2>
            <article className="prose prose-sm max-w-none text-foreground">
              <MarkdownContent content={result.report} />
            </article>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          <div className="text-center">
            <div className="mb-3 text-4xl">📊</div>
            <p className="text-sm">{t('analysis.emptyTitle')}</p>
            <p className="mt-1 text-xs">{t('analysis.emptySubtitle')}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function buildKlinePayload(data: KlineData[]): string {
  const last = data[data.length - 1]!
  const prev20 = data.slice(-20)
  const ma5 = avg(data.slice(-5).map((d) => d.close))
  const ma20 = avg(prev20.map((d) => d.close))
  const ma50 = data.length >= 50 ? avg(data.slice(-50).map((d) => d.close)) : 0

  const summary = [
    `日线数据摘要（前复权，共${data.length}根，按日期升序）：`,
    `最新收盘：${last.close.toFixed(2)}`,
    `MA5=${ma5.toFixed(2)} MA20=${ma20.toFixed(2)}${ma50 ? ` MA50=${ma50.toFixed(2)}` : ''}`,
    `近20日最高：${Math.max(...prev20.map((d) => d.high)).toFixed(2)}`,
    `近20日最低：${Math.min(...prev20.map((d) => d.low)).toFixed(2)}`,
    `近5日平均量：${avg(data.slice(-5).map((d) => d.volume)).toFixed(0)}`,
    `近20日平均量：${avg(prev20.map((d) => d.volume)).toFixed(0)}`,
  ].join('\n')
  const csvRows = data.map((d) => [
    d.date,
    fixed(d.open),
    fixed(d.high),
    fixed(d.low),
    fixed(d.close),
    Math.round(d.volume),
  ].join(','))

  return [
    summary,
    '',
    '以下是近320个交易日以内的完整日线OHLCV CSV数据。你必须读取这些数据进行判断，不要声称无法读取日线数据。',
    '```csv',
    'date,open,high,low,close,volume',
    ...csvRows,
    '```',
  ].join('\n')
}

function avg(arr: number[]): number {
  return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
}

function fixed(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : '0.00'
}

async function callLLM(config: LLMConfig, code: string, name: string, klinePayload: string): Promise<string> {
  const systemPrompt = `你是威科夫分析大师，精通量价分析和威科夫方法。请对给定股票进行深度分析，包括：
1. 当前所处威科夫阶段（积累/上涨/派发/下跌），Phase A-E 定位
2. 量价关系分析（供需力量对比）
3. 关键支撑与阻力位
4. 主力意图判断
5. 操作建议与风险提示（含止损位）

请用简洁、专业的中文回答。使用 markdown 格式，结构清晰。`

  const userMsg = `请分析股票 ${code} ${name}。基于威科夫理论给出当前阶段判断和操作建议。\n\n${klinePayload}`

  const response = await fetch('/api/llm-proxy/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.api_key}`,
      'X-Target-URL': config.base_url,
    },
    body: JSON.stringify({
      model: config.model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userMsg },
      ],
      temperature: 0.7,
      max_tokens: 4096,
    }),
  })

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}))
    throw new Error(errData.error?.message || `API 请求失败 (${response.status})`)
  }

  const data = await response.json()
  return data.choices?.[0]?.message?.content || '未获取到分析结果'
}
