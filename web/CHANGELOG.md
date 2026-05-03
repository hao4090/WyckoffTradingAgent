# Changelog

## v1.0.0 (2026-05-03)

React Web App 首版上线，部署到 Cloudflare Pages。

### Features

- **Auth**: Supabase 邮箱登录/注册，AuthGuard 路由保护
- **MarketBar**: 大盘水温横栏 — 上证/A50/VIX 实时指标 + 市场情绪标签
- **Layout**: 侧边栏导航 + 响应式布局（shadcn/ui + Tailwind v4）
- **路由**: `/home` 首页、`/login` 登录、`/chat` 读盘室、`/portfolio` 持仓、`/tracking` 推荐跟踪、`/settings` 设置

### Tech Stack

- React 19 + Vite 6 + TypeScript
- React Router v7 (SPA)
- Tailwind CSS v4 + shadcn/ui
- TanStack Query + Zustand
- Supabase JS SDK (Auth + DB)
- Cloudflare Pages 自动部署（Git push → build → deploy）

### Links

- Web App: https://wyckoff-analysis.pages.dev/home
- Streamlit: https://wyckoff-analysis-youngcanphoenix.streamlit.app/
