import unittest

from chess_game_review.config import AppConfig
from chess_game_review.web import create_app


class WebTests(unittest.TestCase):
    def test_analyze_requires_pgn(self) -> None:
        app = create_app(AppConfig())
        client = app.test_client()
        resp = client.post("/api/analyze", json={})
        self.assertEqual(resp.status_code, 400)

    def test_analyze_returns_result(self) -> None:
        app = create_app(AppConfig())
        client = app.test_client()
        pgn = "[Event \"Test\"]\n[White \"W\"]\n[Black \"B\"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *"
        resp = client.post("/api/analyze", json={"pgn": pgn})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("player_accuracy", body)


if __name__ == "__main__":
    unittest.main()
