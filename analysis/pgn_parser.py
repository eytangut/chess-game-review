"""PGN file parser - extracts metadata, moves, and clock annotations."""

import re
import io
import chess
import chess.pgn


def parse_pgn(pgn_source):
    """
    Parse PGN content and return a list of game dicts.

    Args:
        pgn_source: PGN content as a string

    Returns:
        List of game dicts, each with keys:
            - metadata: dict with player info, event, result, etc.
            - moves: list of move dicts {san, uci, ply, color}
            - clock_times: list of remaining times in seconds, or None
    """
    pgn_text = pgn_source if isinstance(pgn_source, str) else pgn_source.decode("utf-8", errors="replace")

    games = []
    pgn_io = io.StringIO(pgn_text)

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        games.append(_extract_game_data(game))

    return games


def _extract_game_data(game):
    """Extract structured data from a python-chess Game object."""
    headers = game.headers

    metadata = {
        "white": headers.get("White", "Unknown"),
        "black": headers.get("Black", "Unknown"),
        "white_elo": _parse_elo(headers.get("WhiteElo", "?")),
        "black_elo": _parse_elo(headers.get("BlackElo", "?")),
        "date": headers.get("Date", "????.??.??"),
        "event": headers.get("Event", "?"),
        "site": headers.get("Site", "?"),
        "result": headers.get("Result", "*"),
        "time_control": headers.get("TimeControl", None),
        "opening": headers.get("Opening", None),
        "eco": headers.get("ECO", None),
    }

    moves = []
    clock_times = []
    has_clock = False

    board = game.board()
    node = game

    for move in game.mainline_moves():
        node = node.next()
        ply = board.ply()
        color = "white" if board.turn == chess.WHITE else "black"

        san = board.san(move)
        uci = move.uci()

        # Extract clock annotation from comment
        comment = node.comment if node else ""
        clock_seconds = _parse_clock_annotation(comment)
        if clock_seconds is not None:
            has_clock = True
        clock_times.append(clock_seconds)

        moves.append({
            "san": san,
            "uci": uci,
            "ply": ply,
            "color": color,
            "comment": comment,
        })

        board.push(move)

    return {
        "metadata": metadata,
        "moves": moves,
        "clock_times": clock_times if has_clock else None,
        "final_fen": board.fen(),
    }


def _parse_elo(elo_str):
    """Parse ELO string to int, returning None if not available."""
    if not elo_str or elo_str in ("?", ""):
        return None
    try:
        val = int(elo_str)
        return val if 0 < val < 4000 else None
    except ValueError:
        return None


def _parse_clock_annotation(comment):
    """
    Extract remaining clock time from a PGN comment.

    Supports formats:
        [%clk 1:30:00]
        [%clk 0:05:30]
    Returns seconds as int, or None if not found.
    """
    if not comment:
        return None
    match = re.search(r"\[%clk\s+(\d+):(\d+):(\d+)\]", comment)
    if match:
        hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return None


def get_positions_from_game(game_data):
    """
    Reconstruct board positions from a parsed game dict.

    Returns list of FEN strings for each position (before each move),
    plus the final position.
    """
    import chess
    board = chess.Board()
    fens = [board.fen()]

    for move_data in game_data["moves"]:
        move = chess.Move.from_uci(move_data["uci"])
        if move in board.legal_moves:
            board.push(move)
            fens.append(board.fen())
        else:
            break

    return fens
