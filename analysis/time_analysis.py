"""Clock annotation parsing and time pressure analysis."""

import re


def parse_clock_times(pgn_game_or_clock_list):
    """
    Parse clock times from a python-chess Game object or a list of times.

    Args:
        pgn_game_or_clock_list: chess.pgn.Game OR list of remaining clock times in seconds

    Returns:
        List of remaining times in seconds per move, or None if no clock data.
    """
    # If it's already a list, return it directly
    if isinstance(pgn_game_or_clock_list, list):
        if all(t is None for t in pgn_game_or_clock_list):
            return None
        return pgn_game_or_clock_list

    # Otherwise, parse from a pgn Game object
    import chess.pgn
    game = pgn_game_or_clock_list
    times = []
    has_clock = False

    for node in game.mainline():
        comment = node.comment or ""
        match = re.search(r"\[%clk\s+(\d+):(\d+):(\d+)\]", comment)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            times.append(h * 3600 + m * 60 + s)
            has_clock = True
        else:
            times.append(None)

    return times if has_clock else None


def time_spent_per_move(clock_times, time_control=None):
    """
    Compute time spent on each move from remaining clock times.

    Args:
        clock_times: list of remaining times in seconds (alternating white/black)
        time_control: time control string like "600+5" or "1800" (optional)

    Returns:
        List of time spent per move in seconds.
        None entries where time data is unavailable.
    """
    if not clock_times:
        return []

    # Parse increment from time control
    increment = 0
    if time_control and "+" in str(time_control):
        parts = str(time_control).split("+")
        try:
            increment = int(parts[1])
        except (ValueError, IndexError):
            increment = 0

    # Parse initial time from time control
    initial_white = None
    initial_black = None
    if time_control:
        tc_str = str(time_control)
        base_part = tc_str.split("+")[0]
        try:
            initial_time = int(base_part)
            initial_white = initial_time
            initial_black = initial_time
        except ValueError:
            pass

    time_spent = []
    # Separate white (even indices 0,2,4,...) and black (odd indices 1,3,5,...) clock times
    white_times = [clock_times[i] for i in range(0, len(clock_times), 2)]
    black_times = [clock_times[i] for i in range(1, len(clock_times), 2)]

    def _spent_for_series(color_times, initial):
        """Compute time-spent list for one player's clock readings."""
        prev = initial
        spent = []
        for current in color_times:
            if current is None or prev is None:
                spent.append(None)
            else:
                spent.append(max(0, prev + increment - current))
            prev = current
        return spent

    white_spent = _spent_for_series(white_times, initial_white)
    black_spent = _spent_for_series(black_times, initial_black)

    # Interleave white and black times back to move order
    result = []
    wi = bi = 0
    for i in range(len(clock_times)):
        if i % 2 == 0:
            result.append(white_spent[wi] if wi < len(white_spent) else None)
            wi += 1
        else:
            result.append(black_spent[bi] if bi < len(black_spent) else None)
            bi += 1

    return result


def detect_time_pressure_moves(time_remaining, threshold=30):
    """
    Identify moves made under time pressure (less than `threshold` seconds remaining).

    Args:
        time_remaining: list of remaining clock times in seconds per move
        threshold: seconds threshold below which it's considered time pressure

    Returns:
        List of 0-based indices of moves played under time pressure.
    """
    if not time_remaining:
        return []

    return [
        i for i, t in enumerate(time_remaining)
        if t is not None and t < threshold
    ]


def detect_think_long_play_wrong(time_spent, classifications, think_threshold=60):
    """
    Find moves where the player thought for a long time but still blundered or made a mistake.

    Args:
        time_spent: list of seconds spent per move
        classifications: list of classification dicts (with 'classification' key)
        think_threshold: seconds of thinking above which it's considered "thinking long"

    Returns:
        List of 0-based indices where player thought long but played poorly.
    """
    if not time_spent or not classifications:
        return []

    result = []
    for i, (time, cls) in enumerate(zip(time_spent, classifications)):
        if time is None or cls is None:
            continue
        classification = cls.get("classification", "")
        if time >= think_threshold and classification in ("blunder", "mistake"):
            result.append(i)

    return result


def analyze_time_by_phase(time_spent, phases):
    """
    Calculate average time spent per move in each game phase.

    Args:
        time_spent: list of seconds spent per move
        phases: list of phase strings per move ("opening", "middlegame", "endgame")

    Returns:
        Dict: phase → {avg_seconds, move_count, total_seconds}
    """
    stats = {
        "opening": {"avg_seconds": None, "move_count": 0, "total_seconds": 0},
        "middlegame": {"avg_seconds": None, "move_count": 0, "total_seconds": 0},
        "endgame": {"avg_seconds": None, "move_count": 0, "total_seconds": 0},
    }

    for time, phase in zip(time_spent, phases):
        if time is None or phase not in stats:
            continue
        stats[phase]["move_count"] += 1
        stats[phase]["total_seconds"] += time

    for phase, data in stats.items():
        if data["move_count"] > 0:
            data["avg_seconds"] = round(data["total_seconds"] / data["move_count"], 1)

    return stats
