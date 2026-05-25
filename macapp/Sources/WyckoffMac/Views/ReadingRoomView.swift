import SwiftUI

struct ReadingRoomView: View {
    @ObservedObject var store: ReadingRoomStore

    var body: some View {
        VStack(spacing: 0) {
            ReadingRoomToolbar(store: store)
            Divider()
            messageList
            Divider()
            ReadingRoomComposer(store: store)
        }
        .background(MacTheme.background)
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    if store.messages.isEmpty {
                        EmptyReadingRoomView(store: store)
                            .padding(.top, 64)
                    }
                    ForEach(store.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                    if store.isRunning && store.messages.last?.content.isEmpty == false {
                        ProgressView()
                            .controlSize(.small)
                            .padding(.horizontal, 24)
                    }
                }
                .padding(24)
            }
            .onChange(of: store.messages) { messages in
                guard let last = messages.last else { return }
                withAnimation(.easeOut(duration: 0.18)) {
                    proxy.scrollTo(last.id, anchor: .bottom)
                }
            }
        }
    }
}

private struct ReadingRoomToolbar: View {
    @ObservedObject var store: ReadingRoomStore

    var body: some View {
        HStack(spacing: 10) {
            Label("读盘室", systemImage: "message")
                .font(.headline)
                .foregroundStyle(MacTheme.foreground)
            Text("CLI AgentRuntime")
                .font(.caption)
                .foregroundStyle(MacTheme.mutedForeground)
            Spacer()
            Button {
                store.newChat()
            } label: {
                Label("新对话", systemImage: "plus.message")
            }
            .disabled(store.isRunning)
            if store.isRunning {
                Button(role: .cancel) {
                    store.cancel()
                } label: {
                    Label("停止", systemImage: "stop.fill")
                }
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
    }
}

private struct EmptyReadingRoomView: View {
    @ObservedObject var store: ReadingRoomStore

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                Text("我只看供给、需求和主力行为")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(MacTheme.foreground)
                Text("这块原生界面通过本地 CLI 读盘室运行，工具路由和安全边界与终端保持一致。")
                    .foregroundStyle(MacTheme.mutedForeground)
            }
            FlowLayout(items: AppSection.readingRoom.quickPrompts) { prompt in
                Button(prompt) {
                    store.send(prompt)
                }
                .buttonStyle(.bordered)
                .disabled(store.isRunning)
            }
        }
        .frame(maxWidth: 620, alignment: .leading)
    }
}

private struct MessageBubble: View {
    var message: ChatMessage

    var body: some View {
        HStack(alignment: .top) {
            if message.role == .user {
                Spacer(minLength: 80)
            }
            VStack(alignment: .leading, spacing: 8) {
                if !message.steps.isEmpty {
                    StepSummaryView(steps: message.steps)
                }
                if message.isError || message.role == .user {
                    Text(message.content.isEmpty ? " " : message.content)
                        .textSelection(.enabled)
                        .font(.body)
                        .lineSpacing(3)
                        .foregroundStyle(message.isError ? .red : MacTheme.foreground)
                } else {
                    MarkdownContentView(content: message.content.isEmpty ? " " : message.content)
                }
            }
            .padding(12)
            .frame(maxWidth: 720, alignment: .leading)
            .background(message.role == .user ? MacTheme.accent : MacTheme.muted, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
            if message.role == .assistant {
                Spacer(minLength: 80)
            }
        }
    }
}

private struct StepSummaryView: View {
    var steps: [AgentStep]
    @State private var expanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(steps) { step in
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: icon(for: step.kind))
                            .frame(width: 14)
                            .foregroundStyle(color(for: step.kind))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(step.title)
                                .font(.caption.weight(.medium))
                            if !step.detail.isEmpty {
                                Text(step.detail)
                                    .font(.caption2)
                                    .foregroundStyle(MacTheme.mutedForeground)
                                    .lineLimit(3)
                            }
                        }
                    }
                }
            }
            .padding(.top, 6)
        } label: {
            Text("\(steps.count) 个运行步骤")
                .font(.caption)
                .foregroundStyle(MacTheme.mutedForeground)
        }
    }

    private func icon(for kind: AgentStep.Kind) -> String {
        switch kind {
        case .tool: "wrench.and.screwdriver"
        case .reasoning: "brain"
        case .error: "exclamationmark.triangle"
        }
    }

    private func color(for kind: AgentStep.Kind) -> Color {
        switch kind {
        case .tool: .orange
        case .reasoning: .blue
        case .error: .red
        }
    }
}

struct ReadingRoomComposer: View {
    @ObservedObject var store: ReadingRoomStore
    var compact = false

    var body: some View {
        HStack(spacing: 10) {
            TextField("问我关于股票的任何问题...", text: $store.draft, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...(compact ? 3 : 4))
                .onSubmit { store.send() }
                .disabled(store.isRunning)
            Button {
                store.send()
            } label: {
                Image(systemName: "paperplane.fill")
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.borderedProminent)
            .disabled(store.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.isRunning)
            .help("发送")
        }
        .padding(compact ? 10 : 14)
    }
}
