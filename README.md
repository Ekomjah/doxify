# Doxify

Doxify compiles evidence-backed READMEs and portfolio case studies from local
git repositories. It also scouts breaking dependency upgrades against your
code.

The core pipeline is deterministic: scan the repository, build evidence cards,
generate prose from that evidence, verify every claim, and export the result.
The model only writes; the compiler checks.

<!-- doxify-attested: project description and positioning -->

## Install

Linux, macOS, and WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/Ekomjah/doxify/v0.1.0/install.sh -o /tmp/doxify-install.sh
sh /tmp/doxify-install.sh
```

The installer requires `curl`, `git`, and `tar`. It installs `uv` if needed,
places Doxify in an isolated per-user environment, and runs
`doxify self-check`. It does not use `sudo`, install Ollama, or download a model.

Verify the install:

```bash
doxify --version
doxify self-check --json
```

From a source checkout:

```bash
git clone https://github.com/Ekomjah/doxify
cd doxify
uv sync
uv run doxify --help
```

Native Windows is not supported by the shell installer yet. Use WSL for now.

<!-- doxify-attested: installation instructions -->

## Local mode (default)

Local mode uses Ollama and `gemma3:1b`. Nothing about the repository leaves
your machine.

```bash
ollama serve
ollama pull gemma3:1b
doxify doctor
doxify readme /path/to/repo
```

<!-- doxify-attested: local setup and privacy behavior -->

## Cloud mode (no local Ollama install)

Cloud mode uses Ollama Cloud directly. You do not need the Ollama app, server,
or a downloaded model. You do need an API key.

```bash
export OLLAMA_API_KEY="your_api_key"
doxify doctor --provider cloud
doxify readme /path/to/repo --provider cloud
```

Cloud defaults to `gemma4:31b`. Override it with `--model` or `DOXIFY_MODEL`.

Cloud mode sends evidence cards (file paths, snippets, commit messages, and
dependency names) to Ollama Cloud. Do not use it for confidential repositories.
Cloud usage may incur charges.

Configuration:

| Setting | Flag | Environment variable | Default |
|---|---|---|---|
| Provider | `--provider` | `DOXIFY_PROVIDER` | `local` |
| Model | `--model` | `DOXIFY_MODEL` | `gemma3:1b` local, `gemma4:31b` cloud |
| Endpoint | `--host` | `DOXIFY_OLLAMA_HOST` | `http://127.0.0.1:11434` local, `https://ollama.com` cloud |
| API key | none | `OLLAMA_API_KEY` | required for cloud |

Precedence is flag, then environment variable, then default.

<!-- doxify-attested: cloud setup, privacy, and billing guidance -->

## Commands

```bash
doxify --version
doxify self-check [--json] [--check-model]
doxify doctor [--provider local|cloud]
doxify scan REPO
doxify compile REPO
doxify readme REPO [--output PATH]
doxify scout PACKAGE FROM TO [--repo PATH]
doxify verify SESSION [--artifact PATH] [--fail-on STATUSES]
doxify attest SESSION --claim C1 --answer "..."
doxify export SESSION
```

`scan`, `verify`, `attest`, and `export` never call a model and work offline.

`doxify verify` exits non-zero when a claim needs evidence or is rejected. Use
`--fail-on none` to report without failing, `--check` to avoid rewriting session
files, and `--artifact` with `--evidence` to audit a README or case study
directly.

<!-- doxify-attested: command reference -->

## Project facts

Doxify is written in Python. The project declares runtime dependencies including
`gitpython`, `ollama`, `pydantic`, `rich`, `sentry-sdk`, `tomli`, and `typer`.

The repository is organized into top-level paths including `src`, `tests`,
`output`, and `.github`.

The repository contains test-related files at `tests/test_readme.py`. CI is
defined in `.github/workflows/ci.yml`.

<!-- doxify-evidence: E2 E4 E5 E6 E7 -->

## Scout upgrades

`doxify scout` fetches release notes between two versions, extracts breaking
changes with exact quotes, and searches your tracked code for affected APIs.

```bash
doxify scout react 18 19 --repo /path/to/app
```

Use `--notes FILE` for offline notes, `--deep` to analyze every fetched release,
and `--expect FILE` to replay a known breaking-change list. Scout writes
`scout.md`, `scout.json`, `release-notes.json`, and `manifest.json`; it never
modifies the scanned repository.

<!-- doxify-attested: scout usage instructions -->

## Verify in CI

The composite action runs the same deterministic checker. Unmarked sections
fail; sections marked `doxify-attested` are author-owned and pass unless
`attested` is added to `fail-on`. Point it at an evidence-marked README:

```yaml
- uses: Ekomjah/doxify@main
  with:
    artifact: README.md
    evidence: docs/self-audit/evidence.json
    fail-on: needs_evidence,rejected
```

Or point it at a compile session to fail on unresolved case-study claims:

```yaml
- uses: Ekomjah/doxify@main
  with:
    session: path/to/session
    fail-on: needs_evidence,rejected
```

<!-- doxify-attested: CI usage instructions -->

## Development

```bash
uv run pytest -q
uv run ruff check .
```

<!-- doxify-attested: contributor instructions -->
