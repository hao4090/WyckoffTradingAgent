const LOCAL_API_URL = 'http://127.0.0.1:8787'
const PRODUCTION_API_URL = ''

export function apiUrl(path: `/api/${string}`): string {
  const configured = import.meta.env.VITE_API_URL?.trim()
  const base = configured || (import.meta.env.DEV ? LOCAL_API_URL : PRODUCTION_API_URL)
  return `${base.replace(/\/$/, '')}${path}`
}
