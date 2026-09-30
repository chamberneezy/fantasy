"""Draft mock at /draft. Live-room helper at /helper. They do not share a session."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from draft_room import DEFAULT_BUDGET, HELPER_PATH, LAB_PATH, MAX_BUDGET, MIN_BUDGET, SESSION_PATH, TEAM_COUNT, build_pool
from lab import DEFAULT_RUNS, load_report, run_lab, save_report, scenario
from sidecar import SidecarSession, load_sidecar, save_sidecar
from yahoo_auction import DraftSession, load_session, save_session
from math_engine import ALL_CATEGORIES

app = Flask(__name__, template_folder=str(SRC / "templates"), static_folder=str(SRC / "static"))
SESSION: dict[str, DraftSession | None] = {"current": None}
HELPER: dict[str, SidecarSession | None] = {"current": None}
LAB: dict[str, dict | None] = {"report": None}
POOLS: dict[tuple, list[dict]] = {}


def pool_for(punts: list[str], team_count: int = TEAM_COUNT, budget: int = DEFAULT_BUDGET) -> list[dict]:
    key = (tuple(punts), team_count, budget)
    if key not in POOLS:
        POOLS[key] = build_pool(punts, team_count=team_count, budget=budget)
    return POOLS[key]


def idle_state() -> dict:
    return {"started": False, "categories": list(ALL_CATEGORIES), "team_count": TEAM_COUNT, "budget": DEFAULT_BUDGET}


def current_session() -> DraftSession | None:
    if SESSION["current"] is None and SESSION_PATH.exists():
        import json

        payload = json.loads(SESSION_PATH.read_text())
        if payload.get("mode") == "live":
            return None
        punts = list(payload.get("punts") or [])
        team_count = int(payload.get("team_count") or TEAM_COUNT)
        budget = int(payload.get("budget") or DEFAULT_BUDGET)
        try:
            SESSION["current"] = load_session(pool_for(punts, team_count, budget))
        except (KeyError, TypeError, ValueError):
            SESSION["current"] = None
    return SESSION["current"]


def current_helper() -> SidecarSession | None:
    if HELPER["current"] is None and HELPER_PATH.exists():
        import json

        payload = json.loads(HELPER_PATH.read_text())
        punts = list(payload.get("punts") or [])
        team_count = int(payload.get("team_count") or TEAM_COUNT)
        budget = int(payload.get("budget") or DEFAULT_BUDGET)
        try:
            HELPER["current"] = load_sidecar(pool_for(punts, team_count, budget))
        except (KeyError, TypeError, ValueError):
            HELPER["current"] = None
    return HELPER["current"]


@app.get("/")
def home_page():
    return render_template("index.html")


@app.get("/draft")
def draft_page():
    return render_template("draft.html")


@app.get("/helper")
def helper_page():
    return render_template("helper.html")


@app.get("/lab")
def lab_page():
    return render_template("lab.html")


@app.get("/draft/api/state")
def draft_state():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    return jsonify(session.state())


@app.post("/draft/api/start")
def draft_start():
    body = request.get_json(force=True, silent=True) or {}
    try:
        team_count = int(body.get("team_count", TEAM_COUNT))
        budget = int(body.get("budget", DEFAULT_BUDGET))
        punts = [category for category in body.get("punts") or [] if category]
        session = DraftSession(pool_for(punts, team_count, budget), team_count, int(body["draft_slot"]), punts, budget)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc) or "Choose your nomination order."}), 400
    SESSION["current"] = session
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/nominate")
def draft_nominate():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    try:
        session.nominate(str(body.get("player_name", "")), int(body.get("opening") or 1))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/bid")
def draft_bid():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    try:
        session.bid(int(body.get("amount") or 0))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/queue")
def draft_queue():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get("player_name", ""))
    try:
        if body.get("action") == "remove":
            session.queue_remove(name)
        else:
            session.queue_add(name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/tick")
def draft_tick():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    try:
        session.tick()
    except ValueError:
        pass
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/opponent-pick")
def draft_opponent_pick():
    return draft_tick()


@app.post("/draft/api/undo")
def draft_undo():
    session = current_session()
    if session is None:
        return jsonify(idle_state())
    try:
        session.undo()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/reset")
def draft_reset():
    SESSION["current"] = None
    save_session(None)
    return jsonify(idle_state())


@app.get("/helper/api/state")
def helper_state():
    session = current_helper()
    if session is None:
        return jsonify(idle_state())
    return jsonify(session.state())


@app.post("/helper/api/start")
def helper_start():
    body = request.get_json(force=True, silent=True) or {}
    try:
        team_count = int(body.get("team_count", TEAM_COUNT))
        budget = int(body.get("budget", DEFAULT_BUDGET))
        if budget < MIN_BUDGET or budget > MAX_BUDGET:
            raise ValueError("Draft dollars are $160–$240. That number is your cap, not a payment.")
        punts = [category for category in body.get("punts") or [] if category]
        session = SidecarSession(pool_for(punts, team_count, budget), team_count, punts, budget)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    HELPER["current"] = session
    save_sidecar(session)
    return jsonify(session.state())


@app.post("/helper/api/feed")
def helper_feed():
    session = current_helper()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    try:
        session.feed(str(body.get("line") or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_sidecar(session)
    return jsonify(session.state())


@app.post("/helper/api/pick")
def helper_pick():
    session = current_helper()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    try:
        amount = body.get("amount")
        session.pick(str(body.get("player_name") or ""), None if amount in (None, "") else int(amount))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    save_sidecar(session)
    return jsonify(session.state())


@app.post("/helper/api/close")
def helper_close():
    session = current_helper()
    if session is None:
        return jsonify(idle_state())
    body = request.get_json(force=True, silent=True) or {}
    try:
        amount = body.get("amount")
        session.close(str(body.get("action") or ""), None if amount in (None, "") else int(amount))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    save_sidecar(session)
    return jsonify(session.state())


@app.post("/helper/api/undo")
def helper_undo():
    session = current_helper()
    if session is None:
        return jsonify(idle_state())
    try:
        session.undo()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_sidecar(session)
    return jsonify(session.state())


@app.post("/helper/api/reset")
def helper_reset():
    HELPER["current"] = None
    save_sidecar(None)
    return jsonify(idle_state())


def current_lab() -> dict | None:
    if LAB["report"] is None:
        LAB["report"] = load_report()
    return LAB["report"]


@app.get("/lab/api/report")
def lab_report():
    report = current_lab()
    if report is None:
        return jsonify({"ready": False, "n": 0, "draft_slot": 5, "policy": "stay"})
    return jsonify({**report, "ready": True, "drafts": []})


@app.post("/lab/api/run")
def lab_run():
    body = request.get_json(force=True, silent=True) or {}
    try:
        report = run_lab(
            pool_for([]),
            n=int(body.get("n") or DEFAULT_RUNS),
            draft_slot=int(body.get("draft_slot") or 5),
            policy=str(body.get("policy") or "stay"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    LAB["report"] = report
    save_report(report)
    return jsonify({**report, "ready": True, "drafts": []})


@app.post("/lab/api/reset")
def lab_reset():
    LAB["report"] = None
    save_report(None)
    return jsonify({"ready": False, "n": 0, "draft_slot": 5, "policy": "stay"})


@app.post("/lab/api/scenario")
def lab_scenario():
    report = current_lab()
    if report is None:
        return jsonify({"error": "Run the lab first."}), 400
    body = request.get_json(force=True, silent=True) or {}
    try:
        card = scenario(
            report,
            str(body.get("player_name") or ""),
            buyer=str(body.get("buyer") or "room"),
            price=None if body.get("price") in (None, "") else int(body.get("price")),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(card)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5340, debug=False)
