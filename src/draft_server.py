"""Draft page. The stable path is /draft."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from draft_room import SESSION_PATH, DraftSession, build_pool, load_session, save_session
from math_engine import ALL_CATEGORIES

app = Flask(__name__, template_folder=str(SRC / "templates"), static_folder=str(SRC / "static"))
SESSION: dict[str, DraftSession | None] = {"current": None}
POOLS: dict[tuple[str, ...], list[dict]] = {}


def pool_for(punts: list[str]) -> list[dict]:
    key = tuple(punts)
    if key not in POOLS:
        POOLS[key] = build_pool(punts)
    return POOLS[key]


def current_session() -> DraftSession | None:
    if SESSION["current"] is None and SESSION_PATH.exists():
        saved = load_session(pool_for([]))
        if saved is not None and saved.punts:
            saved = load_session(pool_for(saved.punts))
        SESSION["current"] = saved
    return SESSION["current"]


@app.get("/")
def home():
    return render_template("draft.html")


@app.get("/draft")
def draft_page():
    return render_template("draft.html")


@app.get("/draft/api/state")
def draft_state():
    session = current_session()
    if session is None:
        return jsonify({"started": False, "categories": list(ALL_CATEGORIES)})
    return jsonify(session.state())


@app.post("/draft/api/start")
def draft_start():
    body = request.get_json(force=True, silent=True) or {}
    try:
        team_count = int(body.get("team_count", 2))
        draft_slot = int(body["draft_slot"])
        punts = [category for category in body.get("punts") or [] if category]
        session = DraftSession(pool_for(punts), team_count, draft_slot, punts)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc) or "Choose the position you are picking."}), 400
    SESSION["current"] = session
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/pick")
def draft_pick():
    session = current_session()
    if session is None:
        return jsonify({"error": "Choose the position you are picking before the board opens."}), 400
    body = request.get_json(force=True, silent=True) or {}
    try:
        session.pick(str(body.get("player_name", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/queue")
def draft_queue():
    session = current_session()
    if session is None:
        return jsonify({"error": "Choose the position you are picking before the board opens."}), 400
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


@app.post("/draft/api/opponent-pick")
def draft_opponent_pick():
    session = current_session()
    if session is None:
        return jsonify({"error": "No draft is open."}), 400
    if session.on_clock() == session.your_team:
        return jsonify(session.state())
    try:
        session.autopick()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/autopick")
def draft_autopick():
    session = current_session()
    if session is None:
        return jsonify({"error": "No draft is open."}), 400
    try:
        session.autopick()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_session(session)
    return jsonify(session.state())


@app.post("/draft/api/undo")
def draft_undo():
    session = current_session()
    if session is None:
        return jsonify({"error": "No draft is open."}), 400
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
    return jsonify({"started": False, "categories": list(ALL_CATEGORIES)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5340, debug=False)
