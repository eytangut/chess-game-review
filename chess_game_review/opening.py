from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import chess.pgn


@dataclass(frozen=True)
class OpeningEntry:
    eco: str
    name: str
    moves: tuple[str, ...]


class OpeningDB:
    def __init__(self, entries: list[OpeningEntry]) -> None:
        self.entries = entries

    @classmethod
    def from_tsv(cls, path: str) -> "OpeningDB":
        file_path = Path(path)
        if not file_path.exists():
            return cls([])

        entries: list[OpeningEntry] = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("\t", 2)]
            if len(parts) < 3:
                parts = [part.strip() for part in line.split("\\t", 2)]
            if len(parts) < 3:
                continue
            eco, name, pgn_moves = parts
            game = chess.pgn.read_game(io.StringIO(pgn_moves))
            if game is None:
                continue
            board = game.board()
            uci_moves: list[str] = []
            for move in game.mainline_moves():
                uci_moves.append(move.uci())
                board.push(move)
            entries.append(OpeningEntry(eco=eco, name=name, moves=tuple(uci_moves)))
        return cls(entries)

    def match(self, moves: list[str]) -> tuple[OpeningEntry | None, int]:
        best: OpeningEntry | None = None
        best_len = 0
        as_tuple = tuple(moves)
        for entry in self.entries:
            if len(entry.moves) > len(as_tuple):
                continue
            if as_tuple[: len(entry.moves)] == entry.moves and len(entry.moves) > best_len:
                best = entry
                best_len = len(entry.moves)
        return best, best_len
