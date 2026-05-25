import AppKit
import SwiftUI

@main
struct WyckoffMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup("Wyckoff") {
            ContentView()
                .frame(minWidth: 1360, minHeight: 760)
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("新读盘室") {
                    NotificationCenter.default.post(name: .newReadingRoomChat, object: nil)
                }
                .keyboardShortcut("n", modifiers: [.command])
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

extension Notification.Name {
    static let newReadingRoomChat = Notification.Name("newReadingRoomChat")
}
