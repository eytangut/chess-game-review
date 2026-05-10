"""Lichess opening database matching with local TSV cache."""

import os
import csv
import json
import logging
import requests

logger = logging.getLogger(__name__)

LICHESS_BASE_URL = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/dist/{letter}.tsv"
LICHESS_LETTERS = ["a", "b", "c", "d", "e"]


class OpeningDatabase:
    """
    Matches chess move sequences to named openings using the Lichess ECO database.

    The database is downloaded lazily and cached as TSV files in the data/openings/ directory.
    """

    def __init__(self, cache_dir=None, descriptions_path=None):
        if cache_dir is None:
            base = os.path.dirname(os.path.dirname(__file__))
            cache_dir = os.path.join(base, "data", "openings")
        if descriptions_path is None:
            base = os.path.dirname(os.path.dirname(__file__))
            descriptions_path = os.path.join(base, "data", "opening_descriptions.json")

        self.cache_dir = cache_dir
        self.descriptions_path = descriptions_path
        self._openings = None  # Loaded lazily: list of (moves_tuple, eco, name, variation)
        self._descriptions = None

    def _ensure_loaded(self):
        """Load openings from cache or download if needed."""
        if self._openings is not None:
            return

        os.makedirs(self.cache_dir, exist_ok=True)
        self._openings = []

        for letter in LICHESS_LETTERS:
            path = os.path.join(self.cache_dir, f"{letter}.tsv")
            if not os.path.exists(path):
                self._download_tsv(letter, path)
            self._load_tsv(path)

    def _download_tsv(self, letter, save_path):
        """Download a single TSV file from Lichess."""
        url = LICHESS_BASE_URL.format(letter=letter)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            logger.info("Downloaded opening DB: %s", save_path)
        except Exception as e:
            logger.warning("Failed to download opening DB %s: %s", url, e)

    def _load_tsv(self, path):
        """Load openings from a TSV file into memory."""
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    eco = row.get("eco", "").strip()
                    name = row.get("name", "").strip()
                    uci_moves = row.get("uci", "").strip()

                    if not eco or not uci_moves:
                        continue

                    # Split name into base name and variation
                    parts = name.split(":", 1)
                    base_name = parts[0].strip()
                    variation = parts[1].strip() if len(parts) > 1 else ""

                    moves_tuple = tuple(uci_moves.split())
                    self._openings.append((moves_tuple, eco, base_name, variation))
        except Exception as e:
            logger.warning("Failed to load opening DB %s: %s", path, e)

    def match(self, board_moves_uci_list):
        """
        Match a sequence of moves to an opening.

        Args:
            board_moves_uci_list: list of UCI move strings played so far

        Returns:
            Dict with {eco, name, variation, moves_matched} or None if no match.
        """
        self._ensure_loaded()

        if not board_moves_uci_list or not self._openings:
            return None

        moves_tuple = tuple(board_moves_uci_list)
        best_match = None
        best_match_length = 0

        for opening_moves, eco, name, variation in self._openings:
            match_len = len(opening_moves)
            if match_len > len(moves_tuple):
                continue
            if moves_tuple[:match_len] == opening_moves:
                if match_len > best_match_length:
                    best_match_length = match_len
                    best_match = {
                        "eco": eco,
                        "name": name,
                        "variation": variation,
                        "moves_matched": match_len,
                    }

        return best_match

    def get_opening_description(self, eco_prefix):
        """
        Get a character description for an ECO code.

        Tries the full code, then first 3 chars, then first char.
        """
        if self._descriptions is None:
            self._load_descriptions()

        if not eco_prefix:
            return ""

        # Try longest match first
        for length in [len(eco_prefix), 3, 1]:
            key = eco_prefix[:length]
            if key in self._descriptions:
                return self._descriptions[key]

        return ""

    def _load_descriptions(self):
        """Load opening descriptions from JSON file."""
        self._descriptions = {}
        if os.path.exists(self.descriptions_path):
            try:
                with open(self.descriptions_path, "r", encoding="utf-8") as f:
                    self._descriptions = json.load(f)
            except Exception as e:
                logger.warning("Failed to load opening descriptions: %s", e)

    def download_all(self):
        """Force download of all opening TSV files."""
        os.makedirs(self.cache_dir, exist_ok=True)
        downloaded = []
        for letter in LICHESS_LETTERS:
            path = os.path.join(self.cache_dir, f"{letter}.tsv")
            self._download_tsv(letter, path)
            if os.path.exists(path):
                downloaded.append(letter.upper())
        # Reset in-memory cache to reload from fresh files
        self._openings = None
        return downloaded


# Module-level singleton for reuse
_default_db = None


def get_default_db():
    """Return the module-level OpeningDatabase singleton."""
    global _default_db
    if _default_db is None:
        _default_db = OpeningDatabase()
    return _default_db
