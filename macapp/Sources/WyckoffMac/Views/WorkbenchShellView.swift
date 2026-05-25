import SwiftUI

struct WorkbenchShellView: View {
    var section: AppSection
    var assistantVisible: Bool
    @ObservedObject var store: ReadingRoomStore
    var onPrompt: (String) -> Void

    var body: some View {
        HSplitView {
            WorkspaceDetailView(section: section, store: store, onPrompt: onPrompt)
                .frame(minWidth: 0, maxWidth: .infinity)
            if assistantVisible && section != .readingRoom {
                AssistantRailView(store: store)
                    .frame(width: MacTheme.assistantWidth)
            }
        }
        .background(MacTheme.background)
    }
}

private struct WorkspaceDetailView: View {
    var section: AppSection
    @ObservedObject var store: ReadingRoomStore
    var onPrompt: (String) -> Void

    var body: some View {
        switch section {
        case .readingRoom:
            ReadingRoomView(store: store)
        default:
            FeatureWorkspaceView(section: section, onPrompt: onPrompt)
        }
    }
}
