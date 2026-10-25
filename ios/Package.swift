// swift-tools-version: 6.0
// NBA Fantasy for iOS. Built on Linux with xtool / omarchy-apple-dev, see README.md.
import PackageDescription

let package = Package(
    name: "NBAFantasy",
    platforms: [.iOS(.v17)],
    products: [
        // xtool: exactly one library product = the app
        .library(name: "NBAFantasy", targets: ["NBAFantasy"]),
    ],
    targets: [
        .target(
            name: "NBAFantasy",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
