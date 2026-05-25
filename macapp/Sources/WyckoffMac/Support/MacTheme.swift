import SwiftUI

enum MacTheme {
    static let background = Color(red: 1.0, green: 1.0, blue: 1.0)
    static let foreground = Color(red: 0.102, green: 0.102, blue: 0.18)
    static let muted = Color(red: 0.941, green: 0.949, blue: 0.973)
    static let mutedForeground = Color(red: 0.42, green: 0.443, blue: 0.58)
    static let border = Color(red: 0.886, green: 0.898, blue: 0.945)
    static let primary = Color(red: 0.31, green: 0.275, blue: 0.898)
    static let accent = Color(red: 0.933, green: 0.941, blue: 1.0)
    static let sidebar = Color(red: 0.973, green: 0.976, blue: 0.988)
    static let cyan = Color(red: 0.06, green: 0.72, blue: 0.88)

    static let cardRadius: CGFloat = 10
    static let sidebarWidth: CGFloat = 248
    static let assistantWidth: CGFloat = 360
    static let assistantBreakpoint: CGFloat = 1_180
}
