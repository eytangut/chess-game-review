import os
import unittest

from chess_game_review.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_defaults_are_offline_and_mock(self) -> None:
        config = AppConfig.from_env()
        self.assertTrue(config.offline_mode)
        self.assertTrue(config.use_mock_apis)
        self.assertEqual(config.ai_provider, "mock")

    def test_profile_depth_mapping(self) -> None:
        original = os.environ.get("ANALYSIS_PROFILE")
        os.environ["ANALYSIS_PROFILE"] = "deep"
        try:
            config = AppConfig.from_env()
            self.assertEqual(config.search_depth, 20)
        finally:
            if original is None:
                os.environ.pop("ANALYSIS_PROFILE", None)
            else:
                os.environ["ANALYSIS_PROFILE"] = original


if __name__ == "__main__":
    unittest.main()
