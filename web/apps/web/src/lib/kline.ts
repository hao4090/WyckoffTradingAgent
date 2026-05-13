import { supabase } from './supabase'

export interface KlineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export const TICKFLOW_PURCHASE = 'https://tickflow.org/auth/register?ref=5N4NKTCPL4'

export function isCnSymbol(code: string): boolean {
  return /^\d{6}$/.test(code.trim())
}

export function isTickFlowMarketSymbol(code: string): boolean {
  const c = code.trim().toUpperCase()
  return /^\d{5}\.HK$/.test(c) || /^[A-Z][A-Z0-9.-]{0,15}\.US$/.test(c)
}

export function isSupportedKlineCode(code: string): boolean {
  return isCnSymbol(code) || isTickFlowMarketSymbol(code)
}

export function detectMarket(code: string): 'cn' | 'hk' | 'us' {
  const c = code.trim().toUpperCase()
  if (isCnSymbol(c)) return 'cn'
  if (/^\d{5}\.HK$/.test(c)) return 'hk'
  return 'us'
}

export function normalizeTickFlowSymbol(code: string): string {
  const c = code.trim().toUpperCase()
  if (isTickFlowMarketSymbol(c)) return c
  if (!isCnSymbol(c)) return c
  if (c.startsWith('0') || c.startsWith('1') || c.startsWith('2') || c.startsWith('3')) return `${c}.SZ`
  if (c.startsWith('4') || c.startsWith('8') || c.startsWith('9')) return `${c}.BJ`
  return `${c}.SH`
}

export function normalizeTushareCode(code: string): string {
  if (/^\d{6}$/.test(code)) {
    if (code.startsWith('6') || code.startsWith('5')) return `${code}.SH`
    if (code.startsWith('4') || code.startsWith('8') || code.startsWith('9')) return `${code}.BJ`
    return `${code}.SZ`
  }
  return code
}

function formatTimestampDate(value: unknown): string {
  const numeric = Number(value)
  if (Number.isFinite(numeric) && numeric > 0) {
    return new Date(numeric + 8 * 3600_000).toISOString().slice(0, 10)
  }
  return String(value || '').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3').slice(0, 10)
}

function parseRowArray(rows: unknown[]): KlineData[] {
  return (rows as Record<string, unknown>[])
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

function parseKlinePayload(payload: unknown): KlineData[] {
  if (!payload || typeof payload !== 'object') return []
  const root = payload as Record<string, unknown>
  const data = root.data
  if (Array.isArray(data)) return parseRowArray(data)
  if (Array.isArray(root.records)) return parseRowArray(root.records)
  if (!data || typeof data !== 'object') return []

  const table = data as Record<string, unknown[]>
  const timestamps = Array.isArray(table.timestamp) ? table.timestamp : []
  if (timestamps.length === 0) return []

  const open = table.open || [], high = table.high || [], low = table.low || []
  const close = table.close || [], volume = table.volume || []

  return timestamps
    .map((ts, i) => ({
      date: formatTimestampDate(ts),
      open: Number(open[i] || 0),
      high: Number(high[i] || 0),
      low: Number(low[i] || 0),
      close: Number(close[i] || 0),
      volume: Number(volume[i] || 0),
    }))
    .filter((d) => d.date && d.close > 0)
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

export async function fetchKlineViaTushare(code: string, token: string, startDate: string, endDate: string): Promise<KlineData[]> {
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

export async function fetchKlineViaTickFlow(code: string, apiKey: string): Promise<KlineData[]> {
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

export async function fetchKlineFromCache(code: string, startIso: string, endIso: string): Promise<KlineData[]> {
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
  return parseRowArray(data).reverse()
}

export async function getUserDataKeys(userId: string): Promise<{ tickflow: string | null; tushare: string | null }> {
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

export async function checkWhitelist(userId: string): Promise<boolean> {
  const { data } = await supabase
    .from('whitelist')
    .select('user_id')
    .eq('user_id', userId)
    .limit(1)
  return Array.isArray(data) && data.length > 0
}

export async function fetchKline(
  code: string,
  keys: { tickflow: string | null; tushare: string | null },
  userId: string,
): Promise<KlineData[]> {
  const end = new Date(); end.setDate(end.getDate() - 1)
  const start = new Date(); start.setDate(start.getDate() - 500)
  const fmtCompact = (d: Date) => d.toISOString().slice(0, 10).replace(/-/g, '')
  const fmtIso = (d: Date) => d.toISOString().slice(0, 10)
  const isCn = isCnSymbol(code)

  if (keys.tickflow) {
    try { const r = await fetchKlineViaTickFlow(code, keys.tickflow); if (r.length) return r } catch { /* fallthrough */ }
  }
  if (isCn && keys.tushare) {
    try {
      const r = await fetchKlineViaTushare(code, keys.tushare, fmtCompact(start), fmtCompact(end))
      if (r.length) return r.sort((a, b) => a.date.localeCompare(b.date)).slice(-320)
    } catch { /* fallthrough */ }
  }
  if (isCn && await checkWhitelist(userId)) {
    const r = await fetchKlineFromCache(code, fmtIso(start), fmtIso(end))
    if (r.length) return r
  }
  const suffixHint = isCn ? '' : '美股/港股请使用 TickFlow 标准代码（如 AAPL.US / 00700.HK）。'
  throw new Error(`无法获取K线数据。${suffixHint}请检查股票代码、TickFlow Key 或稍后重试：${TICKFLOW_PURCHASE}`)
}
