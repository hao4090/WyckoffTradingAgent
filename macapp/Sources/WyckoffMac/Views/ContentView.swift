import OSLog
import SwiftUI

struct ContentView: View {
    @StateObject private var readingRoom = ReadingRoomStore()
    @State private var selection: AppSection? = .readingRoom
    @State private var sidebarVisible = true
    @State private var assistantVisible = true
    private let logger = Logger(subsystem: "com.youngcan.WyckoffMac", category: "Sidebar")

    var body: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                if sidebarVisible {
                    SidebarView(selection: $selection)
                        .frame(width: MacTheme.sidebarWidth)
                        .background(MacTheme.sidebar)
                    Divider()
                        .overlay(MacTheme.border)
                }
                WorkbenchShellView(
                    section: selection ?? .readingRoom,
                    assistantVisible: effectiveAssistantVisible(proxy.size.width),
                    store: readingRoom,
                    onPrompt: runPrompt
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(MacTheme.background)
        .tint(MacTheme.primary)
        .toolbar {
            ToolbarItemGroup {
                Button {
                    sidebarVisible.toggle()
                } label: {
                    Label(sidebarVisible ? "隐藏导航" : "显示导航", systemImage: "sidebar.left")
                }
                .help(sidebarVisible ? "隐藏左侧导航" : "显示左侧导航")

                Button {
                    selection = .readingRoom
                    readingRoom.newChat()
                } label: {
                    Label("新对话", systemImage: "plus.message")
                }
                Button {
                    assistantVisible.toggle()
                } label: {
                    Label(assistantVisible ? "隐藏读盘室" : "显示读盘室", systemImage: "sidebar.right")
                }
                .help(assistantVisible ? "隐藏右侧读盘室" : "显示右侧读盘室")
            }
        }
        .onChange(of: selection) { newValue in
            logger.info("Selected section: \(newValue?.id ?? "none", privacy: .public)")
        }
        .onReceive(NotificationCenter.default.publisher(for: .newReadingRoomChat)) { _ in
            selection = .readingRoom
            readingRoom.newChat()
        }
    }

    private func runPrompt(_ prompt: String) {
        assistantVisible = true
        readingRoom.send(prompt)
    }

    private func effectiveAssistantVisible(_ windowWidth: CGFloat) -> Bool {
        assistantVisible && windowWidth >= MacTheme.assistantBreakpoint
    }
}
