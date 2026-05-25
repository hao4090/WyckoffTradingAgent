import Foundation
import OSLog

enum WyckoffCLIError: LocalizedError {
    case launchFailed(String)
    case processFailed(String)

    var errorDescription: String? {
        switch self {
        case .launchFailed(let message):
            "无法启动读盘室：\(message)"
        case .processFailed(let message):
            message.isEmpty ? "读盘室进程异常退出" : message
        }
    }
}

final class WyckoffCLIClient {
    private let repoRoot: URL
    private let logger = Logger(subsystem: "com.youngcan.WyckoffMac", category: "CLI")
    private let lock = NSLock()
    private var process: Process?

    init(repoRoot: URL = RepositoryRoot.resolve()) {
        self.repoRoot = repoRoot
    }

    func cancel() {
        lock.lock()
        let runningProcess = process
        lock.unlock()
        if let runningProcess, runningProcess.isRunning {
            logger.info("Terminating Reading Room process")
            runningProcess.terminate()
        }
    }

    func stream(
        prompt: String,
        history: [ReadingHistoryMessage],
        onEvent: @escaping @MainActor (CLIEvent) -> Void
    ) async throws {
        let process = makeProcess(prompt: prompt, history: history)
        let output = Pipe()
        let errorOutput = Pipe()
        process.standardOutput = output
        process.standardError = errorOutput
        setCurrentProcess(process)
        defer { clearCurrentProcess(process) }

        do {
            try process.run()
        } catch {
            throw WyckoffCLIError.launchFailed(error.localizedDescription)
        }

        logger.info("Started Reading Room process")
        let stderrTask = Task { errorOutput.fileHandleForReading.readDataToEndOfFile() }
        for try await line in output.fileHandleForReading.bytes.lines {
            if Task.isCancelled {
                cancel()
                break
            }
            if let event = CLIEvent.parse(jsonLine: line) {
                await onEvent(event)
            }
        }
        process.waitUntilExit()
        let errorText = String(data: await stderrTask.value, encoding: .utf8) ?? ""
        if process.terminationStatus != 0 && !Task.isCancelled {
            throw WyckoffCLIError.processFailed(errorText.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        logger.info("Reading Room process finished")
    }

    private func makeProcess(prompt: String, history: [ReadingHistoryMessage]) -> Process {
        let process = Process()
        let python = RepositoryRoot.pythonExecutable(in: repoRoot)
        process.executableURL = python
        process.currentDirectoryURL = repoRoot
        process.environment = processEnvironment()
        process.arguments = processArguments(prompt: prompt, history: history)
        return process
    }

    private func processArguments(prompt: String, history: [ReadingHistoryMessage]) -> [String] {
        var arguments = ["-m", "cli", "ask", "--jsonl", "--message", prompt]
        if let historyJSON = encodeHistory(history), !historyJSON.isEmpty {
            arguments.append(contentsOf: ["--history-json", historyJSON])
        }
        return arguments
    }

    private func encodeHistory(_ history: [ReadingHistoryMessage]) -> String? {
        guard !history.isEmpty else {
            return nil
        }
        let encoder = JSONEncoder()
        guard let data = try? encoder.encode(history) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    private func processEnvironment() -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        environment["WYCKOFF_REPO_ROOT"] = repoRoot.path
        return environment
    }

    private func setCurrentProcess(_ process: Process) {
        lock.lock()
        self.process = process
        lock.unlock()
    }

    private func clearCurrentProcess(_ process: Process) {
        lock.lock()
        if self.process === process {
            self.process = nil
        }
        lock.unlock()
    }
}
