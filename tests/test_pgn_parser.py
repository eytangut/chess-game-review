"""Tests for PGN parsing functionality."""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analysis.pgn_parser import parse_pgn, _parse_clock_annotation, _parse_elo


SAMPLE_PGN = """[Event "Test Game"]
[Site "Chess.com"]
[Date "2024.01.15"]
[White "Alice"]
[Black "Bob"]
[WhiteElo "1500"]
[BlackElo "1450"]
[Result "1-0"]
[TimeControl "600+5"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 1-0
"""

SAMPLE_PGN_WITH_CLOCK = """[Event "Blitz"]
[Site "Lichess"]
[Date "2024.01.20"]
[White "Player1"]
[Black "Player2"]
[Result "0-1"]
[TimeControl "300+3"]

1. e4 { [%clk 0:05:00] } e5 { [%clk 0:05:00] } 2. Nf3 { [%clk 0:04:55] } Nc6 { [%clk 0:04:57] } 0-1
"""

MULTI_GAME_PGN = """[Event "Game 1"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0

[Event "Game 2"]
[White "C"]
[Black "D"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""


class TestPgnParser(unittest.TestCase):

    def test_parse_basic_pgn(self):
        """Test that a basic PGN is parsed correctly."""
        games = parse_pgn(SAMPLE_PGN)
        self.assertIsInstance(games, list)
        self.assertEqual(len(games), 1)

    def test_metadata_extraction(self):
        """Test that metadata is extracted from PGN headers."""
        games = parse_pgn(SAMPLE_PGN)
        meta = games[0]["metadata"]

        self.assertEqual(meta["white"], "Alice")
        self.assertEqual(meta["black"], "Bob")
        self.assertEqual(meta["result"], "1-0")
        self.assertEqual(meta["event"], "Test Game")
        self.assertEqual(meta["date"], "2024.01.15")
        self.assertEqual(meta["white_elo"], 1500)
        self.assertEqual(meta["black_elo"], 1450)
        self.assertEqual(meta["time_control"], "600+5")

    def test_moves_extraction(self):
        """Test that moves are extracted correctly."""
        games = parse_pgn(SAMPLE_PGN)
        moves = games[0]["moves"]

        self.assertGreater(len(moves), 0)

        # First move should be e4 by white
        first_move = moves[0]
        self.assertEqual(first_move["san"], "e4")
        self.assertEqual(first_move["uci"], "e2e4")
        self.assertEqual(first_move["color"], "white")
        self.assertEqual(first_move["ply"], 0)

        # Second move should be e5 by black
        second_move = moves[1]
        self.assertEqual(second_move["san"], "e5")
        self.assertEqual(second_move["color"], "black")

    def test_clock_annotation_parsing(self):
        """Test that clock annotations are extracted from PGN comments."""
        games = parse_pgn(SAMPLE_PGN_WITH_CLOCK)
        clock_times = games[0]["clock_times"]

        self.assertIsNotNone(clock_times)
        self.assertEqual(clock_times[0], 300)  # 0:05:00
        self.assertEqual(clock_times[1], 300)  # 0:05:00
        self.assertEqual(clock_times[2], 295)  # 0:04:55
        self.assertEqual(clock_times[3], 297)  # 0:04:57

    def test_no_clock_returns_none(self):
        """Test that games without clock annotations return None for clock_times."""
        games = parse_pgn(SAMPLE_PGN)
        self.assertIsNone(games[0]["clock_times"])

    def test_multi_game_pgn(self):
        """Test parsing a PGN file with multiple games."""
        games = parse_pgn(MULTI_GAME_PGN)
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0]["metadata"]["white"], "A")
        self.assertEqual(games[1]["metadata"]["white"], "C")
        self.assertEqual(games[0]["metadata"]["result"], "1-0")
        self.assertEqual(games[1]["metadata"]["result"], "0-1")

    def test_parse_clock_annotation_function(self):
        """Test the clock annotation parser directly."""
        self.assertEqual(_parse_clock_annotation("{ [%clk 1:30:00] }"), 5400)
        self.assertEqual(_parse_clock_annotation("{ [%clk 0:05:30] }"), 330)
        self.assertEqual(_parse_clock_annotation("{ [%clk 0:00:05] }"), 5)
        self.assertIsNone(_parse_clock_annotation("{ no clock here }"))
        self.assertIsNone(_parse_clock_annotation(None))
        self.assertIsNone(_parse_clock_annotation(""))

    def test_parse_elo(self):
        """Test ELO parsing."""
        self.assertEqual(_parse_elo("1500"), 1500)
        self.assertEqual(_parse_elo("2800"), 2800)
        self.assertIsNone(_parse_elo("?"))
        self.assertIsNone(_parse_elo(""))
        self.assertIsNone(_parse_elo(None))
        self.assertIsNone(_parse_elo("0"))
        self.assertIsNone(_parse_elo("9999"))

    def test_uci_moves_valid(self):
        """Test that all extracted UCI moves are valid format."""
        games = parse_pgn(SAMPLE_PGN)
        moves = games[0]["moves"]
        for move in moves:
            self.assertIn("uci", move)
            uci = move["uci"]
            # UCI moves are 4-5 characters (e.g., e2e4, e7e8q)
            self.assertGreaterEqual(len(uci), 4)
            self.assertLessEqual(len(uci), 5)

    def test_final_fen_is_present(self):
        """Test that final_fen is included in parsed game."""
        games = parse_pgn(SAMPLE_PGN)
        self.assertIn("final_fen", games[0])
        fen = games[0]["final_fen"]
        self.assertIsInstance(fen, str)
        self.assertGreater(len(fen), 10)

    def test_move_numbers_correct(self):
        """Test that ply numbers increase correctly."""
        games = parse_pgn(SAMPLE_PGN)
        moves = games[0]["moves"]
        for i, move in enumerate(moves):
            self.assertEqual(move["ply"], i)


if __name__ == "__main__":
    unittest.main()
