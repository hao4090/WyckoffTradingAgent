import Foundation
import OSLog

@MainActor
final class ReadingRoomStore: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var activeSteps: [AgentStep] = []
    @Published var draft = ""
    @Published var isRunning = false

    private let client: WyckoffCLIClient
    private let logger = Logger(subsystem: "com.youngcan.WyckoffMac", category: "ReadingRoom")
    private var task: Task<Void, Never>?

    init(client: WyckoffCLIClient = WyckoffCLIClient()) {
        self.client = client
    }

    func send(_ rawText: String? = nil) {
        let text = (rawText ?? draft).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isRunning else {
            return
        }
        draft = ""
        let history = encodedHistory()
        messages.append(ChatMessage(role: .user, content: text))
        activeSteps = []
        isRunning = true
        logger.info("Sending Reading Room prompt")

        task = Task { [weak self] in
            guard let self else { return }
            do {
                try await self.client.stream(prompt: text, history: history) { [weak self] event in
                    self?.handle(event)
                }
            } catch {
                self.appendError(error.localizedDescription)
            }
            self.isRunning = false
            self.task = nil
        }
    }

    func cancel() {
        logger.info("Cancelling Reading Room prompt")
        client.cancel()
        task?.cancel()
        task = nil
        isRunning = false
    }

    func newChat() {
        cancel()
        messages = []
        activeSteps = []
        draft = ""
    }

    private func handle(_ event: CLIEvent) {
        switch event.type {
        case "text_delta":
            appendAssistantText(event.text)
        case "tool_start":
            appendStep(kind: .tool, title: displayName(for: event.name), detail: event.summary)
        case "thinking":
            appendStep(kind: .reasoning, title: "推理", detail: event.text)
        case "tool_error":
            appendStep(kind: .error, title: displayName(for: event.name), detail: event.error)
        case "done":
            finishAssistantText(event.text)
        case "error":
            appendError(event.error)
        default:
            break
        }
    }

    private func encodedHistory() -> [ReadingHistoryMessage] {
        messages.compactMap { message in
            guard !message.isError, !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return nil
            }
            return ReadingHistoryMessage(role: message.role.rawValue, content: message.content)
        }
    }

    private func appendAssistantText(_ text: String) {
        ensureAssistantMessage()
        messages[messages.count - 1].content += text
    }

    private func finishAssistantText(_ text: String) {
        ensureAssistantMessage()
        if messages[messages.count - 1].content.isEmpty {
            messages[messages.count - 1].content = text
        }
        messages[messages.count - 1].steps = activeSteps
    }

    private func appendError(_ text: String) {
        messages.append(ChatMessage(role: .assistant, content: text, isError: true, steps: activeSteps))
    }

    private func appendStep(kind: AgentStep.Kind, title: String, detail: String) {
        activeSteps.append(AgentStep(kind: kind, title: title, detail: detail))
        ensureAssistantMessage()
        messages[messages.count - 1].steps = activeSteps
    }

    private func ensureAssistantMessage() {
        if messages.last?.role != .assistant || messages.last?.isError == true {
            messages.append(ChatMessage(role: .assistant, content: "", steps: activeSteps))
        }
    }

    private func displayName(for toolName: String) -> String {
        let names = [
            "search_stock_by_name": "搜索",
            "analyze_stock": "读盘诊断",
            "portfolio": "持仓",
            "get_market_overview": "大盘水温",
            "get_market_history": "大盘回看",
            "screen_stocks": "漏斗选股",
            "generate_ai_report": "AI 研报",
            "generate_strategy_decision": "策略建议",
            "query_history": "历史记录",
            "update_portfolio": "持仓管理",
            "run_backtest": "回测",
        ]
        return names[toolName] ?? (toolName.isEmpty ? "工具" : toolName)
    }
}
