# Doxify

Doxify compiles evidence-backed READMEs and portfolio case studies from local
git repositories. It also scouts breaking dependency upgrades against your
code.

The core pipeline is deterministic: scan the repository, build evidence cards,
generate prose from that evidence, verify every claim, and export the result.
The model only writes; the compiler checks.

## Install

Requires Python 3.10+ and git.

```bash
uv sync
uv run doxify --help
```

Or install the package and run `doxify` directly.

## Local mode (default)

Local mode uses Ollama and `gemma3:1b`. Nothing about the repository leaves
your machine.

```bash
ollama serve
ollama pull gemma3:1b
doxify doctor
doxify readme /path/to/repo
```

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

## Commands

```bash
doxify doctor [--provider local|cloud]
doxify scan REPO
doxify compile REPO
doxify readme REPO [--output PATH]
doxify scout PACKAGE FROM TO [--repo PATH]
doxify verify SESSION
doxify attest SESSION --claim C1 --answer "..."
doxify export SESSION
```

`scan`, `verify`, `attest`, and `export` never call a model and work offline.

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

## Development

```bash
uv run pytest -q
uv run ruff check .
```
