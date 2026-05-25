import SwiftUI

enum AppSection: String, CaseIterable, Identifiable {
    case readingRoom
    case analysis
    case battle
    case portfolio
    case history
    case tracking
    case tailBuy
    case export
    case settings
    case capabilityMap

    var id: String { rawValue }

    var title: String {
        switch self {
        case .readingRoom: "读盘室"
        case .analysis: "单股分析"
        case .battle: "多股对抗"
        case .portfolio: "持仓诊断"
        case .history: "本地历史"
        case .tracking: "形态跟踪"
        case .tailBuy: "尾盘记录"
        case .export: "行情导出"
        case .settings: "设置"
        case .capabilityMap: "能力边界"
        }
    }

    var detail: String {
        switch self {
        case .readingRoom: "CLI Agent 原生接入"
        case .analysis: "320 日日线、价值快照、AI 报告"
        case .battle: "相对强弱、叠加与分图"
        case .portfolio: "数据库/手工持仓体检"
        case .history: "复盘、对抗、诊断沉淀"
        case .tracking: "形态复盘与信号池"
        case .tailBuy: "BUY/WATCH 尾盘策略"
        case .export: "批量行情与表格"
        case .settings: "模型、数据源、本机配置"
        case .capabilityMap: "Web、CLI、Actions 的边界"
        }
    }

    var systemImage: String {
        switch self {
        case .readingRoom: "message"
        case .analysis: "chart.xyaxis.line"
        case .battle: "bolt.horizontal"
        case .portfolio: "briefcase"
        case .history: "clock.arrow.circlepath"
        case .tracking: "waveform.path.ecg"
        case .tailBuy: "moon"
        case .export: "square.and.arrow.down"
        case .settings: "gearshape"
        case .capabilityMap: "map"
        }
    }

    var executionLane: String {
        switch self {
        case .analysis, .battle, .portfolio, .history, .tracking, .tailBuy, .export, .settings:
            "读盘室执行"
        case .readingRoom:
            "本机 CLI"
        case .capabilityMap:
            "系统边界"
        }
    }

    var laneIcon: String {
        switch self {
        case .capabilityMap: "point.3.connected.trianglepath.dotted"
        case .readingRoom: "terminal"
        default: "bolt.horizontal"
        }
    }

    var workspaceFacts: [WorkspaceFact] {
        switch self {
        case .analysis:
            return [
                .init("数据", "320 日日线 + 价值面", "chart.bar"),
                .init("输出", "诊断 / 研报 / 行情", "doc.text.magnifyingglass"),
                .init("执行", "analyze_stock / report", "terminal"),
            ]
        case .battle:
            return [
                .init("输入", "多标的列表", "list.bullet.rectangle"),
                .init("比较", "强弱 / 风险 / 顺序", "arrow.left.arrow.right"),
                .init("执行", "读盘室综合分析", "message"),
            ]
        case .portfolio:
            return [
                .init("事实", "实时 portfolio 工具", "briefcase"),
                .init("模式", "查看 / 诊断 / 调仓", "switch.2"),
                .init("边界", "先计划，后确认", "checkmark.shield"),
            ]
        case .history, .tracking, .tailBuy:
            return [
                .init("来源", "本地缓存 / Supabase", "tray.full"),
                .init("筛选", "状态 / 决策 / 条数", "line.3.horizontal.decrease.circle"),
                .init("输出", "重点标的与风险", "target"),
            ]
        case .export:
            return [
                .init("输入", "代码列表 + 周期", "tablecells"),
                .init("格式", "表格 / CSV / 摘要", "square.and.arrow.down"),
                .init("下一步", "Finder 保存面板", "folder"),
            ]
        case .settings:
            return [
                .init("模型", "~/.wyckoff 配置", "cpu"),
                .init("数据源", "TickFlow / Tushare", "key"),
                .init("安全", "不复制密钥", "lock"),
            ]
        case .capabilityMap:
            return [
                .init("轻任务", "Web / Mac", "macwindow"),
                .init("长任务", "CLI / Actions", "clock"),
                .init("数据", "RLS 与后台维护", "server.rack"),
            ]
        case .readingRoom:
            return [
                .init("运行时", "CLI AgentRuntime", "terminal"),
                .init("工具", "ToolRegistry", "wrench.and.screwdriver"),
                .init("上下文", "压缩与记忆", "brain"),
            ]
        }
    }

    var quickPrompts: [String] {
        switch self {
        case .readingRoom:
            ["当前大盘水温怎么样？", "帮我看看 600519", "我有什么持仓？"]
        case .analysis:
            ["帮我看看 600519", "分析一下 AAPL.US", "给 00700.HK 出一份威科夫研判"]
        case .battle:
            ["比较 600519、300750、AAPL.US 的相对强弱", "帮我在宁德时代和比亚迪之间做对抗分析"]
        case .portfolio:
            ["我有什么持仓？", "帮我审一下持仓，有问题的给建议"]
        case .history:
            ["最近形态复盘记录？", "最近尾盘买入记录？"]
        case .tracking:
            ["查一下信号确认池", "最近复盘记录表现如何？"]
        case .tailBuy:
            ["昨天尾盘推了什么？", "最近尾盘 BUY 记录有哪些？"]
        case .export:
            ["帮我导出 600519,300750 最近行情摘要", "给我整理一份候选股行情清单"]
        case .settings:
            ["我当前模型配置正常吗？", "我需要配置哪些数据源？"]
        case .capabilityMap:
            ["哪些能力适合放在 Mac app？", "全市场漏斗和回测应该怎么跑？"]
        }
    }

    var capabilityLines: [String] {
        switch self {
        case .readingRoom:
            ["复用 CLI 的 AgentRuntime、ToolRegistry 和核心 system prompt。", "工具调用、上下文压缩、后台任务和本地配置保持与终端读盘室一致。"]
        case .analysis:
            ["单股 320 日日线结构、威科夫阶段、价值面校准、AI 研报。", "Mac 端通过读盘室快捷动作进入，不复制 Web Agent 工具层。"]
        case .battle:
            ["多标的强弱对比、叠加/分图、价值面校准。", "适合作为下一步原生图表工作区扩展。"]
        case .portfolio:
            ["查看持仓、逐只诊断、现金和仓位建议。", "当前事实必须实时调用 portfolio 工具，不信历史摘要。"]
        case .history:
            ["本地历史、会话日志、诊断导出和分叉。", "桌面端更适合承接 CLI 本机文件流。"]
        case .tracking:
            ["形态复盘、信号确认池、推荐表现回刷结果。", "查询类动作走读盘室，长任务继续由后台维护。"]
        case .tailBuy:
            ["尾盘 BUY/WATCH 决策、规则分、优先级分和 LLM 复判理由。", "结果查询走本机 CLI 或数据库缓存。"]
        case .export:
            ["批量行情导出、候选池整理和后续文档产物。", "浏览器本地历史与桌面文件导出可分层演进。"]
        case .settings:
            ["模型、数据源、Supabase session 仍使用 CLI 的 ~/.wyckoff 配置。", "这样 Mac app 不需要额外保存密钥。"]
        case .capabilityMap:
            ["高频读盘放在 Web/Mac；全市场漏斗、回测、回刷、维护任务留给 CLI、Actions 或数据库后台。", "Mac app 可以逐步补齐 CF Pages 的轻量工作台能力。"]
        }
    }
}

struct WorkspaceFact {
    var title: String
    var value: String
    var icon: String

    init(_ title: String, _ value: String, _ icon: String) {
        self.title = title
        self.value = value
        self.icon = icon
    }
}
