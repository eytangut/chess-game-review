from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from .ai import create_narrative_provider
from .analysis import analyze_game, parse_games
from .config import AppConfig
from .opening import OpeningDB


def create_app(config: AppConfig | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app_config = config or AppConfig.from_env()
    opening_db = OpeningDB.from_tsv(app_config.opening_db_path)
    narrative_provider = create_narrative_provider(app_config)

    @app.get("/")
    def index() -> str:
        return render_template("index.html", config=app_config)

    @app.post("/api/analyze")
    def analyze() -> tuple[str, int] | tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        pgn_text = payload.get("pgn")
        if not pgn_text:
            return {"error": "Missing 'pgn' in request body"}, 400

        games = parse_games(pgn_text)
        if not games:
            return {"error": "No valid PGN games found"}, 400

        game_index = int(payload.get("game_index", 0))
        if game_index < 0 or game_index >= len(games):
            return {"error": "game_index out of range"}, 400

        result = analyze_game(
            games[game_index],
            config=app_config,
            opening_db=opening_db,
            narrative_provider=narrative_provider,
        )
        return jsonify(result), 200

    return app
