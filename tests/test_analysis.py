import unittest

from chess_game_review.ai import MockNarrativeProvider
from chess_game_review.analysis import analyze_game, parse_games
from chess_game_review.config import AppConfig
from chess_game_review.opening import OpeningDB

PGN = """[Event \"Live Chess\"]
[Site \"Chess.com\"]
[Date \"2026.05.10\"]
[Round \"?\"]
[White \"Alice\"]
[Black \"Bob\"]
[Result \"1-0\"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3 8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 1-0
"""


class AnalysisTests(unittest.TestCase):
    def test_parse_and_analyze_returns_core_sections(self) -> None:
        games = parse_games(PGN)
        self.assertEqual(len(games), 1)
        config = AppConfig()
        result = analyze_game(
            games[0],
            config=config,
            opening_db=OpeningDB.from_tsv(config.opening_db_path),
            narrative_provider=MockNarrativeProvider(),
        )
        self.assertIn("metadata", result)
        self.assertIn("moves", result)
        self.assertIn("critical_moments", result)
        self.assertIn("ai_summary", result)
        self.assertTrue(result["opening"]["name"])


if __name__ == "__main__":
    unittest.main()
