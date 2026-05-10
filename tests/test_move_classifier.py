"""Tests for move classification logic."""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analysis.move_classifier import classify_move, is_sacrifice, _piece_value
import chess


class TestMoveClassifier(unittest.TestCase):

    def _classify(self, cp_before, cp_after, **kwargs):
        """Helper to classify a move."""
        defaults = dict(
            color="white",
            is_book=False,
            is_sacrifice=False,
            engine_top_move="e2e4",
            played_move="e2e4",
            legal_moves=None,
        )
        defaults.update(kwargs)
        return classify_move(cp_before, cp_after, **defaults)

    def test_book_move(self):
        """Book moves should be classified as 'book' regardless of cp loss."""
        result = classify_move(0, 50, "white", is_book=True)
        self.assertEqual(result["classification"], "book")
        self.assertEqual(result["label"], "Book")

    def test_best_move_same_as_engine(self):
        """A move matching engine top with minimal loss is 'best'."""
        result = self._classify(cp_before=50, cp_after=-48,
                                engine_top_move="e2e4", played_move="e2e4")
        self.assertIn(result["classification"], ("best", "excellent"))

    def test_excellent_move(self):
        """5-15 cp loss should be excellent."""
        # cp_loss = cp_before - (-cp_after) = 50 - 40 = 10
        result = self._classify(cp_before=50, cp_after=-40,
                                engine_top_move="e2e4", played_move="d2d4")
        self.assertEqual(result["classification"], "excellent")

    def test_good_move(self):
        """15-25 cp loss should be good."""
        # cp_loss = 50 - 30 = 20
        result = self._classify(cp_before=50, cp_after=-30,
                                engine_top_move="e2e4", played_move="d2d4")
        self.assertEqual(result["classification"], "good")

    def test_inaccuracy(self):
        """25-50 cp loss should be inaccuracy."""
        # cp_loss = 50 - 10 = 40
        result = self._classify(cp_before=50, cp_after=-10,
                                engine_top_move="e2e4", played_move="d2d4")
        self.assertEqual(result["classification"], "inaccuracy")

    def test_mistake(self):
        """50-100 cp loss should be mistake."""
        # cp_loss = 100 - 30 = 70
        result = self._classify(cp_before=100, cp_after=-30,
                                engine_top_move="e2e4", played_move="d2d4")
        self.assertEqual(result["classification"], "mistake")

    def test_blunder(self):
        """100+ cp loss should be blunder."""
        # cp_loss = 200 - (-50) = 250
        result = self._classify(cp_before=200, cp_after=50,
                                engine_top_move="e2e4", played_move="d2d4")
        self.assertEqual(result["classification"], "blunder")

    def test_missed_win(self):
        """Dropping from +300 to below +100 should be 'missed_win'."""
        # Was +350 (cp_before=350), now opponent has +50 after our move (cp_after=50)
        result = self._classify(cp_before=350, cp_after=50)
        self.assertEqual(result["classification"], "missed_win")

    def test_forced_move_single_legal(self):
        """When there's only one legal move, it should be 'forced'."""
        result = classify_move(
            cp_before=0, cp_after=0,
            color="white",
            is_book=False,
            is_sacrifice=False,
            engine_top_move="e1g1",
            played_move="e1g1",
            legal_moves=["e1g1"],  # Only one legal move
        )
        self.assertEqual(result["classification"], "forced")

    def test_cp_loss_is_non_negative(self):
        """cp_loss should always be non-negative."""
        # Move that improves position
        result = self._classify(cp_before=0, cp_after=-50)
        self.assertGreaterEqual(result["cp_loss"], 0)

    def test_none_evals_fallback(self):
        """None cp values should fallback to 'good' without crashing."""
        result = classify_move(None, None, "white")
        self.assertIn("classification", result)
        self.assertIn(result["classification"], list({"book", "brilliant", "best", "excellent", "good",
                                                       "inaccuracy", "mistake", "blunder", "missed_win", "forced"}))

    def test_result_has_required_keys(self):
        """Classification result must have all required keys."""
        result = self._classify(cp_before=50, cp_after=-48)
        required_keys = ["classification", "label", "symbol", "color_class", "cp_loss"]
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_brilliant_detection(self):
        """A sacrifice that maintains the position should be brilliant."""
        result = classify_move(
            cp_before=50, cp_after=-45,
            color="white",
            is_book=False,
            is_sacrifice=True,
            engine_top_move="e2e4",
            played_move="d2d4",  # Different from engine top
        )
        self.assertEqual(result["classification"], "brilliant")

    def test_piece_values(self):
        """Piece values should be correctly defined."""
        self.assertEqual(_piece_value(chess.PAWN), 100)
        self.assertEqual(_piece_value(chess.KNIGHT), 320)
        self.assertEqual(_piece_value(chess.BISHOP), 330)
        self.assertEqual(_piece_value(chess.ROOK), 500)
        self.assertEqual(_piece_value(chess.QUEEN), 900)
        self.assertEqual(_piece_value(chess.KING), 20000)

    def test_is_sacrifice_captures(self):
        """Test is_sacrifice with a board position."""
        board = chess.Board()
        # Set up a position where a piece moves to an attacked square
        # Scholar's mate setup: after 1.e4 e5 2.Qh5 Nc6 3.Bc4
        board.push_san("e4")
        board.push_san("e5")
        board.push_san("Qh5")
        board.push_san("Nc6")
        board.push_san("Bc4")
        board.push_san("Nf6")  # Black plays Nf6 threatening Qh5

        # Qxf7+ would be a sacrifice (queen takes defended pawn)
        move = chess.Move.from_uci("h5f7")
        if move in board.legal_moves:
            result = is_sacrifice(board, move)
            self.assertIsInstance(result, bool)

    def test_classification_symbols(self):
        """Each classification should have a symbol string."""
        from analysis.move_classifier import CLASSIFICATIONS
        for key, (label, symbol, color_class) in CLASSIFICATIONS.items():
            self.assertIsInstance(label, str)
            self.assertIsInstance(symbol, str)
            self.assertIsInstance(color_class, str)


class TestMoveClassifierEdgeCases(unittest.TestCase):

    def test_zero_cp_loss_is_best(self):
        """Exactly 0 cp loss (same move as engine) should be best."""
        result = classify_move(
            cp_before=100, cp_after=-100,
            color="white",
            engine_top_move="e2e4",
            played_move="e2e4",
        )
        self.assertIn(result["classification"], ("best", "excellent"))

    def test_large_positive_position_blunder(self):
        """Blundering from a very winning position."""
        result = classify_move(
            cp_before=800, cp_after=300,
            color="white",
        )
        self.assertIn(result["classification"], ("blunder", "missed_win"))

    def test_losing_position_any_move(self):
        """In a losing position, even a 'bad' move might not be classified as blunder."""
        result = classify_move(
            cp_before=-300, cp_after=-350,
            color="white",
        )
        # cp_loss = -300 - 350 = -650 → clamped to 0 → 'best' range
        self.assertIn(result["classification"], ("best", "excellent", "good"))


if __name__ == "__main__":
    unittest.main()
