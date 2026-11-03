import CoreText
import SwiftUI
import UIKit

/// The NBA Fantasy look from the web pad (src/static/helper.css): colours, Oswald + Outfit, the mark.
enum Theme {
    // Brand colours, the same in both themes.
    static let blue = Color(hex: 0x2B77E7)
    static let red = Color(hex: 0xE73F2B)
    static let gold = Color(hex: 0xF4C542)

    // Page tokens: light first, then the dark theme's values.
    static let page = dynamic(light: 0xF6F8FC, dark: 0x070D1A)
    static let paper = dynamic(light: 0xFFFFFF, dark: 0x0D1B36)
    static let ink = dynamic(light: 0x0B1B33, dark: 0xEEF3FF)
    static let mute = dynamic(light: 0x4D5D73, dark: 0x9DB0D0)
    static let heading = dynamic(light: 0x1D428A, dark: 0xFFFFFF)
    static let banner = dynamic(light: 0x1D428A, dark: 0x070D1A)

    /// Headings and numbers that should read like the site's banners.
    static func display(_ size: CGFloat) -> Font { .custom("Oswald-SemiBold", size: size) }

    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        switch weight {
        case .semibold, .bold, .heavy, .black: return .custom("Outfit-SemiBold", size: size)
        case .medium: return .custom("Outfit-Medium", size: size)
        default: return .custom("Outfit-Regular", size: size)
        }
    }

    static let mark: UIImage? = Bundle.module.url(forResource: "mark", withExtension: "png", subdirectory: "Brand")
        .flatMap { UIImage(contentsOfFile: $0.path) }

    /// The bundled fonts live in the package's resource bundle, so they are registered by hand once.
    static func registerFonts() {
        let urls = Bundle.module.urls(forResourcesWithExtension: "ttf", subdirectory: "Fonts") ?? []
        for url in urls {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }

    /// Tab bar and navigation bars in the brand colours.
    static func styleBars() {
        let nav = UINavigationBarAppearance()
        nav.configureWithOpaqueBackground()
        nav.backgroundColor = UIColor(banner)
        nav.shadowColor = .clear
        let title = UIFont(name: "Oswald-SemiBold", size: 18) ?? .boldSystemFont(ofSize: 18)
        nav.titleTextAttributes = [.foregroundColor: UIColor.white, .font: title, .kern: 1.2]
        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().scrollEdgeAppearance = nav
        UINavigationBar.appearance().compactAppearance = nav
        UINavigationBar.appearance().tintColor = .white
        let tabs = UITabBarAppearance()
        tabs.configureWithDefaultBackground()
        let label = UIFont(name: "Outfit-Medium", size: 10.5) ?? .systemFont(ofSize: 10.5)
        for item in [tabs.stackedLayoutAppearance, tabs.inlineLayoutAppearance, tabs.compactInlineLayoutAppearance] {
            item.normal.titleTextAttributes = [.font: label]
            item.selected.titleTextAttributes = [.font: label]
        }
        UITabBar.appearance().standardAppearance = tabs
        UITabBar.appearance().scrollEdgeAppearance = tabs
    }

    private static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { traits in UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light) })
    }
}

extension Color {
    init(hex: UInt32) { self.init(UIColor(hex: hex)) }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}

/// The site's header: the mark in its blue→red ring and the NBA FANTASY wordmark.
struct BrandTitle: View {
    var body: some View {
        HStack(spacing: 8) {
            MarkRing(size: 28)
            Text("NBA FANTASY")
                .font(Theme.display(17))
                .kerning(1.4)
                .foregroundStyle(.white)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("NBA Fantasy")
    }
}

struct MarkRing: View {
    let size: CGFloat

    var body: some View {
        ZStack {
            Circle()
                .fill(AngularGradient(colors: [Theme.blue, Theme.red, Theme.blue], center: .center, startAngle: .degrees(200), endAngle: .degrees(560)))
                .shadow(color: Theme.blue.opacity(0.7), radius: size * 0.2)
            if let mark = Theme.mark {
                Image(uiImage: mark)
                    .resizable()
                    .frame(width: size * 0.9, height: size * 0.9)
                    .background(Circle().fill(Color(hex: 0x070D1A)))
                    .clipShape(Circle())
            }
        }
        .frame(width: size, height: size)
    }
}

/// Section headers in the site's style: Oswald, uppercase, tracked, in the heading colour.
struct SectionTitle: View {
    let text: String

    var body: some View {
        Text(text.uppercased())
            .font(Theme.display(13))
            .kerning(1.1)
            .foregroundStyle(Theme.heading)
    }
}

extension View {
    /// A screen on the page colour with the brand bar on top.
    func brandScreen(_ title: String) -> some View {
        self
            .scrollContentBackground(.hidden)
            .background(Theme.page)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) { BrandTitle() }
            }
            .toolbarBackground(Theme.banner, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }

    /// List rows on the paper colour.
    func paperRow() -> some View { listRowBackground(Theme.paper) }
}
