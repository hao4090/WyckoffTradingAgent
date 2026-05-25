import SwiftUI

struct AssistantRailView: View {
    @ObservedObject var store: ReadingRoomStore

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Label("读盘室", systemImage: "message")
                    .font(.headline)
                    .foregroundStyle(MacTheme.foreground)
                Spacer()
                if store.isRunning {
                    ProgressView()
                        .controlSize(.small)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            Divider()
            compactMessages
            Divider()
            ReadingRoomComposer(store: store, compact: true)
        }
        .background(MacTheme.background)
    }

    private var compactMessages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    if store.messages.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("动作会在这里执行")
                                .font(.headline)
                                .foregroundStyle(MacTheme.foreground)
                            Text("左侧工作区生成结构化请求，右侧读盘室负责真实工具调用和结论输出。")
                                .font(.caption)
                                .foregroundStyle(MacTheme.mutedForeground)
                        }
                        .padding(14)
                    }
                    ForEach(store.messages.suffix(8)) { message in
                        CompactMessageBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding(12)
            }
            .onChange(of: store.messages) { messages in
                guard let last = messages.last else { return }
                proxy.scrollTo(last.id, anchor: .bottom)
            }
        }
    }
}

private struct CompactMessageBubble: View {
    var message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(message.role == .user ? "你" : "威科夫")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MacTheme.mutedForeground)
            if message.isError || message.role == .user {
                Text(message.content.isEmpty ? " " : message.content)
                    .font(.callout)
                    .foregroundStyle(message.isError ? .red : MacTheme.foreground)
                    .lineLimit(message.role == .user ? 4 : 12)
                    .textSelection(.enabled)
            } else {
                MarkdownContentView(content: message.content.isEmpty ? " " : message.content, compact: true)
            }
            if !message.steps.isEmpty {
                Text("\(message.steps.count) 个工具/推理步骤")
                    .font(.caption2)
                    .foregroundStyle(MacTheme.mutedForeground)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(message.role == .user ? MacTheme.accent : MacTheme.muted, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
    }
}
