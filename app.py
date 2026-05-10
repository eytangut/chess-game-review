"""Flask chess game review application."""

import os
import json
import uuid
import logging
import traceback

import chess
import chess.pgn

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
    Response,
)

from config import (
    SECRET_KEY,
    STOCKFISH_PATH,
    ANALYSIS_DEPTHS,
    GEMINI_API_KEY,
    MAX_CONTENT_LENGTH,
    MAX_MOVES_TO_ANALYZE,
)
from analysis.pgn_parser import parse_pgn, get_positions_from_game
from analysis.engine import EngineWrapper, win_prob_from_cp
from analysis.move_classifier import classify_move, is_sacrifice, _piece_value
from analysis.opening import OpeningDatabase
from analysis.tactics import analyze_position_tactics, detect_king_in_center
from analysis.phases import detect_phase, get_phase_stats
from analysis.accuracy import move_accuracy, game_accuracy, find_critical_moments, compute_per_player_accuracy
from analysis.time_analysis import time_spent_per_move, detect_time_pressure_moves, detect_think_long_play_wrong, analyze_time_by_phase
from analysis.patterns import detect_recurring_patterns, summarize_game_quality
from analysis.ai_summary import AISummary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Module-level singletons (initialized lazily)
_opening_db = None
_ai_summary = None


def get_opening_db():
    global _opening_db
    if _opening_db is None:
        _opening_db = OpeningDatabase()
    return _opening_db


def get_ai_summary():
    global _ai_summary
    if _ai_summary is None:
        _ai_summary = AISummary(api_key=GEMINI_API_KEY)
    return _ai_summary


# ─────────────────────────── Routes ──────────────────────────────────────────

@app.route("/")
def index():
    """Upload page."""
    recent = session.get("recent_analyses", [])
    ai_available = bool(GEMINI_API_KEY)
    return render_template("index.html", recent=recent, ai_available=ai_available)


@app.route("/upload", methods=["POST"])
def upload():
    """Accept PGN upload and store in session."""
    pgn_text = None

    if "pgn_file" in request.files:
        f = request.files["pgn_file"]
        if f and f.filename:
            try:
                pgn_text = f.read().decode("utf-8", errors="replace")
            except Exception as e:
                flash(f"Error reading file: {e}", "error")
                return redirect(url_for("index"))

    if not pgn_text:
        pgn_text = request.form.get("pgn_text", "").strip()

    if not pgn_text:
        flash("Please provide a PGN file or paste PGN text.", "warning")
        return redirect(url_for("index"))

    session_id = str(uuid.uuid4())
    session["pgn"] = pgn_text
    session["session_id"] = session_id
    session["depth"] = request.form.get("depth", "balanced")
    session["analyze_color"] = request.form.get("color", "both")
    session["use_ai"] = request.form.get("use_ai") == "on"

    return redirect(url_for("analyze"))


@app.route("/analyze")
def analyze():
    """Run full analysis and render the analysis page."""
    pgn_text = session.get("pgn")
    if not pgn_text:
        flash("No PGN found. Please upload a game first.", "warning")
        return redirect(url_for("index"))

    depth_name = session.get("depth", "balanced")
    analyze_color = session.get("analyze_color", "both")
    use_ai = session.get("use_ai", False)

    try:
        result = _run_analysis(
            pgn_text=pgn_text,
            depth_name=depth_name,
            analyze_color=analyze_color,
            use_ai=use_ai,
        )
    except Exception as e:
        logger.error("Analysis failed: %s\n%s", e, traceback.format_exc())
        flash("Analysis failed. Please check your PGN and try again.", "error")
        return redirect(url_for("index"))

    # Store in recent analyses
    recent = session.get("recent_analyses", [])
    metadata = result.get("metadata", {})
    recent.insert(0, {
        "white": metadata.get("white", "?"),
        "black": metadata.get("black", "?"),
        "result": metadata.get("result", "*"),
        "date": metadata.get("date", ""),
        "session_id": session.get("session_id"),
    })
    session["recent_analyses"] = recent[:10]
    session["last_analysis"] = result

    ai_available = bool(GEMINI_API_KEY)
    return render_template("analysis.html", analysis=result, ai_available=ai_available)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """JSON API endpoint for analysis."""
    data = request.get_json(silent=True) or {}
    pgn_text = data.get("pgn", "")
    depth_name = data.get("depth", "balanced")
    analyze_color = data.get("color", "both")
    use_ai = data.get("use_ai", False)

    if not pgn_text:
        return jsonify({"error": "No PGN provided"}), 400

    try:
        result = _run_analysis(
            pgn_text=pgn_text,
            depth_name=depth_name,
            analyze_color=analyze_color,
            use_ai=use_ai,
        )
        return jsonify(result)
    except Exception as e:
        logger.error("API analysis failed: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": "Analysis failed. Check server logs for details."}), 500


@app.route("/api/download_openings")
def api_download_openings():
    """Trigger opening database download."""
    try:
        db = get_opening_db()
        downloaded = db.download_all()
        return jsonify({"status": "ok", "downloaded": downloaded})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/export_pgn/<session_id>")
def api_export_pgn(session_id):
    """Export annotated PGN."""
    analysis = session.get("last_analysis")
    if not analysis:
        return jsonify({"error": "No analysis found"}), 404

    pgn_annotated = _build_annotated_pgn(analysis)
    return Response(
        pgn_annotated,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=game_review_{session_id[:8]}.pgn"},
    )


# ─────────────────────────── Analysis pipeline ───────────────────────────────

def _run_analysis(pgn_text, depth_name="balanced", analyze_color="both", use_ai=False):
    """
    Run the full analysis pipeline on a PGN string.

    Returns a dict with all analysis results.
    """
    depth = ANALYSIS_DEPTHS.get(depth_name, 18)

    # 1. Parse PGN
    games = parse_pgn(pgn_text)
    if not games:
        raise ValueError("No valid games found in PGN.")
    game_data = games[0]  # Analyze first game

    metadata = game_data["metadata"]
    raw_moves = game_data["moves"]
    clock_times = game_data["clock_times"]

    # 2. Reconstruct board positions
    board = chess.Board()
    uci_moves_played = []

    # 3. Match opening
    opening_db = get_opening_db()
    opening_match = None

    # 4. Determine which colors to analyze
    colors_to_analyze = {"white", "black"}
    if analyze_color == "white":
        colors_to_analyze = {"white"}
    elif analyze_color == "black":
        colors_to_analyze = {"black"}

    # 5. Try to start Stockfish engine
    engine = None
    engine_available = False
    try:
        engine = EngineWrapper(depth=depth, stockfish_path=STOCKFISH_PATH)
        engine_available = True
        logger.info("Stockfish engine started at depth %d", depth)
    except RuntimeError as e:
        logger.warning("Engine unavailable: %s — proceeding without engine analysis.", e)

    analyzed_moves = []
    fens = [board.fen()]

    try:
        for i, move_data in enumerate(raw_moves[:MAX_MOVES_TO_ANALYZE]):
            uci = move_data["uci"]
            san = move_data["san"]
            color = move_data["color"]
            ply = move_data["ply"]
            move_number = (ply // 2) + 1

            try:
                move_obj = chess.Move.from_uci(uci)
            except ValueError:
                continue

            if move_obj not in board.legal_moves:
                break

            # Opening match (update after each move)
            uci_moves_played.append(uci)
            current_opening = opening_db.match(uci_moves_played)
            if current_opening:
                opening_match = current_opening

            # Game phase
            phase = detect_phase(board, move_number)

            # Engine analysis (before move)
            cp_before = None
            cp_after = None
            engine_top_move = None
            alternatives = []
            pv_line = []

            if engine_available and color in colors_to_analyze:
                pre_analysis = engine.analyze_position(board, multipv=3)
                if pre_analysis:
                    best = pre_analysis[0]
                    cp_before = best.get("score_cp", 0) or 0
                    engine_top_move = best.get("move_uci")
                    pv_line = best.get("pv", [])
                    alternatives = pre_analysis[1:]

            # Detect sacrifice
            sacrifice = is_sacrifice(board, move_obj)

            # Detect tactics BEFORE move
            tactics_before = analyze_position_tactics(board, move_obj)

            # Play the move
            board.push(move_obj)
            fens.append(board.fen())

            # Engine analysis (after move)
            if engine_available and color in colors_to_analyze:
                post_analysis = engine.analyze_position(board, multipv=1)
                if post_analysis:
                    cp_after = post_analysis[0].get("score_cp", 0) or 0

            # Is this move in book?
            is_book = (
                opening_match is not None and
                i < opening_match.get("moves_matched", 0)
            )

            # Classify the move
            legal_moves_uci = [m.uci() for m in board.legal_moves]
            classification = classify_move(
                cp_before=cp_before,
                cp_after=cp_after,
                color=color,
                is_book=is_book,
                is_sacrifice=sacrifice,
                engine_top_move=engine_top_move,
                played_move=uci,
                legal_moves=None,  # passed after move, pass before for forced detection
            )

            # Accuracy score
            cp_loss = classification.get("cp_loss", 0)
            accuracy = move_accuracy(cp_loss) if not is_book else 100.0

            # Detect king in center tactic
            king_center_w = detect_king_in_center(board, chess.WHITE, move_number)
            king_center_b = detect_king_in_center(board, chess.BLACK, move_number)
            if king_center_w:
                tactics_before.append({
                    "pattern": "king_in_center",
                    "description": "White's king remains in the center.",
                    "severity": "medium",
                })
            if king_center_b:
                tactics_before.append({
                    "pattern": "king_in_center",
                    "description": "Black's king remains in the center.",
                    "severity": "medium",
                })

            # Win probability
            win_prob_before = win_prob_from_cp(cp_before) if cp_before is not None else 0.5
            win_prob_after = win_prob_from_cp(-cp_after) if cp_after is not None else 0.5

            analyzed_moves.append({
                "index": i,
                "ply": ply,
                "move_number": move_number,
                "san": san,
                "uci": uci,
                "color": color,
                "fen_before": fens[i],
                "fen_after": fens[i + 1],
                "phase": phase,
                "is_book": is_book,
                "is_sacrifice": sacrifice,
                "cp_before": cp_before,
                "cp_after": cp_after,
                "cp_loss": cp_loss,
                "accuracy": accuracy,
                "classification": classification.get("classification"),
                "label": classification.get("label"),
                "symbol": classification.get("symbol"),
                "color_class": classification.get("color_class"),
                "engine_top_move": engine_top_move,
                "alternatives": alternatives,
                "pv": pv_line,
                "tactics": tactics_before,
                "win_prob_before": round(win_prob_before, 4),
                "win_prob_after": round(win_prob_after, 4),
                "time_pressure": False,  # updated below
                "think_long_play_wrong": False,
            })

    finally:
        if engine:
            engine.close()

    # 6. Time analysis
    time_stats = {}
    time_pressure_indices = set()
    if clock_times:
        time_spent = time_spent_per_move(clock_times, metadata.get("time_control"))
        time_pressure_indices = set(detect_time_pressure_moves(clock_times))
        think_long_wrong = set(detect_think_long_play_wrong(time_spent, analyzed_moves))

        phase_list = [m["phase"] for m in analyzed_moves]
        time_stats = analyze_time_by_phase(time_spent, phase_list)

        for i, m in enumerate(analyzed_moves):
            m["time_pressure"] = i in time_pressure_indices
            m["think_long_play_wrong"] = i in think_long_wrong
            if i < len(time_spent):
                m["time_spent"] = time_spent[i]
            if i < len(clock_times):
                m["time_remaining"] = clock_times[i]

    # 7. Phase statistics
    phase_stats = get_phase_stats(analyzed_moves)

    # 8. Overall accuracy
    white_accuracy = compute_per_player_accuracy(analyzed_moves, "white")
    black_accuracy = compute_per_player_accuracy(analyzed_moves, "black")

    # 9. Critical moments
    critical_moments = find_critical_moments(analyzed_moves)

    # 10. Recurring patterns
    patterns = detect_recurring_patterns(analyzed_moves)

    # 11. Game quality summary
    quality = summarize_game_quality(analyzed_moves)

    # 12. Opening description
    opening_description = ""
    if opening_match:
        opening_description = opening_db.get_opening_description(opening_match.get("eco", ""))

    # 13. AI Summary (optional)
    ai_summary_result = None
    if use_ai or GEMINI_API_KEY:
        try:
            ai = get_ai_summary()
            ai_summary_result = ai.generate_game_summary({
                "metadata": metadata,
                "moves": analyzed_moves,
                "opening": opening_match,
                "accuracy": {"white": white_accuracy, "black": black_accuracy},
                "patterns": patterns,
                "phase_stats": phase_stats,
                "critical_moments": critical_moments,
            })
        except Exception as e:
            logger.warning("AI summary failed: %s", e)

    return {
        "metadata": metadata,
        "opening": opening_match,
        "opening_description": opening_description,
        "moves": analyzed_moves,
        "fens": fens,
        "phase_stats": phase_stats,
        "accuracy": {
            "white": white_accuracy,
            "black": black_accuracy,
        },
        "critical_moments": critical_moments,
        "patterns": patterns,
        "quality": quality,
        "time_stats": time_stats,
        "engine_available": engine_available,
        "ai_summary": ai_summary_result,
        "depth": depth_name,
        "total_moves": len(analyzed_moves),
    }


def _build_annotated_pgn(analysis):
    """Build an annotated PGN string from analysis results."""
    lines = []
    metadata = analysis.get("metadata", {})

    # PGN headers
    for key, header in [
        ("Event", "event"), ("Site", "site"), ("Date", "date"),
        ("White", "white"), ("Black", "black"), ("Result", "result"),
    ]:
        val = metadata.get(header, "?")
        lines.append(f'[{key} "{val}"]')

    if analysis.get("opening"):
        opening = analysis["opening"]
        lines.append(f'[ECO "{opening.get("eco", "?")}"]')
        name = opening.get("name", "")
        if opening.get("variation"):
            name += f": {opening['variation']}"
        lines.append(f'[Opening "{name}"]')

    lines.append("")

    # Moves
    move_tokens = []
    for m in analysis.get("moves", []):
        move_number = m.get("move_number", 0)
        color = m.get("color", "white")
        san = m.get("san", "")
        symbol = m.get("symbol", "")
        classification = m.get("classification", "")
        cp_loss = m.get("cp_loss", 0)

        if color == "white":
            move_tokens.append(f"{move_number}.")

        move_str = san + symbol
        comment_parts = []

        if classification and classification not in ("book", "good"):
            comment_parts.append(classification.replace("_", " ").title())
        if cp_loss and cp_loss > 0:
            comment_parts.append(f"{cp_loss:.0f} cp loss")

        engine_top = m.get("engine_top_move")
        if engine_top and engine_top != m.get("uci"):
            comment_parts.append(f"Best: {engine_top}")

        if comment_parts:
            move_str += f" {{{'; '.join(comment_parts)}}}"

        move_tokens.append(move_str)

    result = metadata.get("result", "*")
    move_tokens.append(result)

    # Wrap at ~80 chars
    line = ""
    for token in move_tokens:
        if len(line) + len(token) + 1 > 80:
            lines.append(line.strip())
            line = token + " "
        else:
            line += token + " "
    if line.strip():
        lines.append(line.strip())

    return "\n".join(lines)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
