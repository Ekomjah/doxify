*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

# A 1B Gemma wrote 47 claims about a repo. My verifier let 13 through.

The repository had 20 commits, nine MCP tools, three database models, 26 seeded scholarship records, and no README.

I had built the thing. I had not explained it.

Every project ends the same way for me. The last commit lands, my brain shuts off, and the README stays empty. That page is the first thing an interviewer, a contributor, another developer, or a future-me sees. If it is empty, they leave.

Two years later, the other bill comes due. The dependencies have moved, the build is deprecated, and the release notes are a wall. I do not need a generic summary. I need to know which lines in my repo are affected.

The obvious fix is "ask an AI to write it." That gives you fluent sentences like *built a scalable platform used by thousands of users* or *reduced latency by 40%*, which you then have to fact-check from memory, or defend in an interview. Fluent is not the same as true.

So I built **Doxify**, a local-first CLI where **the model writes and the code checks**. It scans a git repository, turns it into numbered evidence cards, asks a local Gemma to write only from those cards, and then a deterministic verifier decides which sentences survive. Whatever it can't prove becomes a question instead of a claim.

I almost skipped this challenge. My laptop has a weak CPU, and most AI demos I saw assumed a GPU. `gemma3:1b`, a model of about 806 MB, changed that. The constraint shaped the whole design: a small model, short prompts, and a verifier that carries the trust work.

It gives open-source developers, reviewers, bots, and fellow sloths their time back.

The model writes. The code checks.

> **TL;DR**
>
> - **What:** a CLI that compiles a git repo into a cited case study, an evidence-marked README, a list of upgrade breakages that touch your code, and a CI gate. One evidence engine, four outputs.
> - **The result that matters:** on one real repo, Gemma wrote 47 claims. **13 were verified, 34 were flagged "needs evidence", 0 were rejected.** Those 34 are the review queue, not a failure.
> - **Where it runs:** an 8 GB, CPU-only laptop with `gemma3:1b` through Ollama. No API key, no upload. Cloud mode exists but is opt-in and warns you first.
> - **How it is checked:** 74 tests, Ruff, a build check, and a CI job that runs Doxify's verifier on Doxify's own README and fails if a section is unsupported.

## What I Built

Doxify turns a finished repository into the things a tired developer actually needs:

| Surface | Question it answers | What it writes |
|---|---|---|
| Case study compiler | What did I build, and can I defend it? | `case-study.md`, `claims.json`, `defense.md` |
| README compiler | What does this repo do, and how do I run it? | An evidence-marked `README.md` |
| Scout | Which upgrade actually touches my code? | `scout.md`, `scout.json`, release notes, code matches |
| CI gate | Can I trust the docs in this PR? | A pass or fail from the same verifier |

The case study came first. It was the core of this build and it is still the deepest part: six sections, a claim ledger, and an interview defense pack. The README and Scout reuse the same evidence engine, so they are not side projects. The case study is the story. The README is what visitors read. Scout is what future-you runs.

Doxify is for the developer who just pushed the last commit and cannot face a blank page. It is for the developer whose best work is private or under NDA. It is for the maintainer who comes back to a project after two years of dependency drift. It is also for the open-source maintainer whose README is the first thing contributors and bots read.

It is not a portfolio site generator. It is a review tool. The useful output is not just a draft. It is the list of claims that did not survive verification.

The sloth test is simple: start it, walk away, and come back to a review queue.

### README

`doxify readme` runs the same compile, then renders a README from verified and attested material.

Readers get clean Markdown. CI gets provenance:

```markdown
<!-- doxify-evidence: E2 E4 E5 E6 E7 -->
<!-- doxify-attested: project description and positioning -->
```

Unresolved claims are left out of the visible page. The README builder also refuses to overwrite an existing README without `--force`, and it keeps a backup when it does.

```python
if target.exists() and not force:
    raise SessionError(
        f"README target already exists: {target}. "
        "Pass --force to overwrite it, or use --output to write elsewhere."
    )
```

The tool does not eat your existing README while you are looking away.

### Scout

`doxify scout react 18 19 --repo /path/to/app` fetches release notes in the upgrade range, extracts breaking changes with exact quotes, and searches the tracked code for the affected APIs.

The point is not "here is everything that changed in React 19." The point is "here is the short list of changes that touch this repository, with file and line matches."

Scout drops any breaking change whose quote is not actually in the release notes. If the model fails, a deterministic fallback extracts breaking-change lines instead. The report only shows changes that have a code match, because a breaking change that does not touch this repository is not this repository's problem.

The repository includes a [replay fixture](https://github.com/Ekomjah/doxify/blob/main/benchmarks/scout-react-18-19.json) for the React 18 to 19 upgrade, so extraction recall can be checked against a known list instead of judged by how convincing the output looks.

### Case study

`doxify compile` produces six sections: Snapshot, The problem, The approach, The hard part, What shipped, and What I would change.

For each narrative section, Doxify retrieves up to three evidence cards and gives them to Gemma. The model writes with `[E#]` citations. The verifier checks the citations, numbers, identifiers, and a list of claims that code cannot prove.

Unsupported sentences are not deleted silently. They are marked `[needs evidence]`, paired with a gap question, and included in the claim ledger. Author context can be added with `doxify attest` and is labeled as an attestation, not repository proof.

The checked-in `nextjs-dashboard` run left 34 of its 47 claims needing evidence. That is the product working. The 34 are the review queue.

That artifact is the raw run, not a cleaned-up sample. The `[needs evidence]` tags and the model's awkward openings are the point: the verifier flags them instead of hiding them.

## Demo

There is no hosted demo. Doxify is a CLI, and the repository under analysis does not have to leave the machine. The walkthrough is the command block below; the checked-in artifacts are its output.

The motivating demo is `scholarship-mcp`: 20 commits, nine MCP tools, three models, 26 seeded records, and no README. The reproducibility artifact is a run against `nextjs-dashboard`, because it is a useful stress test.

That run produced:

- **13 verified claims**
- **34 claims that need evidence**
- **0 rejected claims**

Install Doxify on Linux, macOS, or WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/Ekomjah/doxify/v0.1.0/install.sh -o /tmp/doxify-install.sh
sh /tmp/doxify-install.sh
doxify --version
```

The installer sets up an isolated `uv` environment and runs `doxify self-check`. It does not use `sudo`, install Ollama, or download a model.

Reproduce the run locally:

```bash
ollama pull gemma3:1b
doxify self-check --json
doxify compile /path/to/nextjs-dashboard --out /tmp/doxify-demo
doxify readme /path/to/nextjs-dashboard --output /tmp/README.md
SERPAPI_API_KEY=... doxify scout react 18 19 --repo /path/to/app
```

Working from a source checkout instead? Run `uv sync`, then prefix each command with `uv run`.

Sentry is opt-in. Leave `SENTRY_DSN` unset to keep tracing off, or set it to see command, stage, model, and HTTP spans.

Precomputed artifacts:

- [Case study](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/case-study.md)
- [Claim ledger](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/claims.json)
- [Defense pack](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/defense.md)

## Code

The full project is at [github.com/Ekomjah/doxify](https://github.com/Ekomjah/doxify).

Start with:

- [`install.sh`](https://github.com/Ekomjah/doxify/blob/main/install.sh) — one-command install for Linux, macOS, and WSL.
- [`src/doxify/pipeline.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/pipeline.py) — compile, README, verify, and export.
- [`src/doxify/evidence.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/evidence.py) — deterministic scanning and evidence cards.
- [`src/doxify/verifier.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/verifier.py) — citation, number, identifier, and forbidden-claim checks.
- [`src/doxify/scout.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/scout.py) — release notes, quote validation, SerpApi fallback, and code matching.
- [`src/doxify/monitoring.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/monitoring.py) — opt-in Sentry tracing.
- [`src/doxify/redaction.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/redaction.py) — the redaction policy.
- [`src/doxify/selfcheck.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/selfcheck.py) — health checks for the Sentry cron monitor.
- [`docs/observability.md`](https://github.com/Ekomjah/doxify/blob/main/docs/observability.md) — Sentry setup, data policy, and dashboards.
- [`action.yml`](https://github.com/Ekomjah/doxify/blob/main/action.yml) — the composite GitHub Action.
- [`.github/workflows/ci.yml`](https://github.com/Ekomjah/doxify/blob/main/.github/workflows/ci.yml) — tests, build, and the self-audit.
- [`.github/workflows/sentry-nightly.yml`](https://github.com/Ekomjah/doxify/blob/main/.github/workflows/sentry-nightly.yml) — nightly self-check and cron check-in.

The repository includes 74 tests, a Ruff check, a build check, and a self-audit that runs Doxify's verifier against Doxify's README.

## How I Built It

Doxify is a Python 3.10 CLI built with Typer, Rich, Pydantic, GitPython, Ollama, and the Sentry SDK. The default model is `gemma3:1b` running locally. Users who cannot or do not want to install Ollama can opt into Ollama Cloud with `--provider cloud` and `OLLAMA_API_KEY`; cloud mode defaults to `gemma4:31b` and warns that evidence cards will leave the machine.

The core pipeline is deliberately boring:

```text
repo -> evidence cards -> 3 cards per section -> Gemma with [E#]
     -> deterministic verifier -> README / case study / defense / CI
```

A 1B model cannot hold a whole repository. Doxify does not ask it to. It gives the model a small set of precise evidence cards and a citation grammar. The model turns those cards into prose. The compiler decides whether the prose is allowed to survive.

### The compile loop

```python
for spec in SECTION_SPECS:
    cards = retrieve_evidence(scan.evidence, spec, limit=3)

    if spec.id in {"snapshot", "problem", "reflection"}:
        generated = GeneratedSection(
            body=template_section(spec, cards),
            fallback_used=False,
        )
    else:
        generated = generate_section(
            client,
            spec,
            cards,
            repo_name=scan.repo.name,
            role=role,
            draft=draft,
        )

    section_claims = extract_claims(
        spec.id,
        generated.body,
        start_index=len(claims) + 1,
    )
    claims.extend(section_claims)

claims = verify_claims(claims, scan.evidence)
```

Snapshot, problem framing, and reflection are deterministic templates because those sections are mostly structure. The narrative sections use the model. If the model fails, the section falls back to a template and the failure is recorded in the manifest.

### The verifier

Every substantive sentence becomes a claim. A generated claim without a citation cannot pass. A citation to an evidence ID that does not exist is rejected.

```python
if not claim.evidence_ids:
    claim.status = ClaimStatus.NEEDS_EVIDENCE
    claim.reason = "No citation token was found."
    return claim

cited = [evidence_by_id.get(evidence_id) for evidence_id in claim.evidence_ids]
unknown = [e for e, card in zip(claim.evidence_ids, cited, strict=False) if card is None]
if unknown:
    claim.status = ClaimStatus.REJECTED
    claim.reason = f"Unknown evidence citation(s): {', '.join(unknown)}."
    return claim
```

The verifier also checks numbers against the cited evidence, checks code identifiers, checks token overlap, and flags claims that code cannot prove: deployment, "tests pass," OAuth, user counts, performance improvements, awards, team size, and "first/only" claims.

A sentence that says the repository has 30 records when the evidence says 26 is rejected. A sentence that says "reduced latency by 40%" without a measurement needs evidence. A sentence that says "deployed to production" needs human evidence; a deployment keyword in a config file is not enough.

### README provenance

The visible README only gets supported material. The omitted claims stay in the compile session.

```python
omitted = [
    claim for claim in claims
    if claim.status not in {ClaimStatus.VERIFIED, ClaimStatus.ATTESTED}
]
```

The hidden markers tell CI which evidence supports each section:

```python
ids = " ".join(dict.fromkeys(card.id for card in cards))
if ids:
    lines.extend(["", f"<!-- doxify-evidence: {ids} -->"])
```

That is how Doxify audits its own README. The repository has a committed evidence file, hidden markers, and a CI job that fails if a section is unmarked or unsupported. The self-audit currently reports five verified claims and eight author-attested claims.

### Scout's exact-quote rule

```python
def quote_in_notes(quote: str, body: str) -> bool:
    normalized = _normalize_quote(quote)
    return len(normalized) >= 12 and normalized in _normalize_quote(body)
```

A breaking change whose quote is not found is dropped:

```python
if note is None:
    warnings.append("Dropped a change because its quote was not found in the release notes.")
    continue
```

Then the deterministic code search looks for the affected APIs in tracked files, with word-boundary matching so `render` does not match `renderToString`:

```python
pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(alias)}(?![A-Za-z0-9_$])")
```

Scout is a candidate finder, not a type checker. It tells you where to look. It does not promise the migration is complete.

### SerpApi

Scout prefers an explicit `--notes` file, then GitHub releases, then SerpApi. The fallback searches for release-note pages and pulls their text. The exact-quote rule still applies, so a search result cannot become a confident breaking-change claim unless the quote is actually on the page.

```python
key = serpapi_key or os.environ.get("SERPAPI_API_KEY")
if key:
    notes = fetch_serpapi_notes(package, from_version, to_version, api_key=key)
    warnings.append("Used SerpApi because GitHub release notes were unavailable.")
```

No key means the user can still pass `--notes FILE` and stay offline. When the key is used, the HTTP span records only the scheme, host, and path, so the query string and API key do not leak into Sentry:

```python
return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
```

### Sentry Agent Tracing

A local CLI has a visibility problem: the user sees a spinner, not the pipeline. Sentry gives Doxify an opt-in view of what happened without turning the tool into a data collector.

```python
init_monitoring()
command = _command_name()
with command_transaction(command):
    app()
```

Inside the Ollama client, a model call becomes a span with provider, model, temperature, max tokens, latency, and token usage. The prompt and the output are not recorded.

```python
with model_span(
    provider=self.provider,
    model=self.model,
    temperature=temperature,
    max_tokens=num_predict,
) as span:
    response = self._client.chat(**payload)
    record_model_usage(
        span,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
```

The trace looks like this:

```text
doxify.compile
├── validate
├── scan
├── generate × 6
│   └── model.chat  (provider, model, tokens, latency)
├── verify
├── defense
└── export
```

When a compile is slow, the trace says whether the time went into scanning, the model, or verification. When Scout fails, the HTTP span shows which fetch failed without exposing the URL query string.

Monitoring only initializes when `SENTRY_DSN` is set, and `DOXIFY_SENTRY=0` turns it off. The SDK uses a restricted data collection policy:

```python
SAFE_DATA_COLLECTION = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "http_bodies": [],
    "url_query_params": {"mode": "off"},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,
    "frame_context_lines": 0,
}
```

Tokens, API keys, and absolute home paths are redacted before events leave the process. `before_send`, `before_breadcrumb`, `before_send_transaction`, and `before_send_log` all pass through the same policy.

`self-check` can also use a Sentry cron monitor:

```python
with cron_monitor(monitor_slug):
    result = run_self_check(client=client)
```

The monitor config describes a nightly 3 a.m. UTC check-in with a 10-minute margin and a 15-minute maximum runtime. `.github/workflows/sentry-nightly.yml` runs `doxify self-check` on that schedule, so a broken install shows up as a missed check-in.

### GitHub Actions

The test job installs `uv`, syncs the lockfile, runs Ruff, runs the 74 tests, builds the package, and uploads the distributions. A separate installer job runs `install.sh` from a source checkout, then checks `doxify --version` and `doxify self-check`.

The verify job runs the self-audit through the local composite action:

```yaml
- name: Verify self-audit README
  uses: ./
  with:
    artifact: README.md
    evidence: docs/self-audit/evidence.json
    fail-on: needs_evidence,rejected
```

It also runs the unresolved `nextjs-dashboard` case study through the same verifier and asserts that the step fails. That negative test matters. A verification system that has never failed is just a green checkmark. The job sets `SENTRY_DSN=""` so CI does not initialize monitoring.

The composite action installs `uv`, syncs with `--no-dev`, and runs `doxify verify --check` with either a session or an artifact/evidence pair. External users can call it from their own workflow:

```yaml
- uses: Ekomjah/doxify@main
  with:
    session: path/to/session
    fail-on: needs_evidence,rejected
```

It is the same CLI with a smaller interface.

### What broke along the way

**The first case study was too confident.** The run against the local demo repo left 34 of its 47 claims needing evidence. That is exactly the kind of fluent, vague writing I was trying to avoid. The fix was not a longer prompt. It was smaller evidence sets, deterministic templates for structural sections, and a review queue that shows every unresolved claim.

**The README writer could overwrite an existing file.** It now refuses without `--force` and backs up the old file when it does.

**Sentry's defaults are built for web apps, not private repositories.** They collect more than a local CLI should. Request bodies, headers, query strings, user info, and model inputs are now explicitly off. Tokens and paths are redacted. A monitoring feature that leaks the repository is worse than no monitoring.

**A passing CI check proves very little if it cannot fail.** The verify job includes an unresolved case study that is expected to fail. If it ever passes, the job fails.

### What I would do next

The obvious next step is a hosted review UI for editing claims and attesting gaps. I have kept it out of this build on purpose: the CLI and the verifier are the parts that have to be right first.

After that: semantic verification instead of lexical overlap, more language support in Scout, and a better story for non-semver dependencies.

## Why Does Open Innovation Matter?

Four things were possible because the pieces are open:

- **The repo can stay private.** A developer with an NDA or sensitive customer data cannot upload the code to a hosted writing tool. Local Gemma means the evidence does not go to a model API.
- **It runs on a normal laptop.** The same weak CPU that almost kept me out is enough for `gemma3:1b`, which is about 806 MB. After the model download, the default workflow is offline. No API key, no per-token bill.
- **The model is a flag.** `--model` or `DOXIFY_MODEL` can swap Gemma for another Ollama model without changing the verifier.
- **The verifier is inspectable.** You do not have to trust the model or trust me. The checks are in the repo, and the evidence is in the output.

The optional services do not change that. Sentry is off without a DSN. SerpApi is a fallback; `--notes FILE` keeps Scout offline. The GitHub Action runs the same local verifier.

Cloud mode exists for people who cannot install Ollama, but it is opt-in and warns that evidence cards leave the machine. The default stays local because privacy is the feature.

A sloth should not have to choose between a useful tool and a private repository.

## My Agent Session

I built Doxify in an opencode session. I did not capture a separate DevRelay embed, so I will not pretend I did.

The session did the ordinary implementation work: the scanner, the verifier, Scout, the Sentry wiring, the redaction policy, the self-check command, and the CI gate. The part I care about is the boundary it produced: the model is allowed to propose prose, but it is never allowed to certify it. That boundary is enforced in code.

The durable record is the manifest, the evidence ledger, the claim ledger, and the commit history. That is the same idea behind sharing an agent session: make the work inspectable, not just impressive.

## The Lazy Payoff

I used Doxify on `nextjs-dashboard` and on Doxify's own README.

The `nextjs-dashboard` run returned 13 verified claims and 34 claims that need evidence. That sounds like a bad result. It is the useful part: the tool gave me a review queue instead of 34 confident sentences I would have had to fact-check from memory.

The README run produced a clean README with hidden provenance that CI can check. Scout turns a stack of release notes into the few breaking changes that touch my code, with file and line matches. And `scholarship-mcp`, the repo that started all this, now has something to compile: 20 commits and no README become a structured draft, a claim ledger, and an interview defense pack.

The design target is a sub-10-minute local compile on an 8 GB CPU laptop, because that is the machine I have. The model is small, the prompts are bounded, and the expensive trust work is deterministic. I would rather ship a 1B model plus a verifier that says "I cannot prove that" than a larger model that says everything confidently.

Slow and steady is the right pace for documentation, because the careful part is the part nobody wants to do by hand.

## Prize Categories

**Best Use of Gemma.** Gemma is the writer inside a compiler: `gemma3:1b` locally by default, `gemma4:31b` on Ollama Cloud when the user opts in. The model drafts the narrative; deterministic checks decide what survives.

**Best Use of Sentry Agent Tracing.** Doxify records opt-in command transactions, pipeline stages, model spans, HTTP spans, token counts, and latency, while explicitly disabling prompt/output collection and redacting secrets and paths. The trace tree above is the shape; `self-check --monitor-slug` and the nightly workflow turn a health check into a Sentry cron monitor.

**Best Use of SerpApi.** Scout falls back to SerpApi when GitHub does not have release notes, pulls the page text, and still requires the model's breaking-change quote to exist in that text. `--notes FILE` keeps the offline path available.

**Best Use of GitHub Copilot.** The category includes automating your project with GitHub Actions. The whole contribution path is automated: every push and pull request runs lint, 74 tests, a build, and the Doxify evidence gate. A Copilot-authored PR gets the same check as mine. The agent can propose; CI verifies.

**Best Use of Entire.** The category asks you to share the agent session behind the project. I did that in `My Agent Session`, and every compile writes a `manifest.json` plus `claims.json` so the reasoning trail survives the chat. Doxify makes the output of the agent's work auditable.

`#devchallenge` `#hf26challenge` `#hacktoberfest` `#opensource` `#ai` `#gemma` `#ollama` `#sentry` `#serpapi` `#githubactions` `#copilot` `#entire` `#portfolio` `#career` `#sloth`
