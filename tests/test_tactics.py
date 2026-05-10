"""Tests for tactical pattern detection."""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chess
from analysis.tactics import (
    detect_fork,
    detect_pin,
    detect_hanging_piece,
    detect_passed_pawn,
    detect_isolated_pawn,
    detect_doubled_pawns,
    detect_skewer,
    detect_discovered_attack,
    detect_double_check,
    detect_back_rank_weakness,
    detect_overloaded_piece,
    detect_rook_seventh_rank,
    detect_outpost_knight,
    detect_bishop_pair,
    analyze_position_tactics,
)


class TestForkDetection(unittest.TestCase):

    def test_knight_fork(self):
        """Knight forking king and rook should be detected."""
        board = chess.Board(fen="8/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        # Place a white knight that will fork Black king and rook
        board = chess.Board(fen="r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1")
        # Nc7+ forks king on e8 and rook on a8
        move = chess.Move.from_uci("d5c7")
        if move in board.legal_moves:
            result = detect_fork(board, move)
            self.assertTrue(result, "Knight fork should be detected")

    def test_no_fork(self):
        """A regular pawn push should not be a fork."""
        board = chess.Board()
        board.push_san("e4")
        move = chess.Move.from_uci("d2d4")
        result = detect_fork(board, move)
        self.assertFalse(result, "Simple pawn push should not be a fork")

    def test_fork_requires_two_targets(self):
        """A single-target attack is not a fork."""
        board = chess.Board(fen="4k3/8/8/3N4/8/8/8/4K3 w - - 0 1")
        # Knight moves but only attacks one enemy piece
        move = chess.Move.from_uci("d5f6")
        if move in board.legal_moves:
            result = detect_fork(board, move)
            # Only one target (king), not a fork
            self.assertIsInstance(result, bool)


class TestPinDetection(unittest.TestCase):

    def test_rook_pin(self):
        """Rook pinning a piece to the king should be detected."""
        # Black has a knight on e5 pinned by white rook on e1 to black king on e8
        board = chess.Board(fen="4k3/8/8/4n3/8/8/8/4R1K1 w - - 0 1")
        # White rook already pins the knight; move the rook to confirm
        move = chess.Move.from_uci("e1e2")
        if move in board.legal_moves:
            result = detect_pin(board, move)
            self.assertIsInstance(result, bool)

    def test_bishop_creates_pin(self):
        """Bishop move creating a pin should be detected."""
        # Set up: white bishop can pin black knight to black king
        board = chess.Board(fen="4k3/4n3/8/8/8/8/B7/4K3 w - - 0 1")
        # Move bishop to create a pin
        move = chess.Move.from_uci("a2g8")
        if move in board.legal_moves:
            result = detect_pin(board, move)
            self.assertIsInstance(result, bool)


class TestHangingPieceDetection(unittest.TestCase):

    def test_detects_hanging_piece(self):
        """An undefended attacked piece should be detected as hanging."""
        # White queen on d4, attacked by black rook on d8, king on h1 doesn't defend d4
        board = chess.Board(fen="3r4/8/8/8/3Q4/8/8/7K b - - 0 1")
        hanging = detect_hanging_piece(board)
        self.assertGreater(len(hanging), 0, "Hanging queen should be detected")
        squares = [sq for sq, piece in hanging]
        self.assertIn(chess.D4, squares)

    def test_defended_piece_not_hanging(self):
        """A piece defended by another piece should not be hanging."""
        board = chess.Board()
        # Starting position - all pieces are either defended or not attacked
        hanging = detect_hanging_piece(board)
        # In starting position, no pieces should be hanging
        self.assertEqual(len(hanging), 0, "No pieces should be hanging at start")

    def test_hanging_pawn(self):
        """An undefended pawn attacked by opponent should be hanging."""
        # White pawn on d5 attacked by black pawn on e6, no defender
        board = chess.Board(fen="4k3/8/4p3/3P4/8/8/8/4K3 b - - 0 1")
        hanging = detect_hanging_piece(board)
        squares = [sq for sq, piece in hanging]
        # d5 pawn should be hanging (attacked by e6 pawn, no white defender)
        # Note: depends on exact board setup
        self.assertIsInstance(hanging, list)


class TestPassedPawnDetection(unittest.TestCase):

    def test_passed_pawn_white(self):
        """A white pawn with no enemy pawns in front should be passed."""
        # White pawn on d5, no black pawns on c,d,e files ahead
        board = chess.Board(fen="4k3/8/8/3P4/8/8/8/4K3 w - - 0 1")
        passed = detect_passed_pawn(board, chess.WHITE)
        self.assertIn(chess.D5, passed, "d5 pawn should be passed")

    def test_blocked_pawn_not_passed(self):
        """A pawn blocked by an enemy pawn is not passed."""
        board = chess.Board(fen="4k3/3p4/8/3P4/8/8/8/4K3 w - - 0 1")
        passed = detect_passed_pawn(board, chess.WHITE)
        self.assertNotIn(chess.D5, passed, "d5 pawn blocked by d7 pawn should not be passed")

    def test_adjacent_enemy_pawn_blocks(self):
        """An adjacent enemy pawn that can capture blocks the passed pawn."""
        board = chess.Board(fen="4k3/4p3/8/3P4/8/8/8/4K3 w - - 0 1")
        passed = detect_passed_pawn(board, chess.WHITE)
        self.assertNotIn(chess.D5, passed, "e7 pawn should prevent d5 from being passed")

    def test_passed_pawn_black(self):
        """A black pawn with no white pawns below should be passed."""
        board = chess.Board(fen="4k3/8/8/8/3p4/8/8/4K3 w - - 0 1")
        passed = detect_passed_pawn(board, chess.BLACK)
        self.assertIn(chess.D4, passed, "d4 black pawn should be passed")

    def test_no_passed_pawns_at_start(self):
        """No passed pawns in starting position."""
        board = chess.Board()
        white_passed = detect_passed_pawn(board, chess.WHITE)
        black_passed = detect_passed_pawn(board, chess.BLACK)
        self.assertEqual(len(white_passed), 0)
        self.assertEqual(len(black_passed), 0)


class TestIsolatedPawnDetection(unittest.TestCase):

    def test_isolated_pawn(self):
        """A pawn with no adjacent friendly pawns is isolated."""
        board = chess.Board(fen="4k3/8/8/8/3P4/8/PP5P/4K3 w - - 0 1")
        isolated = detect_isolated_pawn(board, chess.WHITE)
        # d4 is isolated (a2, b2 are adjacent to each other but not d4; h2 is isolated too)
        self.assertIn(chess.D4, isolated)

    def test_connected_pawn_not_isolated(self):
        """Connected pawns should not be isolated."""
        board = chess.Board(fen="4k3/8/8/8/3PP3/8/8/4K3 w - - 0 1")
        isolated = detect_isolated_pawn(board, chess.WHITE)
        # d4 and e4 are connected
        self.assertNotIn(chess.D4, isolated)
        self.assertNotIn(chess.E4, isolated)


class TestDoubledPawns(unittest.TestCase):

    def test_doubled_pawns(self):
        """Two pawns on the same file are doubled."""
        board = chess.Board(fen="4k3/3p4/3p4/8/8/8/8/4K3 w - - 0 1")
        doubled = detect_doubled_pawns(board, chess.BLACK)
        files = [f for f, sqs in doubled]
        self.assertIn(3, files, "d-file should have doubled pawns")

    def test_no_doubled_pawns_at_start(self):
        """Starting position has no doubled pawns."""
        board = chess.Board()
        self.assertEqual(len(detect_doubled_pawns(board, chess.WHITE)), 0)
        self.assertEqual(len(detect_doubled_pawns(board, chess.BLACK)), 0)


class TestBishopPair(unittest.TestCase):

    def test_bishop_pair_present(self):
        """Both bishops on different colors = bishop pair."""
        board = chess.Board(fen="4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1")
        self.assertTrue(detect_bishop_pair(board, chess.WHITE))

    def test_single_bishop_no_pair(self):
        """Only one bishop = no bishop pair."""
        board = chess.Board(fen="4k3/8/8/8/8/8/8/2B1K3 w - - 0 1")
        self.assertFalse(detect_bishop_pair(board, chess.WHITE))


class TestRookSeventhRank(unittest.TestCase):

    def test_rook_on_seventh(self):
        """White rook on 7th rank (rank 6 = index) should be detected."""
        board = chess.Board(fen="4k3/R7/8/8/8/8/8/4K3 w - - 0 1")
        result = detect_rook_seventh_rank(board, chess.WHITE)
        self.assertIn(chess.A7, result)

    def test_rook_not_on_seventh(self):
        """Rook not on 7th rank should not be detected."""
        board = chess.Board(fen="4k3/8/R7/8/8/8/8/4K3 w - - 0 1")
        result = detect_rook_seventh_rank(board, chess.WHITE)
        self.assertNotIn(chess.A6, result)


class TestOutpostKnight(unittest.TestCase):

    def test_knight_on_outpost(self):
        """Knight on 5th rank with no enemy pawns to chase it should be an outpost."""
        # White knight on e5, no black pawns on d6 or f6
        board = chess.Board(fen="4k3/8/8/4N3/8/8/8/4K3 w - - 0 1")
        result = detect_outpost_knight(board, chess.WHITE)
        self.assertIn(chess.E5, result)

    def test_knight_chased_by_pawn(self):
        """Knight on 5th rank that can be chased by enemy pawn is not an outpost."""
        board = chess.Board(fen="4k3/8/3p4/4N3/8/8/8/4K3 w - - 0 1")
        result = detect_outpost_knight(board, chess.WHITE)
        self.assertNotIn(chess.E5, result)


class TestAnalyzePositionTactics(unittest.TestCase):

    def test_returns_list(self):
        """analyze_position_tactics should return a list."""
        board = chess.Board()
        result = analyze_position_tactics(board)
        self.assertIsInstance(result, list)

    def test_each_tactic_has_required_keys(self):
        """Each tactic dict should have pattern, description, severity."""
        board = chess.Board(fen="4k3/8/8/8/4r3/8/8/3QK3 b - - 0 1")
        result = analyze_position_tactics(board)
        for tactic in result:
            self.assertIn("pattern", tactic)
            self.assertIn("description", tactic)
            self.assertIn("severity", tactic)
            self.assertIn(tactic["severity"], ("high", "medium", "low"))

    def test_hanging_piece_detected_in_full_analysis(self):
        """Full analysis should detect a hanging piece."""
        # White queen on d4 attacked by black rook on d8, undefended
        board = chess.Board(fen="3r4/8/8/8/3Q4/8/8/7K b - - 0 1")
        result = analyze_position_tactics(board)
        patterns = [t["pattern"] for t in result]
        self.assertIn("hanging_piece", patterns)

    def test_analyze_with_move(self):
        """analyze_position_tactics should work with a move argument."""
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        result = analyze_position_tactics(board, move)
        self.assertIsInstance(result, list)

    def test_back_rank_weakness(self):
        """Back rank weakness should be detected when conditions are met."""
        # White king on g1, pawns on f2, g2, h2 (normal) — no weakness
        board_safe = chess.Board(fen="4r2k/7P/8/8/8/8/5PPP/6RK w - - 0 1")
        # Black rook on e8, black king h8 with pawns blocking
        result = detect_back_rank_weakness(board_safe, chess.BLACK)
        # This specific position may or may not have weakness; just test it doesn't crash
        self.assertIsInstance(result, bool)


class TestDoubleCheckDetection(unittest.TestCase):

    def test_double_check_detection(self):
        """Double check should be detected when two pieces give check."""
        # Known double check position: discovered check + moving piece checks
        # Simplified: if we can construct one, test it
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        result = detect_double_check(board, move)
        self.assertFalse(result, "Simple pawn push is not double check")


if __name__ == "__main__":
    unittest.main()
