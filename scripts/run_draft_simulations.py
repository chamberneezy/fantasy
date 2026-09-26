"""Run 12-team snake mocks for seats 1-12 and write a PDF of your teams.

Your seat always takes the best player by 9-category value. The other eleven
seats follow one of three habits, so the same seat produces different rosters.

  value  Best available every time. One draft per seat is enough.
  games  Among the top eight within 0.75 value of the best, weighted toward
         more predicted games. Twenty drafts per seat.
  reach  About 40% of the time a team with no center takes the best center in
         the top 18, and about 30% of the time a team with no point guard does
         the same for point guards. Otherwise best available. Twenty drafts.
"""

from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from draft_room import SLOTS, build_pool, eligible_for_slot, first_open_slot, snake_order  # noqa: E402

TEAM_COUNT = 12
ROUNDS = 13
GAMES_REPS = 20
REACH_REPS = 20
REPORT = ROOT / "reports" / "draft_simulations.pdf"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _needs(roster: list[dict], label: str) -> bool:
    filled = {player["slot_id"] for player in roster}
    for slot_id, slot_label in SLOTS:
        if slot_id not in filled and slot_label == label:
            return True
    return False


def _choose(available: list[dict], roster: list[dict], policy: str, rng: random.Random) -> dict:
    best = available[0]
    if policy == "value":
        return best
    if policy == "games":
        ceiling = (best["total_value"] or 0) - 0.75
        window = [player for player in available[:8] if (player["total_value"] or 0) >= ceiling]
        weights = [max(1, int(player["predicted_games"] or 1)) for player in window]
        return rng.choices(window, weights=weights, k=1)[0]
    if policy == "reach":
        best_value = best["total_value"] or 0
        if _needs(roster, "C") and rng.random() < 0.40:
            centers = [
                player
                for player in available[:18]
                if "C" in str(player["positions"]).split("/")
                and best_value - (player["total_value"] or 0) <= 2.0
            ]
            if centers and centers[0] is not best:
                return centers[0]
        if _needs(roster, "PG") and rng.random() < 0.30:
            guards = [
                player
                for player in available[:18]
                if "PG" in str(player["positions"]).split("/")
                and best_value - (player["total_value"] or 0) <= 2.0
            ]
            if guards and guards[0] is not best:
                return guards[0]
        return best
    raise ValueError(policy)


def simulate(pool: list[dict], slot: int, policy: str, seed: int) -> dict:
    rng = random.Random(seed)
    you = slot - 1
    remaining = list(pool)
    rosters: list[list[dict]] = [[] for _ in range(TEAM_COUNT)]
    round1 = None
    for team_index in snake_order(TEAM_COUNT, ROUNDS):
        if team_index == you:
            chosen = remaining[0]
        else:
            chosen = _choose(remaining, rosters[team_index], policy, rng)
        remaining.remove(chosen)
        filled = {player["slot_id"] for player in rosters[team_index]}
        try:
            slot_id = first_open_slot(chosen["positions"], filled)
        except ValueError:
            slot_id = next(slot for slot, _label in SLOTS if slot not in filled)
        filed = {
            "slot_id": slot_id,
            "player_name": chosen["player_name"],
            "positions": chosen["positions"],
            "total_value": chosen["total_value"] or 0,
            "predicted_games": chosen["predicted_games"],
            "rookie": chosen["rookie"],
        }
        rosters[team_index].append(filed)
        if team_index == you and round1 is None:
            round1 = chosen["player_name"]
    yours = rosters[you]
    return {
        "slot": slot,
        "policy": policy,
        "round1": round1,
        "value": round(sum(player["total_value"] for player in yours), 2),
        "games": sum(int(player["predicted_games"] or 0) for player in yours),
        "roster": yours,
    }


def _median_roster(drafts: list[dict]) -> dict:
    ordered = sorted(drafts, key=lambda draft: draft["value"])
    target = ordered[len(ordered) // 2]["value"]
    return min(drafts, key=lambda draft: (abs(draft["value"] - target), draft["value"]))


def run_all(pool: list[dict]) -> dict[str, list[dict]]:
    plans = [("value", 1), ("games", GAMES_REPS), ("reach", REACH_REPS)]
    results: dict[str, list[dict]] = {policy: [] for policy, _ in plans}
    for policy, reps in plans:
        for slot in range(1, TEAM_COUNT + 1):
            for rep in range(reps):
                results[policy].append(simulate(pool, slot, policy, seed=slot * 1000 + rep))
    return results


def write_pdf(results: dict[str, list[dict]], path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    pdfmetrics.registerFont(TTFont("Arial", FONT))
    navy = colors.HexColor("#1D428A")
    red = colors.HexColor("#C8102E")
    ink = colors.HexColor("#0C2340")
    sheet = colors.HexColor("#EEF2F6")

    title = ParagraphStyle("title", fontName="Arial", fontSize=16, textColor=navy, leading=20, spaceAfter=8)
    h = ParagraphStyle("h", fontName="Arial", fontSize=12, textColor=navy, leading=15, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Arial", fontSize=9, textColor=ink, leading=12, spaceAfter=6)
    small = ParagraphStyle("small", fontName="Arial", fontSize=8, textColor=ink, leading=10)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0, letter[1] - 28, letter[0], 28, fill=1, stroke=0)
        canvas.setFillColor(red)
        canvas.rect(0, letter[1] - 32, letter[0], 4, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Arial", 9)
        canvas.drawString(36, letter[1] - 18, "Draft room  ·  12-team mock results")
        canvas.setFillColor(ink)
        canvas.setFont("Arial", 8)
        canvas.drawRightString(letter[0] - 36, 22, f"{doc.page}")
        canvas.restoreState()

    story = []
    story.append(Spacer(1, 16))
    story.append(Paragraph("Your teams from seats 1 through 12", title))
    story.append(Paragraph(
        "Each draft is a 12-team snake, 13 rounds, Yahoo roster slots. "
        "Your seat always takes the highest 9-category value still on the board. "
        "The other managers change how they pick. The roster shown for a seat is the one "
        "whose total value sits closest to the middle of that seat's drafts. "
        "Value is the sum of category z-scores. Predicted games are listed beside each name "
        "and do not change the rank.",
        body,
    ))
    story.append(Paragraph("Best available", h))
    story.append(Paragraph(
        "Every other manager takes the highest value. One draft per seat. "
        "This is the roster the live suggestion would build if nobody reaches.",
        body,
    ))
    story.append(Paragraph("Games lean", h))
    story.append(Paragraph(
        "When several players sit within 0.75 value of the best, the other managers "
        "lean toward the one predicted for more games. Twenty drafts per seat. "
        "Your own pick stays on value, so the difference is who is left when you are on the clock.",
        body,
    ))
    story.append(Paragraph("Position reach", h))
    story.append(Paragraph(
        "A manager with an open center slot takes the best center in the top 18 about 40 percent "
        "of the time, when that center is within 2.0 value of the best player. "
        "An open point-guard slot does the same about 30 percent of the time. "
        "Twenty drafts per seat.",
        body,
    ))
    story.append(Paragraph(
        "Read a seat this way: the summary row is the average roster value, the average sum of "
        "predicted games, and how often the same player was your first pick. "
        "The table under it is the middle roster, filed into Yahoo slots.",
        body,
    ))

    labels = dict(SLOTS)
    header = ["Slot", "Player", "Pos", "Value", "Games"]

    for policy, heading in (
        ("value", "Best available"),
        ("games", "Games lean"),
        ("reach", "Position reach"),
    ):
        story.append(PageBreak())
        drafts = results[policy]
        story.append(Paragraph(heading, title))
        summary = [["Seat", "Drafts", "Avg value", "Avg games", "First pick"]]
        for slot in range(1, TEAM_COUNT + 1):
            group = [draft for draft in drafts if draft["slot"] == slot]
            names = Counter(draft["round1"] for draft in group)
            top_name, top_count = names.most_common(1)[0]
            share = f"{top_name} ({top_count}/{len(group)})"
            summary.append([
                str(slot),
                str(len(group)),
                f"{sum(d['value'] for d in group) / len(group):.1f}",
                f"{sum(d['games'] for d in group) / len(group):.0f}",
                share,
            ])
        table = Table(summary, colWidths=[0.6 * inch, 0.7 * inch, 0.9 * inch, 0.9 * inch, 3.6 * inch])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Arial"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, sheet]),
            ("TEXTCOLOR", (0, 1), (-1, -1), ink),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C5CED9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(table)

        for slot in range(1, TEAM_COUNT + 1):
            if slot % 2 == 1:
                story.append(PageBreak())
            group = [draft for draft in drafts if draft["slot"] == slot]
            chosen = _median_roster(group)
            story.append(Paragraph(
                f"Seat {slot}  ·  roster value {chosen['value']:.1f}  ·  "
                f"{chosen['games']} predicted games  ·  first pick {chosen['round1']}",
                h,
            ))
            rows = [header]
            for player in chosen["roster"]:
                games = "" if player["predicted_games"] is None else str(player["predicted_games"])
                name = player["player_name"] + (" (R)" if player["rookie"] else "")
                slot_label = labels.get(player["slot_id"], player["positions"])
                if not eligible_for_slot(player["positions"], slot_label):
                    slot_label = player["positions"]
                rows.append([
                    slot_label,
                    name,
                    player["positions"],
                    f"{player['total_value']:.2f}",
                    games,
                ])
            roster = Table(rows, colWidths=[0.7 * inch, 3.2 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch])
            roster.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Arial"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, sheet]),
                ("TEXTCOLOR", (0, 1), (-1, -1), ink),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C5CED9")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(roster)
            story.append(Paragraph(
                "This is the middle draft for the seat. Your picks were always the best value left.",
                small,
            ))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=48,
        bottomMargin=40,
        title="Draft room mock results",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)


def main() -> None:
    pool = build_pool()
    results = run_all(pool)
    write_pdf(results, REPORT)
    total = sum(len(drafts) for drafts in results.values())
    print(f"pool={len(pool)} drafts={total} pdf={REPORT}")


if __name__ == "__main__":
    main()
