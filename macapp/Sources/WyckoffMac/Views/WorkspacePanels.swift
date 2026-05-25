import SwiftUI

struct AnalysisPanel: View {
    @State private var symbol = "600519"
    @State private var action = "诊断"
    @State private var includeReport = true
    @State private var days = 120
    var onPrompt: (String) -> Void

    var body: some View {
        WorkspaceCard(title: "单股工作区", subtitle: "输入一个 A 股、ETF、美股或港股代码，直接走 CLI 读盘诊断工具。") {
            Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 12) {
                GridRow {
                    Text("标的")
                    TextField("600519 / AAPL.US / 00700.HK", text: $symbol)
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 260)
                }
                GridRow {
                    Text("动作")
                    Picker("动作", selection: $action) {
                        Text("诊断").tag("诊断")
                        Text("AI 研报").tag("AI 研报")
                        Text("近期行情").tag("近期行情")
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 340)
                }
                GridRow {
                    Text("范围")
                    Stepper("近 \(days) 个交易日", value: $days, in: 20...320, step: 20)
                }
                GridRow {
                    Text("选项")
                    Toggle("诊断后追加研报判断", isOn: $includeReport)
                        .disabled(action == "AI 研报")
                }
            }
            HStack {
                Button {
                    onPrompt(prompt)
                } label: {
                    Label(primaryTitle, systemImage: "play.fill")
                }
                .buttonStyle(.borderedProminent)
                Button("清空") {
                    symbol = ""
                }
            }
        }
    }

    private var primaryTitle: String {
        action == "AI 研报" ? "生成研报" : action
    }

    private var prompt: String {
        let clean = symbol.trimmingCharacters(in: .whitespacesAndNewlines)
        if action == "AI 研报" {
            return "给 \(clean) 出一份威科夫深度研报"
        }
        if action == "近期行情" {
            return "查询 \(clean) 最近 \(days) 个交易日的行情和威科夫量价位置"
        }
        return includeReport ? "帮我看看 \(clean)，诊断后补一段研报式结论" : "帮我看看 \(clean)"
    }
}

struct BattlePanel: View {
    @State private var symbols = "600519, 300750, AAPL.US"
    @State private var mode = "相对强弱"
    @State private var includeValue = true
    var onPrompt: (String) -> Void

    var body: some View {
        WorkspaceCard(title: "多股对抗", subtitle: "用桌面端输入一组标的，交给读盘室做强弱、结构和价值面校准。") {
            TextEditor(text: $symbols)
                .font(.body.monospaced())
                .frame(minHeight: 86)
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Color(nsColor: .separatorColor).opacity(0.5))
                }
            HStack {
                Picker("模式", selection: $mode) {
                    Text("相对强弱").tag("相对强弱")
                    Text("进攻顺序").tag("进攻顺序")
                    Text("风险排雷").tag("风险排雷")
                }
                .pickerStyle(.segmented)
                Toggle("价值面校准", isOn: $includeValue)
            }
            Button {
                onPrompt("比较 \(symbols) 的\(mode)，\(includeValue ? "加入价值面校准" : "只看量价结构")，最后给出排序和生死线")
            } label: {
                Label("开始对抗", systemImage: "bolt.horizontal.fill")
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

struct PortfolioPanel: View {
    @State private var mode = "查看持仓"
    @State private var code = ""
    @State private var name = ""
    @State private var shares = 100
    @State private var cost = 0.0
    var onPrompt: (String) -> Void

    var body: some View {
        WorkspaceCard(title: "持仓工作区", subtitle: "持仓事实仍以 CLI/Supabase 工具返回为准，桌面端只负责任务组织。") {
            Picker("模式", selection: $mode) {
                Text("查看持仓").tag("查看持仓")
                Text("持仓诊断").tag("持仓诊断")
                Text("新增/修改").tag("新增/修改")
                Text("删除").tag("删除")
            }
            .pickerStyle(.segmented)
            if mode == "新增/修改" || mode == "删除" {
                Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
                    GridRow {
                        Text("代码")
                        TextField("600519", text: $code)
                            .textFieldStyle(.roundedBorder)
                    }
                    GridRow {
                        Text("名称")
                        TextField("贵州茅台", text: $name)
                            .textFieldStyle(.roundedBorder)
                    }
                    if mode == "新增/修改" {
                        GridRow {
                            Text("股数")
                            Stepper("\(shares)", value: $shares, in: 1...1_000_000)
                        }
                        GridRow {
                            Text("成本")
                            TextField("成本价", value: $cost, format: .number)
                                .textFieldStyle(.roundedBorder)
                        }
                    }
                }
            }
            Button {
                onPrompt(prompt)
            } label: {
                Label(mode, systemImage: "briefcase.fill")
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var prompt: String {
        switch mode {
        case "持仓诊断":
            return "帮我审一下持仓，有问题的给建议"
        case "新增/修改":
            return "把 \(code) \(name) 加入或更新到我的持仓，股数 \(shares)，成本价 \(cost)"
        case "删除":
            return "从我的持仓里删除 \(code) \(name)"
        default:
            return "我有什么持仓？"
        }
    }
}

struct HistoryPanel: View {
    @State private var source = "形态复盘"
    @State private var limit = 20
    var onPrompt: (String) -> Void

    var body: some View {
        QueryPanel(
            title: "历史记录",
            subtitle: "把复盘、信号和尾盘记录按桌面筛选条件交给读盘室查询。",
            options: ["形态复盘", "信号确认池", "尾盘记录"],
            selected: $source,
            limit: $limit
        ) {
            onPrompt("查询最近 \(limit) 条\(source)，按时间倒序整理重点")
        }
    }
}

struct TrackingPanel: View {
    @State private var status = "pending"
    @State private var limit = 30
    var onPrompt: (String) -> Void

    var body: some View {
        QueryPanel(
            title: "形态跟踪",
            subtitle: "复盘记录和 L4 信号确认池保留原后台维护逻辑，桌面端负责查看和筛选。",
            options: ["pending", "confirmed", "expired", "all"],
            selected: $status,
            limit: $limit
        ) {
            onPrompt("查询信号确认池 status=\(status)，返回 \(limit) 条，并总结哪些最需要关注")
        }
    }
}

struct TailBuyPanel: View {
    @State private var decision = "BUY"
    @State private var limit = 20
    var onPrompt: (String) -> Void

    var body: some View {
        QueryPanel(
            title: "尾盘记录",
            subtitle: "查看 BUY/WATCH 决策、规则分、优先级分和 LLM 复判理由。",
            options: ["BUY", "WATCH", "全部"],
            selected: $decision,
            limit: $limit
        ) {
            onPrompt("查询最近 \(limit) 条尾盘记录，decision=\(decision)，按可执行性排序")
        }
    }
}

struct ExportPanel: View {
    @State private var symbols = "600519,300750,AAPL.US"
    @State private var days = 60
    @State private var format = "Markdown 表格"
    var onPrompt: (String) -> Void

    var body: some View {
        WorkspaceCard(title: "行情导出", subtitle: "桌面端先组织导出请求，后续可以接 Finder 保存面板和本地文件产物。") {
            TextField("代码列表，逗号分隔", text: $symbols)
                .textFieldStyle(.roundedBorder)
            HStack {
                Stepper("近 \(days) 日", value: $days, in: 20...320, step: 20)
                Picker("格式", selection: $format) {
                    Text("Markdown 表格").tag("Markdown 表格")
                    Text("CSV 字段").tag("CSV 字段")
                    Text("复盘摘要").tag("复盘摘要")
                }
                .frame(width: 190)
            }
            Button {
                onPrompt("整理 \(symbols) 最近 \(days) 日行情，输出\(format)，包含收盘、涨跌、量价位置和风险提示")
            } label: {
                Label("生成导出内容", systemImage: "square.and.arrow.down")
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

struct SettingsPanel: View {
    var onPrompt: (String) -> Void

    var body: some View {
        WorkspaceCard(title: "设置与本机配置", subtitle: "Mac app 读取 CLI 的模型、数据源和登录状态，不额外保存密钥。") {
            VStack(alignment: .leading, spacing: 10) {
                SettingsAction(title: "检查模型", icon: "cpu") {
                    onPrompt("检查我当前读盘室模型配置是否可用，需要补哪些设置？")
                }
                SettingsAction(title: "检查数据源", icon: "key") {
                    onPrompt("检查 TickFlow、Tushare 和 Supabase 配置是否完整，不要泄露密钥")
                }
                SettingsAction(title: "配置建议", icon: "slider.horizontal.3") {
                    onPrompt("根据 Mac app 使用场景，给我一份模型和数据源配置建议")
                }
            }
        }
    }
}

struct CapabilityMapPanel: View {
    var onPrompt: (String) -> Void

    private let rows = [
        ("Web / Mac", "读盘、单股、多股、持仓、跟踪、尾盘、导出、设置"),
        ("CLI", "长上下文、本机文件流、诊断导出、准点触发"),
        ("GitHub Actions", "全市场漏斗、回测、复盘回刷、飞书产物"),
        ("数据库后台", "信号生命周期、推荐表现、权限和用户隔离"),
    ]

    var body: some View {
        WorkspaceCard(title: "能力边界", subtitle: "功能保留，但按运行环境分层，不把长任务塞进 App 主线程。") {
            Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 10) {
                ForEach(rows, id: \.0) { row in
                    GridRow {
                        Text(row.0)
                            .font(.body.weight(.semibold))
                        Text(row.1)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            HStack {
                Button("跑全市场漏斗") {
                    onPrompt("帮我启动全市场漏斗扫描，并说明它应该在 CLI/Actions 怎么跑")
                }
                Button("跑回测") {
                    onPrompt("帮我跑一次最近半年 top3 的漏斗策略回测")
                }
            }
        }
    }
}

private struct QueryPanel: View {
    var title: String
    var subtitle: String
    var options: [String]
    @Binding var selected: String
    @Binding var limit: Int
    var onRun: () -> Void

    var body: some View {
        WorkspaceCard(title: title, subtitle: subtitle) {
            Picker("范围", selection: $selected) {
                ForEach(options, id: \.self) { option in
                    Text(option).tag(option)
                }
            }
            .pickerStyle(.segmented)
            Stepper("返回 \(limit) 条", value: $limit, in: 5...100, step: 5)
            Button {
                onRun()
            } label: {
                Label("查询", systemImage: "magnifyingglass")
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

private struct SettingsAction: View {
    var title: String
    var icon: String
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(title, systemImage: icon)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.bordered)
    }
}
