*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

# Doxify: for sloths who finished the project and forgot the README

I had a working project, 20 commits, nine MCP tools, three database models, 26 seeded scholarship records, and no README.

The code was done. My brain was a puddle.

If you have ever pushed the last commit and then remembered that a repository needs a front door, you know the feeling. The work exists, but the explanation does not. Interviewers, open-source contributors, bots, and fellow sloths land on the repo, see a blank README, and bounce. Then, two years later, you come back and the dependency tree has moved on without you. The build is deprecated, the upgrade notes are enormous, and you have no idea which lines actually matter.

Doxify is a tool for those two sloth moments.

It is a local-first evidence compiler for software work. It scans a local git repository, builds evidence cards, asks a Gemma model to write from those cards using a strict citation grammar, and then runs a deterministic verifier over every sentence.

The model writes. The compiler checks.

That distinction is the whole project.

## What I Built

Doxify turns a finished repository into the things a tired developer actually needs:

- an evidence-backed README that explains the repo to the next visitor,
- a Scout report that shows exactly where a dependency upgrade touches the code,
- a portfolio-ready case study,
- a claim ledger with a status for every sentence,
- and an interview defense pack built from the same evidence.

The case study compiler was the core of this competition build. It is still the deepest surface: it produces the cited story, the claim ledger, and the defense pack. But the product is shaped for sloths. The README is the front door. Scout is the time machine. The case study is the long-form story you can defend when someone asks.

The JSON and Markdown artifacts are not the point by themselves. They are the receipts that make the sloth's life easier.

### Three surfaces, one evidence engine

| Surface | Sloth question | What it writes |
|---|---|---|
| Case study compiler | What did I build, and can I defend it? | `case-study.md`, `claims.json`, `defense.md` |
| README compiler | What does this repo do, and how do I run it? | An evidence-marked `README.md` |
| Scout | Which upgrade actually touches my code? | `scout.md`, `scout.json`, release notes, code matches |
| CI gate | Can I trust the docs in this PR? | A pass/fail result from the same verifier |

The README and Scout workflows are not bolt-ons. They use the same evidence and verification machinery as the case study. That is why they belong in the same product.

Doxify is a new MIT-licensed project built during this challenge. The `scholarship-mcp` repository is the demo input, not the submitted project.

### Who Doxify is for

Doxify is for the sloth who has already done the hard part:

- the developer who just pushed the last commit and cannot face a blank README,
- the career switcher or bootcamp graduate who needs to explain technical work,
- the developer whose best work is private or under NDA,
- the open-source maintainer whose README is a landing page for contributors and bots,
- the developer returning to a project after two years of dependency drift,
- and teams that want documentation claims checked in CI instead of trusted by vibes.

It is not a fully automatic portfolio site and it is not a marketing copy generator. It is a review tool. The useful output is not just a draft; it is the list of claims that did not survive verification.

A sloth does not sprint through documentation. A sloth compiles it, reviews it, and goes back to hanging.

### The sloth's front door: README

`doxify readme` runs the same compile, then renders a clean README from verified and attested material.

The visible prose has no citation clutter. The provenance lives in HTML comments:

```markdown
<!-- doxify-evidence: E2 E4 E5 E6 E7 -->
<!-- doxify-attested: project description and positioning -->
```

Readers get a normal README. CI gets an audit trail.

The README builder omits unresolved claims from visible prose, strips the "No README" evidence card, refuses to overwrite an existing README without `--force`, and keeps a backup when it does. The temporary compile session can be inspected or cleaned up.

```python
if target.exists() and not force:
    raise SessionError(
        f"README target already exists: {target}. "
        "Pass --force to overwrite it, or use --output to write elsewhere."
    )
```

That is the sloth-safe write path. The tool does not eat your existing README while you are looking away.

### The sloth's time machine: Scout

`doxify scout react 18 19 --repo /path/to/app` fetches release notes in the upgrade range, extracts breaking changes with exact quotes, and searches the tracked code for the affected APIs.

The point is not "here is everything that changed in React 19." The point is "here is the short list of changes that touch this repository, with file and line matches."

Scout is deliberately strict about quotes. If the model returns a "quote" that is not actually in the release notes, the change is dropped. If the model fails, a deterministic fallback extracts breaking-change lines instead. The report only shows changes that have a code match, because a breaking change that does not touch this repository is not this repository's problem.

It writes `scout.md`, `scout.json`, `release-notes.json`, and `manifest.json`, and it never modifies the scanned repository.

The repository includes a replay fixture for the React 18 to 19 upgrade, so extraction recall can be checked against a known list instead of judged by how convincing the output looks.

### The sloth's story: case study

`doxify compile` produces six sections: Snapshot, The problem, The approach, The hard part, What shipped, and What I would change.

For each narrative section, Doxify retrieves up to three evidence cards and gives them to Gemma. The model is instructed to write with `[E#]` citations that point back to the evidence ledger. Then the deterministic verifier checks those citations, numbers, identifiers, and a list of claims that code cannot prove.

Unsupported sentences are not deleted silently. They are marked `[needs evidence]`, paired with a gap question, and included in the claim ledger. Author context can be added with `doxify attest`, and it is visibly labeled as an attestation rather than treated as repository proof.

The output is not "here is your finished portfolio." It is "here is the draft, here is the proof, and here are the 34 sentences you need to think about."

That is more useful to me than a polished lie.

## Demo

There is no hosted demo, and that is deliberate. Doxify's default workflow is local; the repository under analysis should not have to leave the machine.

The motivating before/after is `scholarship-mcp`: 20 commits, nine MCP tools, three models, 26 seeded records, and no README. A real project with a real technical arc and no written narrative.

The checked-in reproducibility artifact is a run against `nextjs-dashboard`, because it is a useful stress test. That run produced:

- **13 verified claims**
- **34 claims that need evidence**
- **0 rejected claims**

That is the demo. The tool is showing you the 34 sentences it will not pretend are proven.

Reproduce it locally:

```bash
git clone https://github.com/Ekomjah/doxify
cd doxify
uv sync
ollama pull gemma3:1b

uv run doxify self-check --json
uv run doxify compile /path/to/nextjs-dashboard --out /tmp/doxify-demo
uv run doxify readme /path/to/nextjs-dashboard --output /tmp/README.md
SERPAPI_API_KEY=... uv run doxify scout react 18 19 --repo /path/to/app
```

Sentry is opt-in: leave `SENTRY_DSN` unset to keep tracing off, or set it to see command, stage, model, and HTTP spans.

Precomputed artifacts:

- [Case study](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/case-study.md)
- [Claim ledger](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/claims.json)
- [Defense pack](https://github.com/Ekomjah/doxify/blob/main/output/next-dashboard/case-study/defense.md)

A 90-second terminal recording of those commands is the intended video demo. The checked-in output is the same artifact.

## Code

The full project is at [github.com/Ekomjah/doxify](https://github.com/Ekomjah/doxify).

Start with:

- [`src/doxify/pipeline.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/pipeline.py) — the compile, README, verify, and export flows.
- [`src/doxify/evidence.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/evidence.py) — deterministic repository scanning and evidence cards.
- [`src/doxify/verifier.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/verifier.py) — citation, number, identifier, and forbidden-claim checks.
- [`src/doxify/scout.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/scout.py) — release-note extraction, quote validation, SerpApi fallback, and code matching.
- [`src/doxify/monitoring.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/monitoring.py) — opt-in Sentry tracing.
- [`src/doxify/redaction.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/redaction.py) — the redaction policy that keeps traces boring.
- [`src/doxify/selfcheck.py`](https://github.com/Ekomjah/doxify/blob/main/src/doxify/selfcheck.py) — the local health checks behind the Sentry cron monitor.
- [`action.yml`](https://github.com/Ekomjah/doxify/blob/main/action.yml) — the composite GitHub Action.
- [`.github/workflows/ci.yml`](https://github.com/Ekomjah/doxify/blob/main/.github/workflows/ci.yml) — the CI and self-audit jobs.

The repository includes 73 tests, a Ruff check, a build check, and a self-audit that runs Doxify's own verifier against Doxify's own README.

## How I Built It

Doxify is a Python 3.10 CLI built with Typer, Rich, Pydantic, GitPython, Ollama, and the Sentry SDK. The default model is `gemma3:1b` running locally. Users who cannot or do not want to install Ollama can explicitly opt into Ollama Cloud with `--provider cloud` and `OLLAMA_API_KEY`; cloud mode defaults to a Gemma-family `gemma4:31b` model and warns that evidence cards will leave the machine.

The architecture is intentionally boring:

```text
local repo
   |
   v
deterministic scan  ->  evidence cards
   |
   v
retrieve 3 cards per section
   |
   v
Gemma drafts with [E#] citations
   |
   v
deterministic verifier
   |
   +--> verified / attested
   +--> needs evidence -> gap question
   +--> rejected -> visible warning
   |
   v
README / case study / defense pack / CI result
```

Around that core:

```text
GitHub releases / SerpApi / --notes
        -> Scout -> exact-quote check -> code search -> scout.md

Sentry (opt-in) -> command, stage, model, and HTTP spans
GitHub Actions -> lint, test, build, verify, expected-failure check
```

The hard part was not getting a model to write. The hard part was making a 1B model trustworthy enough to be useful.

A 1B model cannot hold a whole repository in context. Doxify does not ask it to. It gives the model a small set of precise evidence cards and a citation grammar. The model's job is to turn those cards into readable prose. The compiler's job is to decide whether the prose is allowed to survive.

### The compile loop

The pipeline does not let the model write the whole document and then hope. It builds the case study section by section:

```python
for index, spec in enumerate(SECTION_SPECS, start=1):
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

### The verifier is the product

Every substantive sentence is parsed into a claim. Every `[E#]` is checked against the evidence ledger. A generated claim without a citation cannot pass. A citation to an evidence ID that does not exist is rejected outright.

```python
if not claim.evidence_ids:
    claim.status = ClaimStatus.NEEDS_EVIDENCE
    claim.reason = "No citation token was found."
    return claim

cited = [evidence_by_id.get(evidence_id) for evidence_id in claim.evidence_ids]
unknown = [
    evidence_id
    for evidence_id, card in zip(claim.evidence_ids, cited, strict=False)
    if card is None
]
if unknown:
    claim.status = ClaimStatus.REJECTED
    claim.reason = f"Unknown evidence citation(s): {', '.join(unknown)}."
    return claim
```

After that, the verifier checks numbers against the cited evidence, checks code identifiers, checks token overlap, and flags claims that code cannot prove: deployment, "tests pass," OAuth, user counts, performance improvements, awards, team size, and "first/only" claims.

If a sentence says a repository has 30 records and the evidence says 26, it is rejected. If it says "reduced latency by 40%" and the evidence has no measurement, it needs evidence. If it says "deployed to production," it needs human evidence; a deployment keyword in a config file is not enough.

The verifier is intentionally conservative. It catches unsupported claims, not every subtle falsehood. That limitation is documented, and it is why attestations are labeled separately.

### README provenance

The README mode keeps the document clean but auditable:

```python
omitted = [
    claim
    for claim in claims
    if claim.status not in {ClaimStatus.VERIFIED, ClaimStatus.ATTESTED}
]
```

Those omitted claims stay in the compile session. The visible README gets the supported material, while the hidden markers tell CI which evidence supports each section:

```python
ids = " ".join(dict.fromkeys(card.id for card in cards))
if ids:
    lines.extend(["", f"<!-- doxify-evidence: {ids} -->"])
```

This is also how Doxify audits its own README. The repository has a committed evidence file, hidden markers, and a CI job that fails if a section is unmarked or unsupported. The self-audit currently reports five verified claims and eight author-attested claims.

### Scout's exact-quote rule

Scout follows the same principle: the model can propose, but the source has to agree.

```python
def quote_in_notes(quote: str, body: str) -> bool:
    normalized = _normalize_quote(quote)
    return len(normalized) >= 12 and normalized in _normalize_quote(body)
```

A breaking change whose quote is not found in the release notes is dropped:

```python
if note is None:
    warnings.append(
        "Dropped a change because its quote was not found in the release notes."
    )
    continue
```

Then the deterministic code search looks for the affected APIs in tracked files, with word-boundary matching so `render` does not match `renderToString`:

```python
pattern = re.compile(
    rf"(?<![A-Za-z0-9_$]){re.escape(alias)}(?![A-Za-z0-9_$])"
)
```

Scout is a candidate finder, not a type checker. It tells you where to look. It does not promise the migration is complete.

### SerpApi: release notes when GitHub is not enough

Scout prefers an explicit `--notes` file, then GitHub releases, then SerpApi. The fallback searches for release-note pages and pulls their text. The exact-quote rule still applies, so a search result cannot become a confident breaking-change claim unless the quote is actually on the page.

```python
key = serpapi_key or os.environ.get("SERPAPI_API_KEY")
if key:
    notes = fetch_serpapi_notes(package, from_version, to_version, api_key=key)
    warnings.append("Used SerpApi because GitHub release notes were unavailable.")
```

The query is deliberately specific:

```python
query = f"{package} {from_version} to {to_version} release notes breaking changes"
```

SerpApi is an optional accelerator, not a new dependency in the core workflow. No key means the user can still pass `--notes FILE` and stay fully offline. When the key is used, the HTTP span records only the scheme, host, and path, so the query string and API key do not leak into Sentry:

```python
return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
```

### Sentry Agent Tracing: a nervous system for a local CLI

A local CLI has a visibility problem: the user sees a spinner, not the pipeline. Sentry Agent Tracing gives Doxify an opt-in view of what actually happened without turning the tool into a data collector.

The wiring starts at the CLI boundary:

```python
init_monitoring()
command = _command_name()
with command_transaction(command):
    app()
```

Inside the Ollama client, a model call becomes a span with provider, model, temperature, max tokens, latency, and token usage:

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

That gives a trace shaped like this:

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

The privacy side is not an afterthought. Monitoring only initializes when `SENTRY_DSN` is explicitly set, and `DOXIFY_SENTRY=0` turns it off. The SDK is configured with a restricted data collection policy:

```python
SAFE_DATA_COLLECTION = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "stack_frame_variables": False,
}
```

Prompts and model outputs are not collected. Tokens, API keys, and absolute home paths are redacted before events leave the process. `before_send`, `before_breadcrumb`, `before_send_transaction`, and `before_send_log` all pass through the same policy. The result is tracing that is useful for debugging and boring for anyone who should not see the repository.

The `self-check` command can also use a Sentry cron monitor:

```python
with cron_monitor(monitor_slug):
    result = run_self_check(client=client)
```

The monitor config describes a nightly 3 a.m. UTC check-in with a 10-minute margin and a 15-minute maximum runtime; point a scheduler at `self-check` when you want the sloth to be watched. If the local model or the package install is broken, the sloth finds out before a user does.

### GitHub Actions: the sloth's guardrail

The GitHub Actions workflow is the part that lets a sloth walk away. It does not ask a human to remember to run the verifier.

The test job installs `uv`, syncs the lockfile, runs Ruff, runs the 73 tests, builds the package, and uploads the distributions. The verify job runs the thing this project is actually about:

```yaml
- name: Verify self-audit README
  uses: ./
  with:
    artifact: README.md
    evidence: docs/self-audit/evidence.json
    fail-on: needs_evidence,rejected
```

It also runs the unresolved `nextjs-dashboard` case study through the same verifier and asserts that the step fails. That negative test matters: a verification system that has never failed is just a very confident green checkmark. The job sets `SENTRY_DSN=""` so CI does not initialize monitoring.

The composite action itself installs `uv`, syncs with `--no-dev`, and runs `doxify verify --check` with either a session or an artifact/evidence pair. External users can call it from their own workflow:

```yaml
- uses: Ekomjah/doxify@main
  with:
    session: path/to/session
    fail-on: needs_evidence,rejected
```

This is the same verifier that runs locally. The action is not a second implementation with different rules; it is the CLI with a smaller interface.

### What is not done yet

- The current build is a CLI. The FastAPI and Next.js review UI is planned, not shipped.
- Verification is lexical and deterministic, not full semantic entailment.
- Scout relies on semver-style releases and release-note quality; it is best at major upgrades.
- Doxify skips common secret files, but it is not a security scanner and does not sanitize a repository for publication.
- Attestations are author-owned claims. They are labeled, not magically verified.
- The agent-session write-up is in this post, but there is no separate DevRelay embed.

## Why Does Open Innovation Matter?

Because the most valuable repositories are often the ones you cannot upload.

A developer with a private company repo, an NDA, or sensitive customer data cannot hand the code to a hosted writing tool. A closed API turns "help me write about my work" into "choose between privacy and help." That is a bad trade.

Open-weight Gemma changes the economics and the trust model. `gemma3:1b` is about 806 MB and runs on an 8 GB CPU laptop. That means a student on a cheap machine can use the default workflow offline, with no API key and no per-token bill. The repository evidence does not go to a model API in local mode. The model is small enough to run on the kind of laptop the target user already owns. And because the model is just a flag, the user can swap Gemma for another Ollama model without changing the verifier.

The open part is not just the weights. The verifier is open source too. You do not have to trust the model or trust me. You can read the checks, run them against the evidence, and see exactly why a sentence passed or failed. The output is portable Markdown and JSON, not a proprietary dashboard.

Open innovation is also what makes the optional services honest. Sentry tracing, SerpApi, and the GitHub Action are useful, but they are not required for the core loop. No DSN means no tracing. No SerpApi key means `--notes FILE` still works. The local path remains the default because privacy is the feature.

A sloth should not have to choose between a useful tool and a private repository. Local weights and an open verifier are what let the sloth have both.

## My Agent Session

I built Doxify in an opencode session. I did not capture a separate DevRelay embed for this submission, and I am not going to invent one.

The session did the ordinary implementation work: scaffolding, refactors, the evidence scanner, the verifier, Scout, the Sentry wiring, the redaction policy, the self-check command, and the CI gate. The part I care about is the boundary it produced: the model is allowed to propose prose, but it is never allowed to certify it. That boundary is enforced in code, not in a prompt.

The durable record is in the manifest, the evidence ledger, the claim ledger, and the commit history. That is the same idea behind sharing an agent session: make the work inspectable, not just impressive.

## The Lazy Payoff

The lazy payoff is not "AI writes your portfolio while you sleep." It is "you review a cited draft instead of starting from a blank page."

I used Doxify on `nextjs-dashboard` and on Doxify's own README. The `nextjs-dashboard` run returned 13 verified claims and 34 claims that need evidence. That sounds like a bad result. It is the point: the tool gave me a review queue instead of 34 confident sentences I would have had to fact-check from memory.

The README run gave me a clean README with hidden provenance that CI can check. The Scout run turns a stack of release notes into a list of breaking changes and file/line matches, which is a much smaller job than reading every note and guessing what matters.

For `scholarship-mcp`, the input is 20 commits, nine tools, three models, and 26 records with no README. The first compile turns that raw history into a structured draft, a claim ledger, and an interview defense pack. The user's job shifts from writing to verifying.

The design target is a sub-10-minute local compile on an 8 GB CPU laptop. The model is small, the prompts are bounded, and the expensive trust work is deterministic. I would rather ship a 1B model that says "I cannot prove that" than a larger model that says everything confidently.

Slow and steady is the right pace for this problem. The branch can wait. The nap cannot. Doxify is patient about the part that matters: the evidence.

## Prize Categories

**Best Use of Gemma.** Gemma is not a chatbot bolted onto a form. It is the writer inside a compiler: `gemma3:1b` locally by default, `gemma4:31b` on Ollama Cloud when the user explicitly opts in. The model drafts the narrative; deterministic checks decide what survives. The result is a Gemma-powered workflow that is useful precisely because the model is not the final authority.

**Best Use of Sentry Agent Tracing.** Doxify records opt-in command transactions, pipeline stages, model spans, HTTP spans, token counts, and latency, while explicitly disabling prompt/output collection and redacting secrets and paths. `self-check --monitor-slug` turns a health check into a Sentry cron monitor. It is tracing for a local-first agent that still respects the local-first part.

**Best Use of SerpApi.** Scout's fallback searches for release notes when GitHub does not have them, pulls the page text, and still requires the model's breaking-change quote to exist in that text. SerpApi makes Scout work for packages with messy release distribution; `--notes FILE` keeps the offline path available.

**Best Use of GitHub Copilot.** The repository's agent workflow is the GitHub Actions gate: every push and pull request gets lint, 73 tests, a build, and the Doxify evidence check. A Copilot-authored contribution gets the same treatment as mine: the agent can propose, and CI verifies. The Actions half is live; the contribution path is the point.

**Best Use of Entire.** The build session is summarized in `My Agent Session`, and every compile writes a `manifest.json` plus `claims.json` so the reasoning trail survives the chat. Entire is about making agent work searchable and reviewable; Doxify makes the output of that work auditable.

`#hf26challenge` `#hacktoberfest` `#opensource` `#ai` `#gemma` `#ollama` `#sentry` `#serpapi` `#githubactions` `#copilot` `#entire` `#portfolio` `#career` `#sloth`
