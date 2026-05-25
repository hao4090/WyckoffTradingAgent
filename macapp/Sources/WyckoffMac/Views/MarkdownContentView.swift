import SwiftUI
import WyckoffMacCore

struct MarkdownContentView: View {
    var content: String
    var compact = false

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 6 : 10) {
            ForEach(MarkdownBlock.parse(content)) { block in
                switch block.kind {
                case .text:
                    MarkdownText(text: block.content)
                case .heading(let level):
                    MarkdownHeadingText(text: block.content, level: level)
                case .unorderedList:
                    MarkdownListView(content: block.content, ordered: false)
                case .orderedList:
                    MarkdownListView(content: block.content, ordered: true)
                case .code(let language):
                    MarkdownCodeBlock(code: block.content, language: language)
                case .table:
                    MarkdownTableView(lines: block.content.components(separatedBy: .newlines))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct MarkdownText: View {
    var text: String

    var body: some View {
        if let attributed = try? AttributedString(
            markdown: text,
            options: AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        ) {
            Text(attributed)
                .textSelection(.enabled)
                .foregroundStyle(MacTheme.foreground)
                .lineSpacing(3)
        } else {
            Text(text)
                .textSelection(.enabled)
                .foregroundStyle(MacTheme.foreground)
                .lineSpacing(3)
        }
    }
}

private struct MarkdownHeadingText: View {
    var text: String
    var level: Int

    var body: some View {
        MarkdownText(text: text)
            .font(font)
            .padding(.top, level <= 2 ? 2 : 0)
    }

    private var font: Font {
        switch level {
        case 1: .title3.weight(.semibold)
        case 2: .headline.weight(.semibold)
        default: .subheadline.weight(.semibold)
        }
    }
}

private struct MarkdownListView: View {
    var content: String
    var ordered: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                HStack(alignment: .top, spacing: 8) {
                    Text(ordered ? "\(index + 1)." : "•")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(MacTheme.mutedForeground)
                        .frame(width: ordered ? 24 : 14, alignment: .trailing)
                    MarkdownText(text: item)
                }
            }
        }
    }

    private var items: [String] {
        content.components(separatedBy: .newlines).filter { !$0.isEmpty }
    }
}

private struct MarkdownCodeBlock: View {
    var code: String
    var language: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !language.isEmpty {
                Text(language)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(MacTheme.mutedForeground)
            }
            ScrollView(.horizontal) {
                Text(code)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(MacTheme.foreground)
                    .textSelection(.enabled)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(MacTheme.background, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
            .overlay {
                RoundedRectangle(cornerRadius: MacTheme.cardRadius)
                    .stroke(MacTheme.border)
            }
        }
    }
}

private struct MarkdownTableView: View {
    var lines: [String]

    var body: some View {
        ScrollView(.horizontal) {
            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    GridRow {
                        ForEach(row, id: \.self) { cell in
                            Text(cell)
                                .font(index == 0 ? .caption.weight(.semibold) : .caption)
                                .foregroundStyle(index == 0 ? MacTheme.foreground : MacTheme.mutedForeground)
                                .textSelection(.enabled)
                        }
                    }
                }
            }
            .padding(10)
        }
        .background(MacTheme.background, in: RoundedRectangle(cornerRadius: MacTheme.cardRadius))
        .overlay {
            RoundedRectangle(cornerRadius: MacTheme.cardRadius)
                .stroke(MacTheme.border)
        }
    }

    private var rows: [[String]] {
        lines
            .filter { !MarkdownBlock.isTableSeparator($0) }
            .map { line in
                line.trimmingCharacters(in: CharacterSet(charactersIn: "|"))
                    .split(separator: "|", omittingEmptySubsequences: false)
                    .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            }
            .filter { !$0.isEmpty }
    }
}
