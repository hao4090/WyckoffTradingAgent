import Foundation

enum RepositoryRoot {
    static func resolve() -> URL {
        if let explicit = ProcessInfo.processInfo.environment["WYCKOFF_REPO_ROOT"], !explicit.isEmpty {
            return URL(fileURLWithPath: explicit, isDirectory: true)
        }
        let bundleURL = Bundle.main.bundleURL
        if bundleURL.pathExtension == "app" {
            return bundleURL
                .deletingLastPathComponent()
                .deletingLastPathComponent()
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
    }

    static func pythonExecutable(in repoRoot: URL) -> URL {
        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python")
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            return venvPython
        }
        return URL(fileURLWithPath: "/usr/bin/python3")
    }
}
