"""Gemini AI integration for game narrative summaries."""

import json
import logging

logger = logging.getLogger(__name__)

# Template response used when no API key is configured
MOCK_SUMMARY = {
    "narrative": (
        "This game featured complex strategic play from both sides. "
        "The opening phase was handled reasonably well, with both players "
        "following established principles. As the middlegame developed, "
        "tactical opportunities arose that shaped the course of the game. "
        "The endgame technique ultimately decided the outcome."
    ),
    "tips": [
        "Focus on piece activity and coordination in the middlegame.",
        "Double-check for tactical threats before completing your move.",
        "Study endgame technique to convert advantages more reliably.",
    ],
    "complex_move_explanations": {},
}


class AISummary:
    """
    Generates AI-powered game narrative summaries using the Gemini API.

    When no API key is configured, returns a canned mock response so
    the application remains functional without external dependencies.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key
        self._client = None

        if api_key:
            self._init_client()

    def _init_client(self):
        """Initialize the Gemini generative AI client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel("gemma-3-27b-it")
            logger.info("Gemini AI client initialized successfully.")
        except ImportError:
            logger.warning("google-generativeai package not installed; AI summary disabled.")
            self._client = None
        except Exception as e:
            logger.warning("Failed to initialize Gemini client: %s", e)
            self._client = None

    def generate_game_summary(self, analysis_data):
        """
        Generate a structured game summary using Gemini AI.

        Args:
            analysis_data: dict containing game analysis results, including:
                - metadata: game headers
                - moves: list of move analysis dicts
                - opening: opening match info
                - accuracy: per-player accuracy scores
                - patterns: list of detected patterns
                - phase_stats: statistics per phase

        Returns:
            Dict with keys:
                - narrative: str (3-5 paragraphs)
                - tips: list of 2-3 improvement tips
                - complex_move_explanations: dict of move_index → explanation
        """
        if self._client is None:
            return self._mock_summary(analysis_data)

        try:
            prompt = self._build_prompt(analysis_data)
            response = self._client.generate_content(prompt)
            return self._parse_response(response.text, analysis_data)
        except Exception as e:
            logger.warning("Gemini API call failed: %s", e)
            return self._mock_summary(analysis_data)

    def _build_prompt(self, analysis_data):
        """Build a structured prompt for the Gemini API."""
        metadata = analysis_data.get("metadata", {})
        opening = analysis_data.get("opening", {}) or {}
        accuracy = analysis_data.get("accuracy", {})
        patterns = analysis_data.get("patterns", [])

        # Find notable moves
        moves = analysis_data.get("moves", [])
        blunders = [
            {"move": m.get("san"), "move_number": m.get("move_number"), "color": m.get("color")}
            for m in moves if m.get("classification") == "blunder"
        ][:5]
        brilliants = [
            {"move": m.get("san"), "move_number": m.get("move_number"), "color": m.get("color")}
            for m in moves if m.get("classification") == "brilliant"
        ][:3]
        critical_moments = analysis_data.get("critical_moments", [])

        game_info = {
            "white": metadata.get("white", "White"),
            "black": metadata.get("black", "Black"),
            "white_elo": metadata.get("white_elo"),
            "black_elo": metadata.get("black_elo"),
            "result": metadata.get("result", "*"),
            "opening": opening.get("name", "Unknown Opening"),
            "eco": opening.get("eco", ""),
            "white_accuracy": accuracy.get("white"),
            "black_accuracy": accuracy.get("black"),
            "total_moves": len(moves),
            "blunders": blunders,
            "brilliant_moves": brilliants,
            "patterns": patterns[:5],
        }

        prompt = f"""You are a chess coach providing a game review. Analyze this chess game and provide:

1. A narrative game summary (3-5 paragraphs covering opening choices, middlegame turning points, and endgame)
2. 2-3 specific improvement tips for the losing player (or the lower-accuracy player)
3. Brief explanations for the top 3 most critical moments

Game information:
{json.dumps(game_info, indent=2)}

Respond in this exact JSON format:
{{
  "narrative": "paragraph 1\\n\\nparagraph 2\\n\\nparagraph 3",
  "tips": ["tip 1", "tip 2", "tip 3"],
  "complex_move_explanations": {{
    "move_description": "explanation of what happened and why"
  }}
}}

Keep explanations chess-accurate, educational, and encouraging. Use chess notation where helpful."""

        return prompt

    def _parse_response(self, response_text, analysis_data):
        """Parse the Gemini API response into a structured dict."""
        # Try to extract JSON from the response
        text = response_text.strip()

        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(text)
            return {
                "narrative": parsed.get("narrative", MOCK_SUMMARY["narrative"]),
                "tips": parsed.get("tips", MOCK_SUMMARY["tips"]),
                "complex_move_explanations": parsed.get("complex_move_explanations", {}),
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini response as JSON, using text as narrative.")
            return {
                "narrative": response_text[:2000],
                "tips": MOCK_SUMMARY["tips"],
                "complex_move_explanations": {},
            }

    def _mock_summary(self, analysis_data):
        """Generate a contextual mock summary without calling the API."""
        metadata = analysis_data.get("metadata", {})
        white = metadata.get("white", "White")
        black = metadata.get("black", "Black")
        result = metadata.get("result", "*")
        opening = analysis_data.get("opening", {}) or {}
        opening_name = opening.get("name", "the chosen opening")

        accuracy = analysis_data.get("accuracy", {})
        white_acc = accuracy.get("white")
        black_acc = accuracy.get("black")

        moves = analysis_data.get("moves", [])
        total_moves = len(moves)

        blunders_w = sum(1 for m in moves if m.get("color") == "white" and m.get("classification") == "blunder")
        blunders_b = sum(1 for m in moves if m.get("color") == "black" and m.get("classification") == "blunder")

        # Determine winner
        if result == "1-0":
            winner, loser = white, black
        elif result == "0-1":
            winner, loser = black, white
        else:
            winner, loser = None, None

        narrative_parts = [
            f"This game between {white} and {black} featured {opening_name} and lasted {total_moves // 2} moves.",
        ]

        if white_acc and black_acc:
            narrative_parts.append(
                f"{white} played with {white_acc:.1f}% accuracy while {black} achieved {black_acc:.1f}% accuracy."
            )

        if blunders_w > 0 or blunders_b > 0:
            narrative_parts.append(
                f"The game saw {blunders_w} blunder(s) by {white} and {blunders_b} blunder(s) by {black}, "
                f"which proved decisive in determining the outcome."
            )

        if winner:
            narrative_parts.append(
                f"{winner} demonstrated superior technique to secure the victory."
            )
        else:
            narrative_parts.append("Both players fought hard and the game ended in a draw.")

        # Build contextual tips
        tips = []
        if blunders_w >= blunders_b and blunders_w > 0:
            tips.append(f"{white}: Review tactical patterns to reduce blunders — consider puzzles daily.")
        if blunders_b >= blunders_w and blunders_b > 0:
            tips.append(f"{black}: Review tactical patterns to reduce blunders — consider puzzles daily.")

        patterns = analysis_data.get("patterns", [])
        if patterns:
            tips.append(patterns[0])

        if not tips:
            tips = MOCK_SUMMARY["tips"]

        return {
            "narrative": "\n\n".join(narrative_parts),
            "tips": tips[:3],
            "complex_move_explanations": {},
            "mock": True,
        }
