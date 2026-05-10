"""Classify chess moves based on centipawn loss and context."""

import chess


# Classification definitions: (label, symbol, css_class)
CLASSIFICATIONS = {
    "book":        ("Book",       "○",  "text-blue-500"),
    "brilliant":   ("Brilliant",  "!!", "text-cyan-400"),
    "best":        ("Best",       "★",  "text-green-500"),
    "excellent":   ("Excellent",  "!",  "text-green-400"),
    "good":        ("Good",       "",   "text-gray-400"),
    "inaccuracy":  ("Inaccuracy", "?!", "text-yellow-400"),
    "mistake":     ("Mistake",    "?",  "text-orange-400"),
    "blunder":     ("Blunder",    "??", "text-red-500"),
    "missed_win":  ("Missed Win", "□",  "text-purple-400"),
    "forced":      ("Forced",     "■",  "text-gray-300"),
}


def classify_move(
    cp_before,
    cp_after,
    color,
    is_book=False,
    is_sacrifice=False,
    engine_top_move=None,
    played_move=None,
    legal_moves=None,
):
    """
    Classify a chess move based on centipawn eval change and context.

    Args:
        cp_before: centipawn eval before the move (from perspective of color)
        cp_after: centipawn eval after the move (from perspective of color)
                  Both should be from the SAME color perspective (positive = good for color)
        color: "white" or "black"
        is_book: whether this move is in the opening book
        is_sacrifice: whether this move involved giving up material
        engine_top_move: UCI string of engine's top recommendation, or None
        played_move: UCI string of move actually played, or None
        legal_moves: list of UCI strings of all legal moves (for forced detection)

    Returns:
        Dict with keys: label, symbol, color_class, cp_loss
    """
    if is_book:
        return _make_result("book", 0)

    # Handle None evals gracefully
    if cp_before is None or cp_after is None:
        return _make_result("good", 0)

    # Centipawn loss is positive = worse for color
    # cp_before and cp_after are from color's perspective
    # After move, the turn flips, so cp_after from engine is opponent's perspective
    # We negate cp_after to get color's perspective
    cp_loss = cp_before - (-cp_after)  # Both normalized to color's POV

    # Clamp cp_loss to reasonable range
    cp_loss = max(0, cp_loss)

    # Forced move: only one legal move, or only one non-losing move
    if legal_moves is not None and len(legal_moves) == 1:
        return _make_result("forced", cp_loss)

    # Missed win: position was strongly winning but dropped significantly
    if cp_before >= 300 and (-cp_after) < 100:
        return _make_result("missed_win", cp_loss)

    # Brilliant: sacrifice involved, move is NOT top engine move, but position significantly improved
    if is_sacrifice and engine_top_move and played_move and played_move != engine_top_move:
        # Brilliant if we maintain or slightly improve position despite not being top move
        if cp_loss <= 30 and cp_before >= -50:
            return _make_result("brilliant", cp_loss)

    # Standard threshold-based classification
    if cp_loss <= 5:
        classification = "best"
        # Downgrade to excellent if not the engine's top move
        if engine_top_move and played_move and played_move != engine_top_move:
            classification = "excellent"
            if cp_loss <= 2:
                classification = "best"
    elif cp_loss <= 15:
        classification = "excellent"
    elif cp_loss <= 25:
        classification = "good"
    elif cp_loss <= 50:
        classification = "inaccuracy"
    elif cp_loss <= 100:
        classification = "mistake"
    else:
        classification = "blunder"

    return _make_result(classification, cp_loss)


def _make_result(classification, cp_loss):
    """Build the result dict for a classification."""
    label, symbol, color_class = CLASSIFICATIONS.get(
        classification, ("Unknown", "", "text-gray-400")
    )
    return {
        "classification": classification,
        "label": label,
        "symbol": symbol,
        "color_class": color_class,
        "cp_loss": round(cp_loss, 1),
    }


def is_sacrifice(board_before, move):
    """
    Detect if a move involves sacrificing material.

    A sacrifice is defined as capturing with a piece of equal or greater value
    while the captured piece is defended, or moving to an attacked square
    without adequate compensation.

    Args:
        board_before: chess.Board before the move
        move: chess.Move being played

    Returns:
        bool
    """
    board = board_before.copy()

    # Check if the move captures a piece
    captured_piece = board.piece_at(move.to_square)
    moving_piece = board.piece_at(move.from_square)

    if moving_piece is None:
        return False

    to_square = move.to_square

    # Is the destination square attacked by opponent after the move?
    board.push(move)
    opponent_color = not moving_piece.color
    is_attacked_after = board.is_attacked_by(opponent_color, to_square)
    board.pop()

    if not captured_piece and is_attacked_after:
        # Moving into an attacked square without capture = potential sacrifice
        piece_value = _piece_value(moving_piece.piece_type)
        return piece_value >= 300  # Rook, queen, or minor piece

    if captured_piece and is_attacked_after:
        # Capture where the capturing piece can be recaptured
        capturing_value = _piece_value(moving_piece.piece_type)
        captured_value = _piece_value(captured_piece.piece_type)
        # It's a sacrifice if we're giving up more than we gain
        return capturing_value > captured_value + 100

    return False


def _piece_value(piece_type):
    """Return approximate centipawn value of a piece type."""
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }
    return values.get(piece_type, 0)
