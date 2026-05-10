"""Accuracy score computation for chess moves and games."""

import math


def move_accuracy(cp_loss):
    """
    Convert centipawn loss to move accuracy score (0-100).

    Uses the Lichess formula:
        accuracy = 103.1668 * exp(-0.04354 * cp_loss) - 3.1669
    Clamped to [0, 100].

    Args:
        cp_loss: centipawn loss (non-negative float)

    Returns:
        Float accuracy score in [0, 100].
    """
    if cp_loss is None or cp_loss < 0:
        cp_loss = 0

    accuracy = 103.1668 * math.exp(-0.04354 * cp_loss) - 3.1669
    return round(max(0.0, min(100.0, accuracy)), 2)


def game_accuracy(move_accuracies):
    """
    Compute overall game accuracy as a weighted average of move accuracies.

    Moves earlier in the game are weighted slightly less to reflect that
    opening moves (often forced or booked) should not dominate the score.

    Args:
        move_accuracies: list of floats [0, 100]

    Returns:
        Float game accuracy in [0, 100], or None if no moves.
    """
    if not move_accuracies:
        return None

    if len(move_accuracies) == 1:
        return round(move_accuracies[0], 1)

    # Simple harmonic mean weighted approach (Lichess-inspired)
    # Penalizes low-accuracy moves more than arithmetic mean
    total = len(move_accuracies)
    weighted_sum = 0.0
    total_weight = 0.0

    for i, acc in enumerate(move_accuracies):
        # Weight increases with move number (later moves matter more)
        weight = 1.0 + (i / total) * 0.5
        weighted_sum += acc * weight
        total_weight += weight

    result = weighted_sum / total_weight if total_weight > 0 else 0.0
    return round(max(0.0, min(100.0, result)), 1)


def find_critical_moments(moves_with_evals, top_n=5):
    """
    Identify the most critical turning points in a game.

    Critical moments are moves with the largest absolute change in eval
    (either saving or losing the game).

    Args:
        moves_with_evals: list of move dicts, each with:
            - cp_before: eval before move (from moving side's perspective)
            - cp_after: eval after move (from moving side's perspective, negated)
            - index: move index (0-based)
        top_n: number of critical moments to return

    Returns:
        List of move indices (0-based), sorted by significance.
    """
    if not moves_with_evals:
        return []

    swings = []
    for i, move in enumerate(moves_with_evals):
        cp_before = move.get("cp_before")
        cp_after = move.get("cp_after")

        if cp_before is None or cp_after is None:
            continue

        # Eval swing: how much did the position change?
        # cp_after is from opponent's perspective after the move, so negate it
        eval_before = cp_before
        eval_after = -cp_after

        swing = abs(eval_after - eval_before)
        swings.append((swing, i))

    # Sort by largest swing
    swings.sort(key=lambda x: x[0], reverse=True)
    return [idx for _, idx in swings[:top_n]]


def accuracy_to_grade(accuracy):
    """
    Convert numeric accuracy to a letter grade.

    Args:
        accuracy: float 0-100

    Returns:
        String grade: "Excellent", "Good", "Average", "Below Average", "Poor"
    """
    if accuracy is None:
        return "N/A"
    if accuracy >= 90:
        return "Excellent"
    if accuracy >= 75:
        return "Good"
    if accuracy >= 60:
        return "Average"
    if accuracy >= 45:
        return "Below Average"
    return "Poor"


def compute_per_player_accuracy(moves_analysis, color):
    """
    Compute accuracy for a single player (white or black).

    Args:
        moves_analysis: list of move analysis dicts with 'color' and 'accuracy' keys
        color: "white" or "black"

    Returns:
        Float accuracy in [0, 100] or None.
    """
    player_moves = [
        m["accuracy"] for m in moves_analysis
        if m.get("color") == color and m.get("accuracy") is not None
    ]
    return game_accuracy(player_moves)
