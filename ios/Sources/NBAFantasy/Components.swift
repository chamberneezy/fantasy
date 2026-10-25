import SwiftUI

/// A list section in the site's style: Oswald header, rows on the paper colour, optional footer.
struct BrandSection<Content: View>: View {
    let title: String?
    let footer: String?
    @ViewBuilder let content: () -> Content

    init(_ title: String? = nil, footer: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.footer = footer
        self.content = content
    }

    var body: some View {
        Section {
            content().listRowBackground(Theme.paper)
        } header: {
            if let title { SectionTitle(text: title) }
        } footer: {
            if let footer { Text(footer).font(Theme.ui(12)).foregroundStyle(Theme.mute) }
        }
    }
}

/// A small coloured capsule: lean words, certainty, status.
struct Pill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(Theme.ui(11, .semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.16), in: Capsule())
            .foregroundStyle(color)
    }
}

enum Palette {
    /// Lean words: blue for my side, gold for a coin flip, red for his.
    static func lean(_ word: String) -> Color {
        switch word {
        case "likely yours": return Theme.blue
        case "lean yours": return Theme.blue.opacity(0.75)
        case "coin flip": return Color(hex: 0xC99A0E)
        case "lean his": return Theme.red.opacity(0.8)
        default: return Theme.red
        }
    }

    static func certainty(_ level: String) -> Color {
        switch level {
        case "high": return Theme.blue
        case "medium": return Color(hex: 0xC99A0E)
        default: return Theme.mute
        }
    }

    /// Mine in blue; players I could add in the heading colour; other teams muted.
    static func owner(_ owner: String) -> Color {
        switch owner {
        case "mine": return Theme.blue
        case "free", "unlisted": return Theme.heading
        default: return Theme.mute
        }
    }
}
