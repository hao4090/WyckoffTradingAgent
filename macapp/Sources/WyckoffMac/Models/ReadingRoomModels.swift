import Foundation

struct ChatMessage: Identifiable, Equatable {
    enum Role: String {
        case user
        case assistant
    }

    let id: UUID
    var role: Role
    var content: String
    var isError: Bool
    var steps: [AgentStep]

    init(
        id: UUID = UUID(),
        role: Role,
        content: String,
        isError: Bool = false,
        steps: [AgentStep] = []
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.isError = isError
        self.steps = steps
    }
}

struct AgentStep: Identifiable, Equatable {
    enum Kind: String {
        case tool
        case reasoning
        case error
    }

    let id: UUID
    var kind: Kind
    var title: String
    var detail: String

    init(id: UUID = UUID(), kind: Kind, title: String, detail: String = "") {
        self.id = id
        self.kind = kind
        self.title = title
        self.detail = detail
    }
}

struct ReadingHistoryMessage: Encodable {
    var role: String
    var content: String
}

struct CLIEvent: Equatable {
    var type: String
    var text: String
    var name: String
    var error: String
    var summary: String

    static func parse(jsonLine: String) -> CLIEvent? {
        guard let data = jsonLine.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }
        return CLIEvent(
            type: stringValue(object["type"]),
            text: stringValue(object["text"]),
            name: stringValue(object["name"]),
            error: stringValue(object["error"]),
            summary: summary(from: object)
        )
    }

    private static func stringValue(_ value: Any?) -> String {
        if let value = value as? String {
            return value
        }
        return ""
    }

    private static func summary(from object: [String: Any]) -> String {
        if let args = object["args"] {
            return compactJSON(args)
        }
        if let result = object["result"] {
            return compactJSON(result)
        }
        return ""
    }

    private static func compactJSON(_ value: Any) -> String {
        guard JSONSerialization.isValidJSONObject(value),
              let data = try? JSONSerialization.data(withJSONObject: value),
              let text = String(data: data, encoding: .utf8)
        else {
            return String(describing: value)
        }
        return text.count > 180 ? String(text.prefix(177)) + "..." : text
    }
}
