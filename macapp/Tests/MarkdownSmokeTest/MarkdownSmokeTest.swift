import Foundation
import WyckoffMacCore

@main
struct MarkdownSmokeTest {
    static func main() throws {
        try assertAttributedMarkdown()
        try assertBlocks(
            MarkdownBlock.parse("""
            **结论**：继续观察。

            ```json
            {"symbol":"600519"}
            ```
            """)
        )
        try assertTable(
            MarkdownBlock.parse("""
            | 项目 | 结果 |
            | --- | --- |
            | 趋势 | WATCH |
            """)
        )
        try assertHeadingsAndLists(
            MarkdownBlock.parse("""
            ## 小结
            - **量能**收缩
            - 等待突破
            1. 看趋势
            2. 看风险
            """)
        )
        print("Markdown smoke test passed")
    }

    private static func assertAttributedMarkdown() throws {
        let attributed = try AttributedString(
            markdown: "**结论**：观察 `600519`",
            options: AttributedString.MarkdownParsingOptions(interpretedSyntax: .full)
        )
        try expect(String(attributed.characters) == "结论：观察 600519", "AttributedString markdown parse failed")
    }

    private static func assertBlocks(_ blocks: [MarkdownBlock]) throws {
        try expect(blocks.count == 2, "Expected text and code blocks")
        guard case .text = blocks[0].kind else {
            throw SmokeFailure("First block was not text")
        }
        guard case .code(let language) = blocks[1].kind else {
            throw SmokeFailure("Second block was not code")
        }
        try expect(blocks[0].content.contains("**结论**"), "Text markdown content changed")
        try expect(language == "json", "Code language was not preserved")
        try expect(blocks[1].content == #"{"symbol":"600519"}"#, "Code content changed")
    }

    private static func assertTable(_ blocks: [MarkdownBlock]) throws {
        try expect(blocks.count == 1, "Expected one table block")
        guard case .table = blocks[0].kind else {
            throw SmokeFailure("Block was not table")
        }
        try expect(blocks[0].content.contains("| 趋势 | WATCH |"), "Table rows were not preserved")
    }

    private static func assertHeadingsAndLists(_ blocks: [MarkdownBlock]) throws {
        try expect(blocks.count == 3, "Expected heading, unordered list, and ordered list")
        guard case .heading(let level) = blocks[0].kind else {
            throw SmokeFailure("First block was not heading")
        }
        guard case .unorderedList = blocks[1].kind else {
            throw SmokeFailure("Second block was not unordered list")
        }
        guard case .orderedList = blocks[2].kind else {
            throw SmokeFailure("Third block was not ordered list")
        }
        try expect(level == 2, "Heading level was not preserved")
        try expect(blocks[1].content.contains("**量能**收缩"), "Unordered list markdown changed")
        try expect(blocks[2].content.contains("看风险"), "Ordered list markdown changed")
    }

    private static func expect(_ condition: Bool, _ message: String) throws {
        if !condition {
            throw SmokeFailure(message)
        }
    }
}

private struct SmokeFailure: Error, CustomStringConvertible {
    var description: String

    init(_ description: String) {
        self.description = description
    }
}
