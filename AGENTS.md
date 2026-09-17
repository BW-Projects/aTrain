# AGENTS.md

Notes for AI coding agents (Codex, Claude Code, Copilot, ...). Contribution
mechanics are in [CONTRIBUTING.md](CONTRIBUTING.md); this file lists what an
agent would otherwise get wrong here.

## Ground rules

- State your assumptions. If the task is ambiguous, ask instead of picking silently.
- Make the minimum change that solves the problem. No speculative abstractions, no drive-by refactors, match the existing style.
- Turn the task into checks: a bug fix starts with a failing test, a UI change is clicked through in the running app. If you could not verify something, say so.

## Project invariants

- **Offline by design.** Audio and transcripts never leave the machine. The only outbound traffic is the model download from Hugging Face.
- **uv is the workflow.** `uv sync`, `uv add`, `uv lock`. No `pip install` in setup paths, no bypassing `uv.lock`.
- **Library boundaries stay thin.** `aTrain_core/backends/` adapts one library each (faster-whisper, transformers, pyannote.audio). No generic abstraction layer on top, no wrappers "for flexibility".
- **Three platforms.** Windows (MSIX) and Linux (Flatpak) ship as packages, macOS runs from source and is CPU-only. Platform-specific code needs a fallback; Linux-only deps are gated with `sys_platform` markers in `pyproject.toml`.

## Layout

- `aTrain/` - NiceGUI desktop app (pages, components, utils). Entry point `aTrain start`.
- `aTrain_core/` - transcription engine (faster-whisper and transformers backends), model loading, CLI `aTrain init`.
- `aTrain_core/data/models.json` - model registry. Every entry carries pinned file hashes and the licence id the SBOM script checks.
- `packaging/` - MSIX, Flatpak, PyInstaller. `.github/workflows/release.yml` builds and signs releases on tag push.
- `tests/unit`, `tests/core`, `tests/ui`, `tests/e2e_browser` - `.github/workflows/ci.yml` shows what runs where.
- `docs/` - user and security documentation.

## Setup and checks

```bash
uv sync --locked --extra gui           # app + engine, CPU torch
uv run ruff check . && uv run ruff format .
uv run bandit -r aTrain aTrain_core -c pyproject.toml
uv run pytest tests/unit tests/core    # fast; tests/ui and tests/e2e_browser need the GUI stack
```

Run `uv lock` after any dependency change and commit `uv.lock`; CI installs with `--locked`. Details in [CONTRIBUTING.md](CONTRIBUTING.md).

## Conventions

- Branch from `develop`, name it `feature_<topic>` or `bugfixes_<topic>`, open the PR against `develop`. Never push to `main`.
- Use the PR template in `.github/pull_request_template.md` for every PR body.
- Local agent state (`.claude/settings.local.json`, `.codex/`, `.cursor/`, `CLAUDE.local.md`) is gitignored and stays that way. Shared skills under `.claude/skills/` would be tracked.

## Gotchas

Things that have tripped us up before. If you run into a new one, add it here.

- Models and user data live under `ATRAIN_USER_DIR` (default `~/Documents/aTrain`). Tests must point it at a temp dir; the fixtures in `tests/core/test_transcription_e2e.py` show how. Never let a test download into the real folder.
- Adding a model means a `models.json` entry with file hashes and a licence id, and `.github/scripts/build-sbom.py` must accept it. Non-standard licences need a `LicenseRef-...` expression.
- Model download progress works by patching `huggingface_hub` internals in `aTrain_core/load_resources.py`. Check that path when touching downloads or bumping `huggingface_hub`.
- Heavy imports (torch, ctranslate2) must stay out of the app's startup path, or the splash screen never shows.

## Where to look

- Branching, setup, release policy: [CONTRIBUTING.md](CONTRIBUTING.md)
- MSIX and the release build: [packaging/msix/README.md](packaging/msix/README.md) and the header of `.github/workflows/release.yml`
- Signing and verification: [docs/code-signing-policy.md](docs/code-signing-policy.md), [docs/verifying-releases.md](docs/verifying-releases.md)
- Models and the SBOM: the docstring of `.github/scripts/build-sbom.py`
