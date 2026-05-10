import os

# Stockfish analysis depths
ANALYSIS_DEPTHS = {"fast": 12, "balanced": 18, "deep": 24}

# Stockfish binary path
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")

# Gemini API key (optional - enables AI summaries)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", None)

# Lichess opening TSV files (ECO codes A-E)
LICHESS_OPENING_BASE_URL = (
    "https://raw.githubusercontent.com/lichess-org/chess-openings/master/dist/{letter}.tsv"
)
LICHESS_OPENING_LETTERS = ["a", "b", "c", "d", "e"]

# Local cache directory for openings data
OPENINGS_CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "openings")
OPENING_DESCRIPTIONS_PATH = os.path.join(os.path.dirname(__file__), "data", "opening_descriptions.json")

# Centipawn loss thresholds for move classification
CP_THRESHOLDS = {
    "best": 5,          # 0-5 cp loss → Best
    "excellent": 15,    # 5-15 cp loss → Excellent
    "good": 25,         # 15-25 cp loss → Good
    "inaccuracy": 50,   # 25-50 cp loss → Inaccuracy
    "mistake": 100,     # 50-100 cp loss → Mistake
    # 100+ cp loss → Blunder
}

# Flask secret key for sessions
SECRET_KEY = os.environ.get("SECRET_KEY", "chess-review-dev-secret-key-change-in-production")

# Max PGN upload size in bytes (5 MB)
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

# Maximum number of moves to analyze per game (to limit analysis time)
MAX_MOVES_TO_ANALYZE = 120
