import SwiftUI

struct FeatureWorkspaceView: View {
    var section: AppSection
    var onPrompt: (String) -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                WorkspaceHeader(section: section)
                WorkflowContextStrip(section: section)
                NativePanel(section: section, onPrompt: onPrompt)
                QuickPromptDock(section: section, onPrompt: onPrompt)
            }
            .padding(.leading, 28)
            .padding(.trailing, 28)
            .padding(.vertical, 28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(MacTheme.background)
    }
}

private struct WorkspaceHeader: View {
    var section: AppSection

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: section.systemImage)
                .font(.system(size: 22, weight: .semibold))
                .frame(width: 46, height: 46)
                .foregroundStyle(MacTheme.primary)
                .background(MacTheme.accent, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
            VStack(alignment: .leading, spacing: 4) {
                Text(section.title)
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(MacTheme.foreground)
                Text(section.detail)
                    .foregroundStyle(MacTheme.mutedForeground)
            }
            Spacer()
            Label(section.executionLane, systemImage: section.laneIcon)
                .font(.caption.weight(.medium))
                .foregroundStyle(MacTheme.mutedForeground)
                .padding(.horizontal, 9)
                .padding(.vertical, 5)
                .background(MacTheme.muted, in: Capsule())
        }
    }
}

private struct NativePanel: View {
    var section: AppSection
    var onPrompt: (String) -> Void

    var body: some View {
        switch section {
        case .analysis:
            AnalysisPanel(onPrompt: onPrompt)
        case .battle:
            BattlePanel(onPrompt: onPrompt)
        case .portfolio:
            PortfolioPanel(onPrompt: onPrompt)
        case .history:
            HistoryPanel(onPrompt: onPrompt)
        case .tracking:
            TrackingPanel(onPrompt: onPrompt)
        case .tailBuy:
            TailBuyPanel(onPrompt: onPrompt)
        case .export:
            ExportPanel(onPrompt: onPrompt)
        case .settings:
            SettingsPanel(onPrompt: onPrompt)
        case .capabilityMap:
            CapabilityMapPanel(onPrompt: onPrompt)
        case .readingRoom:
            EmptyView()
        }
    }
}

private struct QuickPromptDock: View {
    var section: AppSection
    var onPrompt: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("常用动作")
                .font(.headline)
                .foregroundStyle(MacTheme.foreground)
            FlowLayout(items: section.quickPrompts) { prompt in
                Button {
                    onPrompt(prompt)
                } label: {
                    Label(prompt, systemImage: "arrow.up.right")
                        .lineLimit(2)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(MacTheme.muted, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
    }
}

private struct WorkflowContextStrip: View {
    var section: AppSection

    var body: some View {
        HStack(spacing: 10) {
            ForEach(section.workspaceFacts, id: \.title) { fact in
                VStack(alignment: .leading, spacing: 3) {
                    Label(fact.title, systemImage: fact.icon)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(MacTheme.foreground)
                    Text(fact.value)
                        .font(.caption)
                        .foregroundStyle(MacTheme.mutedForeground)
                        .lineLimit(1)
                }
                .padding(11)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(MacTheme.background, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
                .overlay {
                    RoundedRectangle(cornerRadius: MacTheme.cardRadius)
                        .stroke(MacTheme.border)
                }
            }
        }
    }
}

struct WorkspaceCard<Content: View>: View {
    var title: String
    var subtitle: String = ""
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.headline)
                    .foregroundStyle(MacTheme.foreground)
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(MacTheme.mutedForeground)
                }
            }
            content()
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(MacTheme.background, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
        .overlay {
            RoundedRectangle(cornerRadius: MacTheme.cardRadius)
                .stroke(MacTheme.border)
        }
    }
}
