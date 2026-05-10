"""Detect recurring mistake patterns in a game analysis."""

from collections import defaultdict


def detect_recurring_patterns(moves_analysis):
    """
    Detect recurring mistake patterns across a game.

    Args:
        moves_analysis: list of move analysis dicts, each containing:
            - classification: str (blunder, mistake, inaccuracy, etc.)
            - color: "white" | "black"
            - tactics: list of tactic pattern dicts
            - time_pressure: bool
            - cp_before: float (eval before move)
            - move_number: int

    Returns:
        List of pattern description strings.
    """
    patterns = []

    # Separate moves by color
    white_moves = [m for m in moves_analysis if m.get("color") == "white"]
    black_moves = [m for m in moves_analysis if m.get("color") == "black"]

    for color, player_moves in [("White", white_moves), ("Black", black_moves)]:
        color_patterns = _analyze_player_patterns(player_moves, color)
        patterns.extend(color_patterns)

    return patterns


def _analyze_player_patterns(moves, color):
    """Analyze patterns for a single player."""
    patterns = []

    # Count classification types
    classification_counts = defaultdict(int)
    for m in moves:
        cls = m.get("classification", "")
        if cls:
            classification_counts[cls] += 1

    blunders = classification_counts.get("blunder", 0)
    mistakes = classification_counts.get("mistake", 0)
    inaccuracies = classification_counts.get("inaccuracy", 0)

    # Multiple blunders
    if blunders >= 3:
        patterns.append(f"{color}: Made {blunders} blunders — consider slowing down and double-checking tactics.")
    elif blunders >= 2:
        patterns.append(f"{color}: Made {blunders} blunders — review each position more carefully.")

    # Many inaccuracies
    if inaccuracies >= 4:
        patterns.append(f"{color}: {inaccuracies} inaccuracies suggest difficulty finding the best moves consistently.")

    # Hanging pieces repeatedly
    hanging_count = sum(
        1 for m in moves
        if any(t.get("pattern") == "hanging_piece" for t in m.get("tactics", []))
    )
    if hanging_count >= 2:
        patterns.append(f"{color}: Left pieces hanging {hanging_count} times — improve piece safety checks.")

    # Never castled (king in center)
    king_center_moves = [
        m for m in moves
        if any(t.get("pattern") == "king_in_center" for t in m.get("tactics", []))
    ]
    if len(king_center_moves) >= 3:
        patterns.append(f"{color}: King remained in the center for many moves — prioritize castling for king safety.")

    # Missed tactics of the same type
    tactic_miss_counts = defaultdict(int)
    for m in moves:
        for t in m.get("tactics", []):
            pattern = t.get("pattern")
            if pattern and m.get("classification") in ("blunder", "mistake"):
                tactic_miss_counts[pattern] += 1

    for tactic, count in tactic_miss_counts.items():
        if count >= 2:
            tactic_name = tactic.replace("_", " ").title()
            patterns.append(f"{color}: Missed {tactic_name} patterns {count} times — study this tactical theme.")

    # Blunders in time pressure
    time_pressure_blunders = [
        m for m in moves
        if m.get("time_pressure") and m.get("classification") in ("blunder", "mistake")
    ]
    if len(time_pressure_blunders) >= 2:
        patterns.append(
            f"{color}: {len(time_pressure_blunders)} errors under time pressure — "
            f"practice faster time controls to improve clock management."
        )

    # Passed pawn not advanced (repeated)
    passed_not_pushed = 0
    for i, m in enumerate(moves):
        has_passed = any(t.get("pattern") == "passed_pawn" for t in m.get("tactics", []))
        if has_passed and m.get("classification") in ("mistake", "blunder", "inaccuracy"):
            passed_not_pushed += 1

    if passed_not_pushed >= 2:
        patterns.append(f"{color}: Had passed pawns but failed to advance them effectively {passed_not_pushed} times.")

    # Think long, play wrong
    think_long_wrong = [m for m in moves if m.get("think_long_play_wrong", False)]
    if think_long_wrong:
        patterns.append(
            f"{color}: Spent a lot of time thinking but still made errors on {len(think_long_wrong)} move(s) — "
            f"trust your calculation more."
        )

    # Multiple mistakes in opening phase
    opening_mistakes = [
        m for m in moves
        if m.get("phase") == "opening" and m.get("classification") in ("blunder", "mistake")
    ]
    if opening_mistakes:
        patterns.append(
            f"{color}: Made {len(opening_mistakes)} serious error(s) in the opening — "
            f"review opening principles and theory."
        )

    # Endgame conversion problems
    endgame_blunders = [
        m for m in moves
        if m.get("phase") == "endgame" and m.get("classification") in ("blunder", "missed_win")
    ]
    if endgame_blunders:
        patterns.append(
            f"{color}: Struggled in the endgame ({len(endgame_blunders)} critical error(s)) — "
            f"study basic endgame technique."
        )

    return patterns


def summarize_game_quality(moves_analysis):
    """
    Produce a concise game quality summary.

    Returns:
        Dict with overall quality metrics.
    """
    total = len(moves_analysis)
    if total == 0:
        return {"quality": "unknown", "message": "No moves analyzed."}

    blunders = sum(1 for m in moves_analysis if m.get("classification") == "blunder")
    mistakes = sum(1 for m in moves_analysis if m.get("classification") == "mistake")
    inaccuracies = sum(1 for m in moves_analysis if m.get("classification") == "inaccuracy")
    brilliant = sum(1 for m in moves_analysis if m.get("classification") == "brilliant")

    error_rate = (blunders * 3 + mistakes * 2 + inaccuracies) / total

    if error_rate < 0.3:
        quality = "excellent"
    elif error_rate < 0.6:
        quality = "good"
    elif error_rate < 1.0:
        quality = "average"
    elif error_rate < 1.5:
        quality = "below_average"
    else:
        quality = "poor"

    return {
        "quality": quality,
        "blunders": blunders,
        "mistakes": mistakes,
        "inaccuracies": inaccuracies,
        "brilliant_moves": brilliant,
        "total_moves": total,
    }
