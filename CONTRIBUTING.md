# Contributing

Thanks for your interest in improving Cafe POS.

## Development setup

1. Create and activate virtual environment.
2. Install dependencies.
3. Run app and smoke tests.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
python scripts/hard_smoke.py
```

## Pull request checklist

1. Keep changes focused and scoped.
2. Run `python scripts/hard_smoke.py` before opening a PR.
3. Update docs when behavior/UI changes.
4. Do not include local data files, backups, or release artifacts.

## Coding notes

1. This app is offline-first and Windows-focused.
2. Prioritize cashier speed and operational safety.
3. Preserve compatibility with existing SQLite data.
