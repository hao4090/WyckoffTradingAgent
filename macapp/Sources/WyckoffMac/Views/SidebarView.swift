import SwiftUI

struct SidebarView: View {
    @Binding var selection: AppSection?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            sidebarHeader
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    SidebarSection(title: "工作台", items: Array(AppSection.allCases.prefix(8)), selection: $selection)
                    SidebarSection(title: "系统", items: Array(AppSection.allCases.suffix(2)), selection: $selection)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 18)
            }
            Spacer(minLength: 0)
            sidebarFooter
        }
        .foregroundStyle(MacTheme.foreground)
    }

    private var sidebarHeader: some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 6)
                .fill(LinearGradient(colors: [MacTheme.primary, MacTheme.cyan], startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: 28, height: 28)
                .overlay {
                    Image(systemName: "chart.xyaxis.line")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(.white)
                }
            Text("Wyckoff")
                .font(.title3.weight(.bold))
        }
        .padding(.horizontal, 18)
        .padding(.top, 18)
        .padding(.bottom, 8)
    }

    private var sidebarFooter: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Wyckoff Native")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MacTheme.foreground)
            Text("读盘室逻辑来自 CLI")
                .font(.caption2)
                .foregroundStyle(MacTheme.mutedForeground)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
    }
}

private struct SidebarSection: View {
    var title: String
    var items: [AppSection]
    @Binding var selection: AppSection?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(MacTheme.mutedForeground)
                .padding(.horizontal, 8)
            ForEach(items) { section in
                SidebarButton(section: section, isSelected: selection == section) {
                    selection = section
                }
            }
        }
    }
}

private struct SidebarButton: View {
    var section: AppSection
    var isSelected: Bool
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: section.systemImage)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(isSelected ? .white : MacTheme.mutedForeground)
                    .frame(width: 20)
                VStack(alignment: .leading, spacing: 2) {
                    Text(section.title)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(isSelected ? .white : MacTheme.foreground)
                        .lineLimit(1)
                    Text(section.detail)
                        .font(.system(size: 11))
                        .foregroundStyle(isSelected ? Color.white.opacity(0.82) : MacTheme.mutedForeground)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 10)
            .frame(height: 52)
            .frame(maxWidth: .infinity)
            .background(isSelected ? MacTheme.primary : Color.clear, in: RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }
}
