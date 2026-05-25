import SwiftUI

struct FlowLayout<Content: View>: View {
    var items: [String]
    @ViewBuilder var content: (String) -> Content

    private let columns = [
        GridItem(.adaptive(minimum: 180), spacing: 8, alignment: .leading),
    ]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { item in
                content(item)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}
