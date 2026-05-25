import type { User } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'

const SESSION_KEY = 'wyckoff.activity.session_id'

type ActivityOptions = {
  feature?: string
  route?: string
  success?: boolean
  durationMs?: number
  metadata?: Record<string, string | number | boolean | null | undefined>
}

function sessionId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY)
    if (existing) return existing
    const next = crypto.randomUUID()
    sessionStorage.setItem(SESSION_KEY, next)
    return next
  } catch {
    return crypto.randomUUID()
  }
}

function safeMetadata(metadata: ActivityOptions['metadata']) {
  const out: Record<string, string | number | boolean> = {}
  for (const [key, value] of Object.entries(metadata || {})) {
    if (value === null || value === undefined) continue
    out[key.slice(0, 64)] = typeof value === 'string' ? value.slice(0, 256) : value
  }
  return out
}

export function trackActivity(user: User | null | undefined, eventName: string, options: ActivityOptions = {}) {
  if (!user?.id || !eventName) return
  void supabase.from('user_activity_events').insert({
    event_id: crypto.randomUUID(),
    user_id: user.id,
    source: 'web',
    session_id: sessionId(),
    event_name: eventName,
    feature: options.feature || eventName,
    route: options.route || window.location.pathname,
    success: options.success ?? true,
    duration_ms: options.durationMs,
    metadata: safeMetadata(options.metadata),
    client_ts: new Date().toISOString(),
  }).then(() => undefined, () => undefined)
}
