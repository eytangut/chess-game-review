from __future__ import annotations

import io
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import chess
import chess.pgn

from .ai import BaseNarrativeProvider
from .config import AppConfig
from .opening import OpeningDB

CLOCK_RE = re.compile(r"%clk\s+(\d+):(\d+):(\d+)")


@dataclass(frozen=True)
class MoveAnalysis:
    ply: int
    san: str
    uci: str
    player: str
    classification: str
    cp_loss: int
    eval_before: int
    eval_after: int
    best_move: str | None
    top_alternatives: list[dict[str, Any]]
    win_probability: float


def _material_eval(board: chess.Board) -> int:
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }
    score = 0
    for piece_type, value in values.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value
    return score


def _win_probability(eval_cp: int) -> float:
    return 100.0 / (1.0 + math.exp(-eval_cp / 180.0))


def _classify(cp_loss: int, in_book: bool, forced: bool, missed_win: bool) -> str:
    if in_book:
        return "Book"
    if forced:
        return "Forced"
    if missed_win:
        return "Missed Win"
    if cp_loss <= 5:
        return "Best"
    if cp_loss <= 15:
        return "Excellent"
    if cp_loss <= 25:
        return "Good"
    if cp_loss <= 50:
        return "Inaccuracy"
    if cp_loss <= 100:
        return "Mistake"
    return "Blunder"


def _top_moves(board: chess.Board, limit: int = 3) -> list[tuple[chess.Move, int]]:
    scored: list[tuple[chess.Move, int]] = []
    mover = board.turn
    for move in board.legal_moves:
        board.push(move)
        score = _material_eval(board)
        board.pop()
        scored.append((move, score))
    scored.sort(key=lambda item: item[1], reverse=mover == chess.WHITE)
    return scored[:limit]


def _extract_clock(node: chess.pgn.GameNode) -> int | None:
    if not node.comment:
        return None
    match = CLOCK_RE.search(node.comment)
    if not match:
        return None
    hh, mm, ss = [int(part) for part in match.groups()]
    return hh * 3600 + mm * 60 + ss


def parse_games(pgn_text: str) -> list[chess.pgn.Game]:
    stream = io.StringIO(pgn_text)
    games: list[chess.pgn.Game] = []
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        games.append(game)
    return games


def _phase_for_ply(board: chess.Board, ply: int) -> str:
    pieces = len(board.piece_map())
    if pieces <= 10:
        return "endgame"
    if ply <= 24:
        return "opening"
    return "middlegame"


def _format_metadata(game: chess.pgn.Game) -> dict[str, str]:
    tags = game.headers
    return {
        "event": tags.get("Event", "?"),
        "site": tags.get("Site", "?"),
        "date": tags.get("Date", "?"),
        "white": tags.get("White", "?"),
        "black": tags.get("Black", "?"),
        "result": tags.get("Result", "*"),
        "white_elo": tags.get("WhiteElo", "?"),
        "black_elo": tags.get("BlackElo", "?"),
        "time_control": tags.get("TimeControl", "?"),
    }


def analyze_game(
    game: chess.pgn.Game,
    config: AppConfig,
    opening_db: OpeningDB,
    narrative_provider: BaseNarrativeProvider,
) -> dict[str, Any]:
    board = game.board()
    moves: list[MoveAnalysis] = []
    uci_history: list[str] = []
    by_player_cpl: dict[str, list[int]] = defaultdict(list)
    phase_cpl: dict[str, list[int]] = defaultdict(list)
    eval_series: list[int] = [_material_eval(board)]
    critical: list[dict[str, Any]] = []
    cls_counts = {"White": defaultdict(int), "Black": defaultdict(int)}

    prev_clock = {"White": None, "Black": None}
    time_spent = {"White": [], "Black": []}

    for ply, move in enumerate(game.mainline_moves(), start=1):
        player = "White" if board.turn == chess.WHITE else "Black"
        if config.analyze_color.lower() in {"white", "black"} and player.lower() != config.analyze_color.lower():
            board.push(move)
            eval_series.append(_material_eval(board))
            uci_history.append(move.uci())
            continue

        legal_count = board.legal_moves.count()
        phase = _phase_for_ply(board, ply)
        before_eval = _material_eval(board)
        top = _top_moves(board, 3)
        best_move = top[0][0] if top else None
        best_eval = top[0][1] if top else before_eval

        san = board.san(move)
        uci = move.uci()
        board.push(move)
        after_eval = _material_eval(board)
        uci_history.append(uci)

        if player == "Black":
            cp_loss = max(0, after_eval - best_eval)
            delta = before_eval - after_eval
            mover_eval_before = -before_eval
        else:
            cp_loss = max(0, best_eval - after_eval)
            delta = after_eval - before_eval
            mover_eval_before = before_eval

        entry, in_book_len = opening_db.match(uci_history)
        in_book = in_book_len >= len(uci_history)
        missed_win = mover_eval_before >= 300 and (after_eval if player == "White" else -after_eval) < 100
        forced = legal_count == 1
        classification = _classify(cp_loss, in_book, forced, missed_win)

        complexity = max(0.7, min(1.3, legal_count / 20.0))
        weighted_cpl = int(cp_loss * complexity)
        by_player_cpl[player].append(weighted_cpl)
        phase_cpl[phase].append(weighted_cpl)
        cls_counts[player][classification] += 1

        move_info = MoveAnalysis(
            ply=ply,
            san=san,
            uci=uci,
            player=player,
            classification=classification,
            cp_loss=cp_loss,
            eval_before=before_eval,
            eval_after=after_eval,
            best_move=best_move.uci() if best_move else None,
            top_alternatives=[{"move": m.uci(), "eval": e} for m, e in top],
            win_probability=_win_probability(after_eval),
        )
        moves.append(move_info)
        eval_series.append(after_eval)
        critical.append(
            {
                "ply": ply,
                "swing": abs(delta),
                "played": uci,
                "best": best_move.uci() if best_move else None,
            }
        )

        node = game.next()
        if node:
            clk = _extract_clock(node)
            if clk is not None and prev_clock[player] is not None:
                spent = max(0, prev_clock[player] - clk)
                time_spent[player].append(spent)
            if clk is not None:
                prev_clock[player] = clk

    critical.sort(key=lambda item: item["swing"], reverse=True)
    critical = critical[:5]

    def _accuracy(cpl: list[int]) -> float:
        if not cpl:
            return 100.0
        avg = sum(cpl) / len(cpl)
        return round(max(0.0, 100.0 - avg / 3.0), 2)

    opening_entry, in_book_moves = opening_db.match(uci_history)
    opening = {
        "eco": opening_entry.eco if opening_entry else "",
        "name": opening_entry.name if opening_entry else "Unknown",
        "in_book_moves": in_book_moves,
        "novelty_ply": in_book_moves + 1 if in_book_moves < len(uci_history) else None,
    }

    recurring = []
    for side in ["White", "Black"]:
        blunders = cls_counts[side]["Blunder"]
        if blunders:
            recurring.append(f"{side} blundered {blunders} times")

    summary_payload = {
        "opening": opening,
        "critical_moments": critical,
        "phase_accuracy": {k: _accuracy(v) for k, v in phase_cpl.items()},
        "recurring_patterns": recurring,
        "mistakes": [m.__dict__ for m in moves if m.classification in {"Mistake", "Blunder", "Missed Win"}],
    }
    narrative = narrative_provider.generate(summary_payload)

    return {
        "metadata": _format_metadata(game),
        "config": {
            "analysis_profile": config.analysis_profile,
            "search_depth": config.search_depth,
            "analyze_color": config.analyze_color,
            "external_api_mode": config.external_api_mode,
            "offline_mode": config.offline_mode,
        },
        "opening": opening,
        "moves": [m.__dict__ for m in moves],
        "eval_series": eval_series,
        "critical_moments": critical,
        "player_accuracy": {side: _accuracy(values) for side, values in by_player_cpl.items()},
        "phase_accuracy": {phase: _accuracy(values) for phase, values in phase_cpl.items()},
        "classifications": {
            side: dict(counts) for side, counts in cls_counts.items()
        },
        "time_management": {
            side: {
                "avg_time_per_move": round(sum(vals) / len(vals), 2) if vals else None,
                "time_pressure_moves": sum(1 for v in vals if v < 30),
                "think_long_play_wrong": 0,
            }
            for side, vals in time_spent.items()
        },
        "recurring_patterns": recurring,
        "ai_summary": {
            "narrative": narrative.narrative,
            "tips": narrative.tips,
            "complex_move_notes": narrative.complex_move_notes,
        },
    }
