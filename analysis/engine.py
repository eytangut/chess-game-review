"""Stockfish UCI engine wrapper using python-chess."""

import math
import chess
import chess.engine


class EngineWrapper:
    """
    Wraps a Stockfish subprocess via python-chess's UCI interface.

    Usage:
        with EngineWrapper(depth=18) as engine:
            results = engine.analyze_position(board, multipv=3)
    """

    def __init__(self, depth=18, stockfish_path="stockfish"):
        self.depth = depth
        self.stockfish_path = stockfish_path
        self._engine = None
        self._start()

    def _start(self):
        """Launch the Stockfish process."""
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        except (FileNotFoundError, chess.engine.EngineError) as e:
            raise RuntimeError(f"Failed to start Stockfish at '{self.stockfish_path}': {e}") from e

    def analyze_position(self, board, multipv=3):
        """
        Analyze the current board position.

        Args:
            board: chess.Board instance
            multipv: number of alternative moves to return

        Returns:
            List of dicts: {move_uci, score_cp, score_mate, pv, win_prob}
            Sorted best-first from the perspective of the side to move.
        """
        if self._engine is None:
            return []

        limit = chess.engine.Limit(depth=self.depth)
        multipv = min(multipv, len(list(board.legal_moves)))
        if multipv == 0:
            return []

        try:
            infos = self._engine.analyse(board, limit, multipv=multipv)
        except chess.engine.EngineError:
            return []

        results = []
        for info in infos:
            score = info.get("score")
            if score is None:
                continue

            # Scores are always from the perspective of the side to move
            score_pov = score.pov(board.turn)

            cp = None
            mate = None
            if score_pov.is_mate():
                mate = score_pov.mate()
                # Convert mate to a large centipawn value for comparisons
                cp = 30000 if mate > 0 else -30000
            else:
                cp = score_pov.score()
                if cp is not None:
                    cp = max(-1000, min(1000, cp))

            pv = info.get("pv", [])
            pv_uci = [m.uci() for m in pv[:10]]

            first_move = pv[0] if pv else None
            move_uci = first_move.uci() if first_move else None

            results.append({
                "move_uci": move_uci,
                "score_cp": cp,
                "score_mate": mate,
                "pv": pv_uci,
                "win_prob": win_prob_from_cp(cp) if cp is not None else 0.5,
            })

        return results

    def close(self):
        """Terminate the Stockfish process."""
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def win_prob_from_cp(cp):
    """
    Convert centipawn evaluation to win probability (Lichess formula).

    Args:
        cp: centipawn score (positive = good for the side to move)

    Returns:
        Float [0, 1] representing win probability for the side to move.
    """
    if cp is None:
        return 0.5
    # Clamp to avoid extreme values
    cp = max(-1000, min(1000, cp))
    return 1.0 / (1.0 + math.exp(-0.00368208 * cp))


def cp_from_score(score, color):
    """
    Get centipawn score from a chess.engine.Score, normalized for `color`.

    Positive means good for `color`.
    """
    if score is None:
        return 0
    pov = score.pov(color)
    if pov.is_mate():
        return 30000 if pov.mate() > 0 else -30000
    val = pov.score()
    return max(-1000, min(1000, val)) if val is not None else 0
