import Foundation

public struct MarkdownBlock: Identifiable {
    public enum Kind {
        case text
        case heading(Int)
        case unorderedList
        case orderedList
        case code(String)
        case table
    }

    public let id = UUID()
    public var kind: Kind
    public var content: String

    public init(kind: Kind, content: String) {
        self.kind = kind
        self.content = content
    }

    public static func parse(_ content: String) -> [MarkdownBlock] {
        var parser = MarkdownBlockParser(content: content)
        return parser.parse()
    }

    public static func isTableSeparator(_ line: String) -> Bool {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.contains("|") else { return false }
        let stripped = trimmed.trimmingCharacters(in: CharacterSet(charactersIn: "|"))
        return stripped.split(separator: "|").allSatisfy { part in
            let chars = part.trimmingCharacters(in: .whitespaces)
            return !chars.isEmpty && chars.allSatisfy { $0 == "-" || $0 == ":" }
        }
    }
}

private struct MarkdownBlockParser {
    var content: String
    var blocks: [MarkdownBlock] = []
    var textLines: [String] = []
    var codeLines: [String] = []
    var codeLanguage = ""
    var inFence = false

    mutating func parse() -> [MarkdownBlock] {
        for line in content.components(separatedBy: .newlines) {
            append(line)
        }
        finish()
        return blocks.isEmpty ? [MarkdownBlock(kind: .text, content: content)] : blocks
    }

    private mutating func append(_ line: String) {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("```") else {
            appendContentLine(line)
            return
        }
        if inFence {
            blocks.append(MarkdownBlock(kind: .code(codeLanguage), content: codeLines.joined(separator: "\n")))
            codeLines.removeAll()
            codeLanguage = ""
            inFence = false
        } else {
            flushText()
            codeLanguage = String(trimmed.dropFirst(3)).trimmingCharacters(in: .whitespacesAndNewlines)
            inFence = true
        }
    }

    private mutating func appendContentLine(_ line: String) {
        if inFence {
            codeLines.append(line)
        } else {
            textLines.append(line)
        }
    }

    private mutating func finish() {
        if inFence {
            blocks.append(MarkdownBlock(kind: .code(codeLanguage), content: codeLines.joined(separator: "\n")))
        } else {
            flushText()
        }
    }

    private mutating func flushText() {
        let text = textLines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            blocks.append(contentsOf: splitTables(in: text))
        }
        textLines.removeAll()
    }

    private func splitTables(in text: String) -> [MarkdownBlock] {
        var splitter = MarkdownTextSplitter(lines: text.components(separatedBy: .newlines))
        return splitter.split()
    }
}

private struct MarkdownTextSplitter {
    var lines: [String]
    var blocks: [MarkdownBlock] = []
    var buffer: [String] = []
    var index = 0

    mutating func split() -> [MarkdownBlock] {
        while index < lines.count {
            if isTableStart {
                appendTable()
            } else if let heading = MarkdownSyntax.heading(in: lines[index]) {
                appendHeading(heading)
            } else if let style = MarkdownSyntax.listStyle(for: lines[index]) {
                appendList(style: style)
            } else {
                buffer.append(lines[index])
                index += 1
            }
        }
        flushBuffer()
        return blocks
    }

    private var isTableStart: Bool {
        index + 1 < lines.count && MarkdownBlock.isTableSeparator(lines[index + 1]) && lines[index].contains("|")
    }

    private mutating func appendTable() {
        flushBuffer()
        var table = [lines[index], lines[index + 1]]
        index += 2
        while index < lines.count, lines[index].contains("|") {
            table.append(lines[index])
            index += 1
        }
        blocks.append(MarkdownBlock(kind: .table, content: table.joined(separator: "\n")))
    }

    private mutating func appendHeading(_ heading: MarkdownHeading) {
        flushBuffer()
        blocks.append(MarkdownBlock(kind: .heading(heading.level), content: heading.text))
        index += 1
    }

    private mutating func appendList(style: MarkdownListStyle) {
        flushBuffer()
        var items: [String] = []
        while index < lines.count, MarkdownSyntax.listStyle(for: lines[index]) == style {
            items.append(MarkdownSyntax.listText(in: lines[index], style: style))
            index += 1
        }
        blocks.append(MarkdownBlock(kind: style.blockKind, content: items.joined(separator: "\n")))
    }

    private mutating func flushBuffer() {
        let body = buffer.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
        if !body.isEmpty {
            blocks.append(MarkdownBlock(kind: .text, content: body))
        }
        buffer.removeAll()
    }
}

private struct MarkdownHeading {
    var level: Int
    var text: String
}

private enum MarkdownListStyle {
    case ordered
    case unordered

    var blockKind: MarkdownBlock.Kind {
        switch self {
        case .ordered: .orderedList
        case .unordered: .unorderedList
        }
    }
}

private enum MarkdownSyntax {
    static func heading(in line: String) -> MarkdownHeading? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        let level = trimmed.prefix { $0 == "#" }.count
        guard (1...6).contains(level), trimmed.dropFirst(level).first == " " else {
            return nil
        }
        return MarkdownHeading(
            level: level,
            text: String(trimmed.dropFirst(level + 1)).trimmingCharacters(in: .whitespaces)
        )
    }

    static func listStyle(for line: String) -> MarkdownListStyle? {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") || trimmed.hasPrefix("+ ") {
            return .unordered
        }
        return orderedPrefixLength(in: trimmed) == nil ? nil : .ordered
    }

    static func listText(in line: String, style: MarkdownListStyle) -> String {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        switch style {
        case .unordered:
            return String(trimmed.dropFirst(2)).trimmingCharacters(in: .whitespaces)
        case .ordered:
            let offset = orderedPrefixLength(in: trimmed) ?? 0
            return String(trimmed.dropFirst(offset)).trimmingCharacters(in: .whitespaces)
        }
    }

    private static func orderedPrefixLength(in text: String) -> Int? {
        let digits = text.prefix { $0.isNumber }.count
        guard digits > 0 else { return nil }
        let dotIndex = text.index(text.startIndex, offsetBy: digits)
        guard dotIndex < text.endIndex, text[dotIndex] == "." else { return nil }
        let spaceIndex = text.index(after: dotIndex)
        guard spaceIndex < text.endIndex, text[spaceIndex] == " " else { return nil }
        return digits + 2
    }
}
