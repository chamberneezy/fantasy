import SwiftUI

/// A half court in feet (50 wide, 47 deep), basket at the top, drawn into any rect.
/// ESPN's shot spots are feet across (x 0–50) and from the rim (y), so the rim sits at `rimY` from the baseline.
enum CourtGeometry {
    static let width: CGFloat = 50
    static let depth: CGFloat = 47
    static let rimY: CGFloat = 5.25
    static let aspect: CGFloat = width / depth

    /// Court feet → a point in `rect`.
    static func point(x: CGFloat, y: CGFloat, in rect: CGRect) -> CGPoint {
        CGPoint(x: rect.minX + x / width * rect.width, y: rect.minY + y / depth * rect.height)
    }

    /// An ESPN shot (y from the rim) → a point in `rect`.
    static func shot(x: Double, y: Double, in rect: CGRect) -> CGPoint {
        point(x: CGFloat(x), y: CGFloat(y) + rimY, in: rect)
    }
}

/// The court's lines: sideline box, paint, free-throw circle, three-point line, rim, half-court circle.
struct CourtLines: Shape {
    func path(in rect: CGRect) -> Path {
        let unit = rect.width / CourtGeometry.width
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CourtGeometry.point(x: x, y: y, in: rect) }
        var path = Path()
        path.addRect(rect)
        // Paint and free-throw circle.
        path.addRect(CGRect(origin: p(17, 0), size: CGSize(width: 16 * unit, height: 19 * unit)))
        path.addEllipse(in: CGRect(x: p(25, 19).x - 6 * unit, y: p(25, 19).y - 6 * unit, width: 12 * unit, height: 12 * unit))
        // Backboard, rim, restricted area.
        path.move(to: p(22, 4))
        path.addLine(to: p(28, 4))
        let rim = p(25, CourtGeometry.rimY)
        path.addEllipse(in: CGRect(x: rim.x - 0.75 * unit, y: rim.y - 0.75 * unit, width: 1.5 * unit, height: 1.5 * unit))
        path.addArc(center: rim, radius: 4 * unit, startAngle: .degrees(0), endAngle: .degrees(180), clockwise: false)
        // Three-point line: corners straight, then the 23.75 ft arc.
        let corner = CourtGeometry.rimY + sqrt(23.75 * 23.75 - 22 * 22)
        path.move(to: p(3, 0))
        path.addLine(to: p(3, corner))
        let start = Angle(radians: atan2(Double(corner - CourtGeometry.rimY), -22))
        let end = Angle(radians: atan2(Double(corner - CourtGeometry.rimY), 22))
        path.addArc(center: rim, radius: 23.75 * unit, startAngle: start, endAngle: end, clockwise: true)
        path.addLine(to: p(47, 0))
        // Half-court circle.
        let center = p(25, CourtGeometry.depth)
        path.move(to: CGPoint(x: center.x - 6 * unit, y: center.y))
        path.addArc(center: center, radius: 6 * unit, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
        return path
    }
}

/// The court surface in the brand: navy floor, a blue paint, soft white lines.
struct CourtFloor: View {
    var body: some View {
        GeometryReader { geo in
            let rect = CGRect(origin: .zero, size: geo.size)
            let unit = rect.width / CourtGeometry.width
            ZStack {
                LinearGradient(colors: [Color(hex: 0x1D428A), Color(hex: 0x0D1B36)], startPoint: .top, endPoint: .bottom)
                Rectangle()
                    .fill(Theme.blue.opacity(0.22))
                    .frame(width: 16 * unit, height: 19 * unit)
                    .position(x: 25 * unit, y: 9.5 * unit)
                CourtLines().stroke(.white.opacity(0.55), lineWidth: 1.4)
            }
        }
        .aspectRatio(CourtGeometry.aspect, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

/// A player's ESPN photo in a ring; a silhouette while it loads or when there is none.
struct Headshot: View {
    let url: String?
    let size: CGFloat
    var ring: Color = Theme.blue

    var body: some View {
        ZStack {
            Circle().fill(Color(hex: 0x0D1B36))
            AsyncImage(url: url.flatMap(URL.init(string:))) { phase in
                if let image = phase.image {
                    image.resizable().scaledToFill().offset(y: size * 0.06)
                } else {
                    Image(systemName: "person.fill").resizable().scaledToFit().padding(size * 0.22).foregroundStyle(.white.opacity(0.35))
                }
            }
            .frame(width: size, height: size)
            .clipShape(Circle())
        }
        .frame(width: size, height: size)
        .overlay(Circle().stroke(ring, lineWidth: max(2, size * 0.045)))
    }
}

/// Seats on the court, as feet: point guard up top, wings, then the bigs by the rim.
private let seatSpots: [String: CGPoint] = [
    "PG": CGPoint(x: 25, y: 36),
    "SG": CGPoint(x: 41.5, y: 25),
    "SF": CGPoint(x: 8.5, y: 25),
    "PF": CGPoint(x: 12.5, y: 9),
    "C": CGPoint(x: 37.5, y: 9),
]

/// Today's five on a half court; tap a player (photo or name) for his card.
struct CourtView: View {
    let lineup: Lineup
    let open: (String) -> Void

    var body: some View {
        CourtFloor()
            .overlay {
                GeometryReader { geo in
                    let rect = CGRect(origin: .zero, size: geo.size)
                    ForEach(lineup.court) { spot in
                        let feet = seatSpots[spot.slot] ?? CGPoint(x: 25, y: 25)
                        SpotView(spot: spot, size: min(64, rect.width * 0.17), onCourt: true) {
                            if let name = spot.playerName { open(name) }
                        }
                        .position(CourtGeometry.point(x: feet.x, y: feet.y, in: rect))
                    }
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityLabel("Today's starting five on the court")
    }
}

/// One player: photo, short name, tonight's game. The whole block is the tap target.
struct SpotView: View {
    let spot: Spot
    let size: CGFloat
    let onCourt: Bool
    let tap: () -> Void

    var body: some View {
        Button(action: tap) {
            VStack(spacing: 3) {
                ZStack(alignment: .topTrailing) {
                    Headshot(url: spot.headshot, size: size, ring: ring)
                        .opacity(spot.playerName == nil || !spot.plays ? 0.55 : 1)
                    Text(spot.slot)
                        .font(Theme.display(10))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 5).padding(.vertical, 1)
                        .background(Theme.red, in: Capsule())
                        .offset(x: 4, y: -2)
                }
                Text(spot.playerName == nil ? "Empty" : (spot.shortName ?? spot.playerName ?? ""))
                    .font(Theme.display(12.5))
                    .foregroundStyle(onCourt ? .white : Theme.ink)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
                Text(gameText)
                    .font(Theme.ui(10, .medium))
                    .foregroundStyle(onCourt ? .white.opacity(0.75) : Theme.mute)
                    .lineLimit(1)
            }
            .frame(width: size * 1.55)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(spot.playerName == nil)
        .accessibilityLabel("\(spot.slot): \(spot.playerName ?? "empty"), \(gameText)")
    }

    private var ring: Color {
        if let status = spot.status, !status.isEmpty { return Theme.red }
        return spot.plays ? Theme.blue : Theme.mute
    }

    private var gameText: String {
        if let status = spot.status, !status.isEmpty, !spot.plays { return status }
        guard let opp = spot.opp else { return "No game" }
        var text = "\(spot.home == true ? "vs" : "@") \(opp)"
        if let tip = spot.tipUtc, let date = ISO8601DateFormatter().date(from: tip) {
            text += " " + date.formatted(date: .omitted, time: .shortened)
        }
        return text
    }
}

/// Bench and IL under the court, one scrolling row each.
struct BenchRow: View {
    let title: String
    let spots: [Spot]
    let open: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(Theme.display(12)).kerning(1).foregroundStyle(Theme.mute)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 4) {
                    ForEach(spots) { spot in
                        SpotView(spot: spot, size: 46, onCourt: false) {
                            if let name = spot.playerName { open(name) }
                        }
                    }
                }
            }
        }
    }
}
