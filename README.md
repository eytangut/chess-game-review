# chess-game-review

Minimal open-source chess game reviewer with Flask + python-chess, deterministic move analysis, and optional AI narrative generation.

## Features implemented

- PGN parsing (single or multi-game input)
- Metadata extraction
- Deterministic move-by-move classification from centipawn-loss approximation
- Opening matching from local TSV opening database
- Eval series, win probability, critical moments, phase and player accuracy
- Time-management summary when `%clk` comments exist
- One-per-game narrative generation via pluggable provider
- Offline-first API mocking configuration

## Offline/mock/replacement API configuration

Set environment variables:

- `OFFLINE_MODE=true|false` (default `true`)
- `USE_MOCK_APIS=true|false` (default `true`)
- `EXTERNAL_API_MODE=mock|live|off` (default `mock`)
- `AI_PROVIDER=mock|gemini|disabled` (default `mock`)
- `AI_PROVIDER_CLASS=module.ClassName` (optional replacement provider)
- `GEMINI_API_KEY=...` (required only when `AI_PROVIDER=gemini`)
- `ANALYSIS_PROFILE=fast|balanced|deep`
- `ANALYZE_COLOR=all|white|black`

`AI_PROVIDER_CLASS` lets you inject your own provider implementation (for local LLMs, mock servers, or test doubles) without changing app code.

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## Run tests

```bash
python -m unittest discover -s tests -v
```
