"""Game phase detection: opening, middlegame, endgame."""

import chess


def detect_phase(board, move_number):
    """
    Determine the current game phase.

    Args:
        board: chess.Board instance
        move_number: current full move number (1-based)

    Returns:
        "opening" | "middlegame" | "endgame"
    """
    # Early opening by move count
    if move_number <= 6:
        return "opening"

    # Count material on board
    queens_white = len(board.pieces(chess.QUEEN, chess.WHITE))
    queens_black = len(board.pieces(chess.QUEEN, chess.BLACK))
    total_queens = queens_white + queens_black

    # Count minor pieces + rooks
    minor_white = (len(board.pieces(chess.KNIGHT, chess.WHITE)) +
                   len(board.pieces(chess.BISHOP, chess.WHITE)))
    minor_black = (len(board.pieces(chess.KNIGHT, chess.BLACK)) +
                   len(board.pieces(chess.BISHOP, chess.BLACK)))
    rooks_white = len(board.pieces(chess.ROOK, chess.WHITE))
    rooks_black = len(board.pieces(chess.ROOK, chess.BLACK))

    total_minor = minor_white + minor_black
    total_rooks = rooks_white + rooks_black

    # Endgame conditions
    if total_queens == 0:
        return "endgame"

    # One queen each with few minor pieces
    if total_queens <= 2 and total_minor <= 2 and total_rooks <= 2:
        return "endgame"

    # Heavy material loss indicates endgame
    total_heavy = total_queens + total_rooks
    if total_heavy <= 2 and total_minor <= 2:
        return "endgame"

    # Opening: first 12 moves and pieces not fully developed
    if move_number <= 12:
        if _is_development_phase(board):
            return "opening"

    return "middlegame"


def _is_development_phase(board):
    """
    Heuristic: are we still in the development/opening phase?

    Returns True if many pieces are still on their starting squares.
    """
    # Check if many minor pieces are still undeveloped
    undeveloped = 0
    starting_squares = {
        chess.WHITE: {
            chess.KNIGHT: [chess.B1, chess.G1],
            chess.BISHOP: [chess.C1, chess.F1],
        },
        chess.BLACK: {
            chess.KNIGHT: [chess.B8, chess.G8],
            chess.BISHOP: [chess.C8, chess.F8],
        },
    }

    for color in [chess.WHITE, chess.BLACK]:
        for piece_type, squares in starting_squares[color].items():
            for sq in squares:
                piece = board.piece_at(sq)
                if piece and piece.piece_type == piece_type and piece.color == color:
                    undeveloped += 1

    # If 3+ minor pieces are on starting squares, still opening
    return undeveloped >= 3


def calculate_phase_accuracy(moves_with_classifications, phase):
    """
    Calculate accuracy score for a specific game phase.

    Args:
        moves_with_classifications: list of move dicts with 'phase' and 'accuracy' keys
        phase: "opening" | "middlegame" | "endgame"

    Returns:
        Float 0-100, or None if no moves in that phase.
    """
    phase_moves = [
        m for m in moves_with_classifications
        if m.get("phase") == phase and m.get("accuracy") is not None
    ]

    if not phase_moves:
        return None

    accuracies = [m["accuracy"] for m in phase_moves]
    return round(sum(accuracies) / len(accuracies), 1)


def get_phase_stats(moves_analysis):
    """
    Compute per-phase statistics from a list of analyzed moves.

    Args:
        moves_analysis: list of move dicts with 'phase', 'accuracy', 'classification' keys

    Returns:
        Dict with phase → {accuracy, move_count, blunders, mistakes, inaccuracies}
    """
    stats = {
        "opening": {"accuracy": None, "move_count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
        "middlegame": {"accuracy": None, "move_count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
        "endgame": {"accuracy": None, "move_count": 0, "blunders": 0, "mistakes": 0, "inaccuracies": 0},
    }

    for move in moves_analysis:
        phase = move.get("phase", "middlegame")
        if phase not in stats:
            continue

        stats[phase]["move_count"] += 1
        classification = move.get("classification", "")

        if classification == "blunder":
            stats[phase]["blunders"] += 1
        elif classification == "mistake":
            stats[phase]["mistakes"] += 1
        elif classification == "inaccuracy":
            stats[phase]["inaccuracies"] += 1

    # Calculate accuracy per phase
    for phase in stats:
        acc = calculate_phase_accuracy(moves_analysis, phase)
        stats[phase]["accuracy"] = acc

    return stats
