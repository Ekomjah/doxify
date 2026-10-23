# Doxify — Hacktoberfest Week 3 Project Plan

> Working title: **Doxify**  
> Tagline: **Portfolio case studies you can defend.**  
> Status: planning complete; implementation not started.  
> Plan date: 2026-10-22.  
> Hackathon deadline: 2026-10-25, 11:59 PM PDT = 2026-10-26, 7:59 AM WAT.  
> Target category: **Best Use of Gemma**.  
> Demo input repo: `/home/ekomjah/Desktop/repos/scholarship-mcp`.

---

## 0. How to use this document

This document is the single source of truth for the project. It is intentionally verbose so that implementation decisions do not have to be re-derived later.

Read it in this order:

1. **Sections 1–6** — why this project exists and why the demo repo was chosen.
2. **Sections 7–16** — what the product does, how it looks, and how it is built.
3. **Sections 17–21** — the execution plan, tests, demo, and submission.
4. **Sections 22–25** — risks, cut lines, open decisions, and first commands.
5. **Appendices** — exact evidence from the demo repo, sample content, and references.

If time is short, the non-negotiable core is:

- scan a local repo,
- build evidence cards,
- generate a case study where every sentence cites evidence,
- flag unsupported or contradicted claims,
- generate an interview defense pack,
- export Markdown,
- run fully locally with Gemma via Ollama.

Everything else is optional.

---

## 1. One-page summary

**Doxify** is a local-first portfolio case study compiler.

It takes a finished software project and turns it into:

- a portfolio-ready case study,
- an evidence ledger,
- and an interview defense pack.

The important difference is that it does not simply ask a language model to write a story about a repository. It first extracts evidence from the repository, then writes only from that evidence, then verifies that every claim is either:

- supported by code or git history,
- explicitly attested by the user,
- or flagged as missing evidence.

The product thesis is simple:

> Most AI portfolio tools generate confidence. Doxify generates defensibility.

The demo project is `scholarship-mcp`, a working MCP server with 20 commits, 9 tools, 3 database models, 26 seeded scholarship records, and no README. That is the perfect before/after story: a real project with a real technical arc, but no written portfolio narrative.

The tool is built with Python 3.14 + FastAPI on the backend and Next.js + TypeScript on the frontend, with a local `gemma3:1b` model through Ollama. It has no database, no cloud API, no telemetry, and no account system. It reads a local repository, writes session files locally, and calls only the local Ollama server.

The hackathon submission is a brand-new repository. `scholarship-mcp` is only the input used for the demonstration; it is not the submitted project.

---

## 2. The problem

### 2.1 The user problem

Developers finish projects and then fail to write them up.

The work already exists:

- commits,
- code,
- tests,
- deployment files,
- design decisions,
- bug fixes,
- refactors,
- README fragments,
- notes,
- screenshots.

But turning that material into a portfolio case study is a separate, dreaded task. It requires:

- remembering why decisions were made,
- reconstructing a timeline,
- deciding what matters,
- writing for recruiters,
- writing for interviewers,
- checking that every claim is true,
- and making the result sound like a person, not a template.

Most people postpone it. Their portfolio stays stale or empty.

### 2.2 The AI problem

The obvious solution is “ask an LLM to write the case study.”

That creates a new problem: **AI slop that collapses in an interview.**

A generic model will happily write:

- “Built a scalable platform used by thousands of users.”
- “Reduced latency by 40%.”
- “Led a team of five engineers.”
- “Implemented OAuth authentication.”

None of those claims may be true. Some may be partly true. Some may be impossible to verify from code. The developer then has to defend them in a hiring conversation.

The failure is structural:

- the model was given a repository,
- it was asked for a narrative,
- and it optimized for a confident story rather than a true one.

Prompting more carefully does not fix this. The missing ingredient is **evidence with a verification step**.

### 2.3 The private-work problem

    The problem gets worse for private or NDA work.

Many developers cannot share the repository at all. Their best work lives behind a company login. Cloud portfolio tools ask them to connect GitHub or upload code, which is often not allowed.

A local tool is not a nice-to-have here. It is the only way the workflow can exist.

### 2.4 The interview problem

A portfolio case study is not just a document. It is a promise:

> “I can answer questions about this.”

If the document says “I designed a matching engine,” the interviewer may ask:

- Why did you choose that scoring model?
- How did you handle ineligible candidates?
- What did you test?
- What would you change?

A generated story without evidence creates interview risk. The tool should prepare the user for that conversation, not just produce prettier prose.

---

## 3. The insight

The insight is:

> A case study should be compiled from evidence, not generated from a prompt.

This leads to a different product architecture:

1. **Extract evidence first.**
2. **Write only from evidence.**
3. **Verify every claim.**
4. **Turn missing evidence into questions.**
5. **Rehearse the defense.**

The language model is still useful, but its role changes. It is not the source of truth. It is a writing assistant that works inside a compiler.

The deterministic parts do the trust-bearing work:

- file scanning,
- commit history,
- counting,
- keyword matching,
- citation checks,
- numeric checks,
- secret redaction.

The model writes prose and questions. The compiler checks the result.

This is also a good fit for a small model. A 1B model cannot hold an entire repository in its head, but it can rewrite a short section when given six precise evidence cards and a strict citation format.

---

## 4. Hackathon context

### 4.1 The challenge

Hacktoberfest 2026 Week 3 theme: **Slow and Steady**.

The challenge asks for a brand-new project with open-source AI at its core. The project should reward laziness by helping someone relax, automating a task, or otherwise making life easier.

Required elements:

- a new project created and completed during the entry period,
- open-source AI at the core: open-weight models, open agent harnesses, or local inference,
- a DEV submission post using the challenge template and `#hf26challenge`,
- an explanation of why open innovation matters for the project,
- a demo link or video,
- a link to or embed of the code.

Deadline: October 25, 2026, 11:59 PM PDT = October 26, 2026, 7:59 AM WAT.

### 4.2 Why Doxify fits “Slow and Steady”

The literal reading of the theme is “automate something while you rest.”

Doxify fits, but with a sharper interpretation:

> Good case studies are slow. The tool makes the slow part painless.

The user does not have to spend a weekend writing. They start a compile, walk away, and come back to:

- a cited draft,
- a list of claims that need evidence,
- and an interview prep sheet.

The tool deliberately refuses to rush the truth. That is the “steady” part.

### 4.3 Why it fits the Gemma category

The product’s privacy promise depends on local inference:

- the repository may be private,
- the career claims may be sensitive,
- the output may mention internal architecture,
- the user may be offline.

Using a cloud API would undermine the core story. `gemma3:1b` via Ollama is small enough to run on the target laptop and open enough to be inspectable and portable.

The submission should make this explicit:

- local model,
- local repo,
- no network calls,
- no API keys,
- no per-token cost.

### 4.4 What must be new

The submitted project must be a new repository created during the entry period.

`scholarship-mcp` is an existing repository. It is allowed as **input data** for the demo. It must not be presented as the submitted project.

The submission repository should be something like `doxify` and should contain all new code, README, license, tests, and demo artifacts.

---

## 5. Competitive landscape

The generic lane is crowded. This section exists so the project does not accidentally become a worse version of something that already exists.

### 5.1 Generic portfolio case study generators

Examples found during research:

- GitShowcase — GitHub activity, case studies, career copy.
- Gitfolio — commits to portfolio, including private repos and evidence-cited claims.
- Jobr AI Portfolio Builder — GitHub repos to portfolio site and case studies.
- FolioLab — GitHub repositories to portfolio.
- Repo2Site — GitHub profile to editable portfolio.
- SerisLab — GitHub or resume to portfolio.
- Prooflink — AI engineering dossier and case studies.
- GitSkins — READMEs, portfolios, case studies, GitHub Wrapped.
- GitStory / GitNarrative — commits to narrative stories.
- `portfolio-showcase-generator` — Claude skill for portfolio materials.
- `SonwaneyY/portfolio-case-study-generator` — Claude skill for design case studies.

What they generally do well:

- import repositories,
- generate copy,
- provide templates,
- publish a portfolio site,
- sometimes cite commits.

What they generally do not do:

- run fully locally on a small open-weight model,
- treat evidence as a first-class ledger,
- refuse unsupported claims,
- generate an interview defense pack,
- combine all of the above in one workflow.

### 5.2 Evidence and claim verification tools

Examples:

- ClaimCheck — proves document claims against a codebase with file:line citations.
- Proofrail — verifies AI agent completion claims against a commit range.
- Checkmarked — code-verified portfolio claims.
- GitReal — resume verification and “defense mode.”
- CareerForge — local-first evidence engine for resume bullets and STAR stories.
- ProofMap — resume skills vs. GitHub evidence.
- GitHub Resume Assistant — resume claims vs. public GitHub.
- ResumeProof — evidence-based resume tailoring with a claim ledger.
- `claims-ledger` — machine-verifiable claim anchors.
- ProofChain — claim-to-evidence proof packs for grants and hackathons.

What they prove:

- the evidence-ledger idea is valid,
- users care about not lying,
- citations are a real differentiator.

What they generally do not do:

- produce a polished portfolio case study,
- produce an interview defense pack,
- run on a 1B local model,
- target the specific “finished project → portfolio → interview” workflow.

### 5.3 Private/NDA-safe case study tools

Examples:

- Gitfolio supports private repos as first-class.
- CodeBridge scans private codebases and publishes sanitized public versions.
- Repo Cloak anonymizes code for AI assistants.
- `saw` creates a sanitized agent workspace.
- Many developers manually publish sanitized case studies in public repos.

What this proves:

- private-work portfolio help is a real need,
- sanitization is hard,
- hosted tools have a trust problem.

What is still open:

- a local compiler that produces a **case study + claim ledger + defense pack** from a private repo without sending the repo anywhere.

### 5.4 The wedge

Doxify is not “another AI case study generator.”

It is:

> a local evidence compiler that happens to write a case study.

The memorable line:

> **Most tools write the story first. Doxify collects the proof first.**

The three differentiators:

1. **Evidence-first generation** — the model cannot write a sentence without a citation token.
2. **Fail-closed verification** — missing or contradicted evidence becomes a question, not confident prose.
3. **Interview defense** — the output includes the questions an interviewer would ask and the evidence-backed answer outline.

The local/open-weight requirement is not a gimmick. It is what makes the private-work use case possible.

---

## 6. Demo project: scholarship-mcp

### 6.1 Why this repo

`scholarship-mcp` is a strong demo because it is a real, working project with a clear technical story and no README.

Facts verified from the repository:

| Fact                                        | Evidence                 |
| ------------------------------------------- | ------------------------ |
| 20 commits                                  | `git log --reverse`      |
| Built Sept 12–14, 2026                      | commit dates             |
| No README                                   | `git ls-files`           |
| 9 MCP tools                                 | `src/utils/tools.js`     |
| 3 Mongoose models                           | `src/models/`            |
| 1 MCP prompt                                | `src/mcp/prompt.js`      |
| 1 MCP resource template                     | `src/mcp/resource.js`    |
| Streamable HTTP + graceful shutdown         | `src/index.js`           |
| Hard eligibility filters + weighted scoring | `src/services/match.js`  |
| 26 seeded scholarship records               | `data/scholarships.json` |
| Seed script                                 | `scripts/seed.js`        |
| Smoke test                                  | `scripts/smoke-test.js`  |

The repository has a clean commit arc:

1. initial setup,
2. models,
3. services,
4. MCP tool schemas and handlers,
5. prompt and resource,
6. server assembly,
7. seed data,
8. smoke test,
9. host default fix.

That arc is exactly the kind of thing a portfolio case study needs, and exactly the kind of thing a README would normally hide.

### 6.2 The story the case study should tell

Working title for the demo case study:

> **Scholarship MCP: Giving an AI agent real scholarship-research tools**

The narrative:

- Scholarship search is usually a form or a scraping problem.
- An AI agent with no tools can only talk about scholarships; it cannot search, compare, save, or track them.
- This project exposes a small, typed MCP tool surface so an agent can do real research work.
- The hard part is not the CRUD. The hard part is eligibility matching that is explainable: hard filters remove ineligible awards, then weighted scoring ranks the rest with reasons.
- The project also includes a research prompt, a resource template, a seed catalog, and a smoke test.
- What is missing: a README, a real data source, authentication, and production hardening.
- That honesty is the point.

### 6.3 True claims for the demo

These should be verifiable and citable:

- Exposes nine MCP tools for search, retrieval, matching, saving, notes, deadlines, and comparison. → `src/utils/tools.js`
- Uses Zod schemas to validate tool inputs. → `src/utils/tools.js`
- Uses three Mongoose models: scholarship, saved scholarship, research note. → `src/models/`
- Implements hard eligibility filters and weighted match scoring with human-readable reasons. → `src/services/match.js`
- Serves MCP over streamable HTTP with graceful shutdown. → `src/index.js`
- Includes a research-plan prompt. → `src/mcp/prompt.js`
- Includes a scholarship record resource template. → `src/mcp/resource.js`
- Seeds a 26-record catalog from JSON. → `scripts/seed.js`, `data/scholarships.json`
- Includes a smoke test that exercises the tool surface. → `scripts/smoke-test.js`

Be careful with wording:

- “includes a smoke test” is true.
- “all tests pass” is not proven unless the test was actually run.
- “26 seeded records” is true.
- “26 real scholarships” is not proven; the data is a seeded catalog.
- “production-ready” is not proven.
- “deployed” is not proven unless there is deployment evidence.

### 6.4 False or unsupported claims for the demo

Use these in the rough draft to demonstrate the verifier:

| Claim                                           | Expected result                      | Why                                                 |
| ----------------------------------------------- | ------------------------------------ | --------------------------------------------------- |
| “Includes OAuth authentication.”                | `REJECTED` or `NEEDS EVIDENCE`       | No OAuth implementation found.                      |
| “Indexes 10,000 scholarships.”                  | `REJECTED`                           | The catalog has 26 records.                         |
| “Handles millions of users.”                    | `NEEDS EVIDENCE`                     | No traffic, load, or deployment evidence.           |
| “Reduced application time by 40%.”              | `NEEDS EVIDENCE`                     | No measurement or user study.                       |
| “Built by a team of five.”                      | `ATTESTED` only if the user confirms | Code cannot prove team size.                        |
| "Scholarship data is scraped from the internet" | REJECTED                             | the web scraping implementiaation doesn't het exist |

The demo should show at least one claim turning red and one claim turning into a question. That is the product moment.

### 6.5 What not to claim

Do not claim:

- real-world impact,
- user numbers,
- performance,
- production deployment,
- test pass status,
- team size,
- funding,
- awards,
- “first” or “only”,
- that the seeded scholarships are real awards.

These require user attestation or external evidence.

---

## 7. Product definition

### 7.1 Target user

Primary:

- a developer with finished projects but no portfolio case studies,
- especially someone whose best work is private or under NDA,
- someone preparing for interviews,
- someone who dislikes writing about themselves.

Secondary:

- bootcamp graduates,
- career switchers,
- open-source maintainers,
- students,
- freelancers who need project write-ups.

### 7.2 Job to be done

> When I finish a project, I want a case study and interview prep that are grounded in what I actually built, so I can show my work without spending a weekend writing or risking a claim I cannot defend.

### 7.3 Core promise

> A case study you can defend.

### 7.4 Product principles

1. **Evidence before prose.** No narrative before evidence cards.
2. **Fail closed.** If the evidence cannot support a claim, the claim does not ship as verified.
3. **Show the receipts.** Every verified sentence has a clickable citation.
4. **Label uncertainty.** User context is `ATTESTED`, not `VERIFIED`.
5. **Local by default.** The repo never leaves the machine.
6. **Small-model native.** The architecture works with a 1B model, not just a frontier model.
7. **Human review is the final step.** The tool produces a draft and a checklist, not a publish button.

### 7.5 Non-goals

Doxify is not:

- a portfolio website builder,
- a resume builder,
- a code review tool,
- a plagiarism detector,
- a hosting service,
- a generic README generator,
- a chatbot,
- a replacement for human judgment,
- a tool that runs the project’s tests or deploys it.

### 7.6 Success criteria

For the hackathon demo:

- One command/button starts a compile.
- The compile finishes on the 8GB CPU laptop in under 10 minutes.
- The output includes at least 6 case-study sections.
- Every generated sentence has a citation or is flagged.
- At least one false claim is caught.
- At least 5 interview questions are generated.
- Markdown export works.
- The app works with Wi-Fi off.
- The code is understandable and tested enough to defend.

---

## 8. User experience

### 8.1 The flow

1. **Landing**
   - Input: local repository path.
   - Optional: rough draft or notes.
   - Optional: target role.
   - Button: “Compile case study.”
   - Small print: “Runs locally with Gemma. Nothing leaves this machine.”

2. **Compile**
   - Stage list:
     - Validating repository
     - Scanning files
     - Reading git history
     - Building evidence cards
     - Drafting sections
     - Verifying claims
     - Preparing defense questions
     - Writing export
   - Each stage shows status and a short log line.
   - The UI is intentionally calm. This is not a slot machine.

3. **Review**
   - Three panes/tabs:
     - **Case Study** — the draft with citation chips.
     - **Evidence** — the evidence ledger, grouped by kind.
     - **Defense** — interview questions and answer outlines.
   - A summary bar:
     - `VERIFIED: n`
     - `ATTESTED: n`
     - `NEEDS EVIDENCE: n`
     - `REJECTED: n`

4. **Evidence inspector**
   - Click a citation chip.
   - See:
     - evidence title,
     - exact excerpt,
     - file path and line range,
     - commit SHA and message if applicable,
     - strength label.

5. **Gap resolution**
   - For `NEEDS EVIDENCE`, show a question:
     - “What was your role on this project?”
     - “Do you have a user count or outcome you can verify?”
     - “Was this deployed? Where?”
   - The user can:
     - answer (creates an `ATTESTED` evidence card),
     - remove the claim,
     - rewrite the claim manually.
   - Attested claims are visually distinct. They are never silently upgraded to `VERIFIED`.

6. **Defense**
   - Each question card:
     - question,
     - why an interviewer asks it,
     - 3-bullet answer outline,
     - evidence chips,
     - gap marker if the answer needs user context.

7. **Export**
   - `case-study.md`
   - `defense.md`
   - `claims.json`
   - `evidence.json`
   - Optional: copy Markdown to clipboard.

### 8.2 Visual direction

A distinctive “case file / editorial dossier” aesthetic, not a generic SaaS dashboard.

- Background: warm paper (`#f4f1ea`) with a subtle grain or ruled lines.
- Ink: near-black (`#1d1d1b`).
- Headings: serif (Georgia, Charter, or system serif).
- Body: readable serif or humanist sans.
- Evidence tags: monospace, uppercase, small, boxed.
- Status colors:
  - `VERIFIED`: deep green (`#1f6b4f`)
  - `ATTESTED`: slate blue (`#3f5f8a`)
  - `NEEDS EVIDENCE`: amber (`#9a6414`)
  - `REJECTED`: brick red (`#9b3a32`)
- Borders: thin, ink-like; avoid soft gradient cards.
- A “stamp” treatment for section headers or the final export.
- Motion: restrained. A stamp/fade when a claim is verified; no confetti.
- No emojis in the product UI.

The design should feel like a document you would trust, not a chat app.

### 8.3 Layout

Desktop:

```text
+---------------------------------------------------------------+
| Doxify          [repo path]              [Compile]         |
+----------------+-------------------------------+--------------+
| Evidence index | Case study                    | Defense      |
| E1 Stack       | # Scholarship MCP             | Q1 ...       |
| E2 Nine tools  | ...                           | Q2 ...       |
| E3 Matching    | ... [E2] [E3]                 | Q3 ...       |
| E4 ...         |                               |              |
+----------------+-------------------------------+--------------+
| VERIFIED 12 | ATTESTED 2 | NEEDS EVIDENCE 3 | REJECTED 1      |
+---------------------------------------------------------------+
```

Mobile:

- Tabs: Case Study / Evidence / Defense.
- Summary bar sticks to the top.
- Citation chips open a bottom sheet.

### 8.4 States

- **Empty:** “Choose a local git repository to compile.”
- **Invalid path:** “That path does not exist or is not a git repository.”
- **No commits:** “This repository has no commit history. The case study will rely on files only.”
- **No README:** “No README found. That is fine; evidence will come from code and commits.”
- **Model missing:** “Ollama is running, but `gemma3:1b` is not installed. Run `ollama pull gemma3:1b`.”
- **Ollama down:** “Start Ollama with `ollama serve` and try again.”
- **Model slow:** show elapsed time and a “still working” message.
- **Generation failure:** offer “retry section,” “use template fallback,” or “export evidence only.”
- **Too many files:** warn and show the file limit; allow exclusions.

### 8.5 Accessibility

- Keyboard navigation for tabs, claim chips, and gap forms.
- Visible focus rings.
- Contrast ratio at least 4.5:1 for body text.
- Status is not conveyed by color alone; include text labels.
- `prefers-reduced-motion` respected.
- Evidence excerpts are selectable and copyable.

---

## 9. Technical architecture

### 9.1 Stack

Backend:

- Python 3.14 (installed; 3.12+ minimum).
- `uv` for the virtual environment and dependency lockfile.
- FastAPI for the local API.
- Uvicorn as the ASGI server.
- Pydantic v2 for request/response models and validation.
- `httpx` for asynchronous calls to Ollama.
- Python standard library `asyncio`, `subprocess`, `pathlib`, `json`, `re`, and `tomllib` for the scanner and pipeline.
- Pytest + `pytest-asyncio` for tests.
- Mypy for type checking; Ruff for linting.

Frontend:

- Next.js with the App Router.
- React.
- TypeScript.
- npm for the frontend package.
- Plain CSS / CSS Modules; no Tailwind or component library in the MVP.
- `next.config.ts` rewrites `/api/:path*` to the FastAPI server.

Local AI:

- Ollama with `gemma3:1b`.
- Direct HTTP calls with `httpx`; no Ollama SDK, no LangChain, no vector database.

Unchanged constraints:

- No database.
- No cloud services.
- No authentication.
- No telemetry.
- No Next.js API routes; FastAPI remains the only backend.

Why this stack:

- Python 3.14 and `uv` are already installed on the target machine.
- FastAPI gives typed request/response models, validation, and an OpenAPI schema with very little glue code.
- Pydantic models keep the scanner, verifier, generator, and API contract explicit.
- Python is a good fit for subprocess-based git scanning, text processing, and deterministic verification.
- Next.js gives file-based routing, React, TypeScript, and a clean local proxy to FastAPI.
- Node 24 remains installed for Next.js, but the backend no longer depends on a Node server.
- The Ollama HTTP API is straightforward with `httpx.AsyncClient`.
- The whole app still runs locally with no cloud API, no API keys, and no per-token cost.

Why FastAPI instead of Express:

- The backend is a data pipeline first: scan files, parse git output, build evidence cards, validate claims, and write JSON. Python is a natural fit.
- Pydantic gives runtime validation and serialization without hand-writing a second schema layer.
- FastAPI exposes `/docs` and `/openapi.json` automatically, which makes the frontend contract inspectable.
- FastAPI background tasks and `asyncio` are enough for a single-user local job runner; no queue or worker infrastructure is needed.

Why Next.js instead of Vite:

- The review screen benefits from file-based routing and a clear `app/` layout.
- Next.js rewrites let the browser call `/api` on the same origin, so no CORS setup is needed.
- The frontend remains a normal React/TypeScript app; Next.js is not used for server-side business logic.

### 9.2 High-level architecture

```text
+-------------------+        +-----------------------+
| Next.js UI        |  HTTP  | FastAPI API           |
| localhost:3000    | <----> | localhost:8787        |
+-------------------+        +-----------+-----------+
                                         |
                                         | asyncio subprocess
                                         v
                              +-----------------------+
                              | Local git repo        |
                              | (read-only scan)      |
                              +-----------------------+
                                         |
                                         | evidence cards
                                         v
                              +-----------------------+
                              | Job runner            |
                              | (one job at a time)   |
                              +-----------+-----------+
                                          |
                                          | HTTP
                                          v
                              +-----------------------+
                              | Ollama                |
                              | gemma3:1b             |
                              +-----------------------+
```

The Next.js dev server proxies `/api/*` to `http://127.0.0.1:8787/api/*` through `next.config.ts`. The FastAPI process does the scanning, generation, verification, and export. Next.js is only the UI layer.

### 9.3 Directory structure

```text
doxify/
├── PLAN.md
├── README.md
├── LICENSE
├── Makefile
├── .gitignore
├── scripts/
│   └── dev.sh
├── server/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── sessions.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── repo.py
│   │   │   ├── scanner.py
│   │   │   ├── evidence.py
│   │   │   ├── retrieval.py
│   │   │   ├── generator.py
│   │   │   ├── verifier.py
│   │   │   ├── defense.py
│   │   │   ├── exporter.py
│   │   │   ├── redact.py
│   │   │   ├── ollama.py
│   │   │   └── jobs.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── system.py
│   │       ├── section.py
│   │       ├── repair.py
│   │       └── defense.py
│   └── tests/
│       ├── test_citation.py
│       ├── test_verifier.py
│       ├── test_evidence.py
│       └── fixtures/
├── web/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── CompileForm.tsx
│   │   ├── StageList.tsx
│   │   ├── CaseStudy.tsx
│   │   ├── EvidencePane.tsx
│   │   ├── DefensePane.tsx
│   │   ├── ClaimChip.tsx
│   │   └── SummaryBar.tsx
│   └── lib/
│       ├── api.ts
│       └── types.ts
├── shared/
│   └── openapi.json
└── demo/
    └── scholarship-mcp/
        ├── evidence.json
        ├── claims.json
        ├── case-study.md
        └── defense.md
```

The exact structure can change, but the separation should remain:

- `server/` — FastAPI app, scanning, generation, verification, export, pytest tests.
- `web/` — Next.js review UI, API client, and TypeScript mirror types.
- `shared/` — optional OpenAPI snapshot for contract review; no shared runtime package.
- `demo/` — precomputed output for judges.
- `scripts/` + `Makefile` — local developer commands that start both services.

The backend Pydantic models in `server/app/models.py` are the source of truth. The frontend mirrors the JSON shape in `web/lib/types.ts`. If time allows, generate the TypeScript types from FastAPI's `/openapi.json` with `openapi-typescript`; for the MVP, a hand-maintained mirror is acceptable and easier to debug.

Planned `Makefile` targets:

```text
make install    # (cd server && uv sync) && (cd web && npm install)
make api        # cd server && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
make web        # cd web && npm run dev
make dev        # run api and web together via scripts/dev.sh
make test       # cd server && uv run pytest
make typecheck  # (cd server && uv run mypy app) && (cd web && npm run typecheck)
make build      # cd web && npm run build
```

### 9.4 Runtime and ports

- FastAPI: `http://127.0.0.1:8787`
- Next.js dev server: `http://127.0.0.1:3000`
- Ollama: `http://127.0.0.1:11434`

The FastAPI server must bind to `127.0.0.1`, not `0.0.0.0`. Next.js should also bind to `127.0.0.1` for the local demo.

`next.config.ts` rewrites `/api/:path*` to `http://127.0.0.1:8787/api/:path*`. This keeps the browser on one origin and avoids a CORS package or permissive CORS middleware. The frontend calls relative `/api/...` URLs.

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8787/api/:path*",
      },
    ];
  },
};

export default nextConfig;
```

### 9.5 Job model

Compiles can take minutes on a CPU. Do not block a single HTTP request for the whole compile.

Use a single-process FastAPI job manager with one active job at a time:

- `POST /api/sessions` validates the request and creates the session directory.
- The route starts a background coroutine with `asyncio.create_task`.
- A module-level `asyncio.Semaphore(1)` or a small `asyncio.Queue` worker prevents concurrent compiles.
- The job manager writes stage transitions to `job.json`.
- No Celery, Redis, or external queue is needed.

Job states:

```text
queued
validating
scanning
extracting
drafting
verifying
defense
exporting
done
error
```

Persist job state to:

```text
.doxify/sessions/<session-id>/job.json
```

This allows the UI to reconnect and provides a debugging trail.

The job runner should emit stage updates and log lines. The UI polls every 1 second.

### 9.6 API

Suggested endpoints:

```text
GET  /api/health
GET  /api/model/health

POST /api/sessions
  body: { repoPath: string, roughDraft?: string, targetRole?: string }
  response: { sessionId: string }

GET  /api/sessions/:id
  response: { job: Job, result?: CompileResult }

GET  /api/sessions/:id/evidence
GET  /api/sessions/:id/claims
GET  /api/sessions/:id/export?format=markdown
POST /api/sessions/:id/attest
  body: { claimId: string, answer: string }
POST /api/sessions/:id/claims/:claimId/remove
POST /api/sessions/:id/claims/:claimId/rewrite
  body: { text: string }
```

For the MVP, `POST /api/sessions` can synchronously return after validation, then the job runs in the background. The UI polls `GET /api/sessions/:id`.

All request and response bodies are Pydantic models in `server/app/models.py`. FastAPI serves interactive docs at `/docs` and the OpenAPI schema at `/openapi.json`. Use Pydantic's `alias_generator=to_camel` (with `populate_by_name=True`) so Python stays snake_case internally while the JSON API keeps the camelCase shape the Next.js client expects (`repoPath`, `sessionId`, `evidenceIds`, and so on).

### 9.7 Session storage

```text
.doxify/
└── sessions/
    └── <session-id>/
        ├── job.json
        ├── repo.json
        ├── evidence.json
        ├── claims.json
        ├── case-study.json
        ├── case-study.md
        ├── defense.json
        └── defense.md
```

Do not store the repository contents beyond the session. Do not copy the repo. Evidence excerpts are short and local.

---

## 10. Data contracts

The backend Pydantic models in `server/app/models.py` are the source of truth. They validate API input/output and are serialized to camelCase JSON with `alias_generator=to_camel`.

The TypeScript interfaces below are the frontend mirror in `web/lib/types.ts`. They document the JSON payload shape the Next.js client consumes. Keep them in sync with the Pydantic models. If time allows, generate them from `/openapi.json` with `openapi-typescript` instead of maintaining them by hand.

### 10.1 Evidence card

```ts
type EvidenceStrength =
  | "deterministic"
  | "code"
  | "commit"
  | "readme"
  | "attested";

type EvidenceKind =
  | "metric"
  | "stack"
  | "file"
  | "code"
  | "commit"
  | "test"
  | "deploy"
  | "readme"
  | "attested";

interface EvidenceRef {
  path?: string;
  lines?: string;
  commit?: string;
  url?: string;
}

interface EvidenceCard {
  id: string; // E1, E2, ...
  kind: EvidenceKind;
  title: string; // short human label
  text: string; // factual statement
  quote?: string; // exact excerpt, never model-generated
  refs: EvidenceRef[];
  strength: EvidenceStrength;
  keywords: string[]; // for retrieval
  meta?: Record<string, string | number | boolean>;
}
```

Rules:

- `quote` must be copied from the repo or git output.
- `text` is a short, factual description written by deterministic code, not the model.
- `strength` controls how the claim can be used.
- `attested` cards are created only from user input.

### 10.2 Claim

```ts
type ClaimStatus = "verified" | "attested" | "needs_evidence" | "rejected";

interface Claim {
  id: string; // C1, C2, ...
  text: string; // sentence from the draft
  sectionId: string;
  evidenceIds: string[];
  status: ClaimStatus;
  reason?: string; // why it was flagged
  gapQuestion?: string; // question for the user
  userAnswer?: string; // attested context
}
```

Status meanings:

- `verified` — the claim has at least one valid citation, keyword overlap with the cited evidence, and no numeric contradiction.
- `attested` — the claim relies on user-provided context. It is labeled and never presented as code-verified.
- `needs_evidence` — the claim may be true, but the repo does not support it yet.
- `rejected` — the claim is contradicted by evidence, or cites evidence that does not contain the claim.

### 10.3 Case-study section

```ts
interface CaseStudySentence {
  text: string;
  claimId: string;
  evidenceIds: string[];
}

interface CaseStudySection {
  id: string;
  title: string;
  sentences: CaseStudySentence[];
}
```

### 10.4 Defense question

```ts
interface DefenseQuestion {
  id: string;
  question: string;
  whyAsked: string;
  answerOutline: string[];
  evidenceIds: string[];
  gap?: string;
}
```

### 10.5 Compile result

```ts
interface CompileResult {
  sessionId: string;
  repo: {
    path: string;
    name: string;
    commitCount: number;
    firstCommitDate?: string;
    lastCommitDate?: string;
    hasReadme: boolean;
    languages: string[];
  };
  evidence: EvidenceCard[];
  claims: Claim[];
  sections: CaseStudySection[];
  defense: DefenseQuestion[];
  summary: {
    verified: number;
    attested: number;
    needsEvidence: number;
    rejected: number;
  };
}
```

---

## 11. Pipeline details

### 11.1 Stage 0 — Validate repository

Checks:

- path exists,
- path is a directory,
- path contains `.git`,
- `git rev-parse --is-inside-work-tree` succeeds,
- path is not the tool’s own repo (avoid recursive weirdness),
- path is not `/`, home directory, or a massive directory.

Reject with a clear error.

Do not accept URLs in the MVP. Local paths only. This keeps the privacy story simple.

### 11.2 Stage 1 — Scan

Use `git` commands with `asyncio.create_subprocess_exec` (argument lists, no shell), or `subprocess.run([...])` in a worker thread for short blocking calls. Never build a shell string and never use `shell=True`.

Collect:

- `git log --reverse --pretty=format:%H|%ad|%s --date=short`
- `git log --numstat --pretty=format:...`
- `git ls-files`
- `git shortlog -sne` (optional, but do not infer team size from it)
- first and last commit dates
- commit count
- file count
- language counts by extension
- README presence
- manifest presence
- test file presence
- CI/deploy config presence

Skip:

- `.git/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `node_modules/`
- `vendor/`
- `dist/`
- `build/`
- `.next/`
- `coverage/`
- lockfiles for evidence extraction (`package-lock.json`, `pnpm-lock.yaml`, `uv.lock`, `poetry.lock`)
- binary files
- files larger than 100 KB for excerpting
- minified files
- generated files where detectable

Limits:

- max 5,000 tracked files for analysis,
- max 200 files read for excerpts,
- max 20 commits summarized,
- max 50 evidence cards.

If the repo exceeds limits, warn and continue with the most relevant files.

### 11.3 Stage 2 — Build evidence cards

Evidence categories:

1. **Project identity**
   - repo name,
   - primary language,
   - file count,
   - commit count,
   - date span,
   - README presence.

2. **Stack**
   - `package.json` dependencies,
   - `pyproject.toml`, `requirements.txt`,
   - `go.mod`, `Cargo.toml`,
   - `Dockerfile`, `docker-compose.yml`,
   - framework-specific config files.

3. **Architecture**
   - top-level directories,
   - entry points,
   - route files,
   - service files,
   - model files,
   - MCP tool/prompt/resource files,
   - notable module names.

4. **Features**
   - route names,
   - tool names,
   - exported functions,
   - CLI commands,
   - API endpoints,
   - README headings if present.

5. **Tests**
   - test files,
   - test scripts,
   - CI workflows.
   - Do not claim tests pass unless they were run.

6. **Deployment**
   - Dockerfile,
   - Render/Fly/Vercel/Netlify config,
   - GitHub Actions deploy steps.
   - Do not claim deployment unless evidence shows a deployment artifact or URL.

7. **Timeline**
   - first commit,
   - last commit,
   - active days,
   - notable commit subjects.

8. **Decisions**
   - commit subjects containing `feat`, `refactor`, `fix`, `chore`,
   - code comments that state constraints or tradeoffs,
   - README “Why” sections if present.

9. **Metrics**
   - counts only: commits, files, tools, models, routes, tests, records.
   - No inferred users, revenue, latency, or impact.

Each card gets:

- a stable ID,
- a short title,
- a factual text,
- an exact quote if available,
- refs,
- keywords for retrieval.

Example cards for `scholarship-mcp`:

```json
{
  "id": "E1",
  "kind": "metric",
  "title": "Twenty commits over three days",
  "text": "The repository has 20 commits between 2026-09-12 and 2026-09-14.",
  "refs": [{ "commit": "b7f326a" }],
  "strength": "deterministic",
  "keywords": ["commits", "timeline", "history"]
}
```

```json
{
  "id": "E2",
  "kind": "code",
  "title": "Nine registered MCP tools",
  "text": "src/utils/tools.js defines nine MCP tools for search, retrieval, matching, saving, notes, deadlines, and comparison.",
  "quote": "export const TOOLS = [ ... ]",
  "refs": [{ "path": "src/utils/tools.js", "lines": "31-192" }],
  "strength": "code",
  "keywords": ["tools", "mcp", "search", "match", "save"]
}
```

### 11.4 Stage 3 — Retrieve evidence per section

No embeddings in the MVP.

Use keyword overlap:

- tokenize section intent and evidence text,
- remove stopwords,
- score by shared content words,
- boost exact path/name matches,
- take the top 6 cards.

Section intents:

- Snapshot: identity, stack, purpose.
- Problem: README context, commit messages, project description; if absent, use neutral framing.
- Architecture: stack, entry points, directories, models, tools.
- Hard problem: matching logic, validation, refactors, fixes.
- What shipped: features, tools, routes, tests.
- Evidence/outcome: metrics, tests, deploy config.
- Reflection: gaps, missing README, next steps.

The same evidence card can appear in multiple sections.

### 11.5 Stage 4 — Generate sections

Generate one section per model call.

Why:

- a 1B model has a small reliable working set,
- short prompts are faster,
- a failed section can be retried without redoing everything,
- citations are easier to validate per section.

Prompt contract:

- input: section title, section goal, 6 evidence cards, project name,
- output: 2–4 paragraphs, 1–3 sentences each,
- every sentence ends with one or more citation tokens: `[E2]` or `[E2][E5]`,
- no invented numbers,
- no claims about impact, users, tests passing, or deployment unless the evidence card explicitly says so,
- if evidence is insufficient, write a sentence with `[GAP]` and a question for the user.

The generator should be conservative. Under-writing is better than overclaiming.

### 11.6 Stage 5 — Verify claims

Parse each generated sentence.

For each sentence:

1. Extract citation tokens.
2. If no citation:
   - mark `needs_evidence`,
   - generate a gap question.
3. If citations reference unknown IDs:
   - mark `rejected`,
   - reason: invalid citation.
4. If citations exist:
   - concatenate the cited evidence text and quotes,
   - compute keyword overlap with the claim,
   - if overlap is below threshold:
     - mark `needs_evidence` or `rejected` depending on severity,
     - reason: citation does not support the claim.
5. If the claim contains numbers:
   - check those numbers against the cited evidence and computed metrics,
   - if a number is contradicted:
     - mark `rejected`,
     - reason: numeric contradiction.
6. If the claim asserts one of the forbidden categories:
   - tests passing,
   - deployment,
   - user count,
   - performance,
   - revenue,
   - team size,
   - awards,
   - “first/only”,
   - and the cited evidence does not explicitly support it:
     - mark `needs_evidence`,
     - ask for attestation.
7. Otherwise:
   - mark `verified`.

The verifier is deterministic. No second LLM is required for the MVP.

Optional second pass:

- ask the model to classify claim vs. evidence as supported/unsupported,
- use only as a tie-breaker,
- never let the model upgrade a deterministic failure.

### 11.7 Stage 6 — Defense pack

For each section, generate 1–2 questions.

Question generation prompt:

- input: verified claims + evidence cards,
- output:
  - question,
  - why an interviewer asks it,
  - 3-bullet answer outline,
  - evidence IDs,
  - gap if the answer needs user context.

The model should ask questions that test understanding, not trivia:

- Why this design?
- What tradeoff did you make?
- How does this handle failure?
- How did you test it?
- What would you change?
- What did you measure?

Do not invent metrics or outcomes in the answer outline.

### 11.8 Stage 7 — Export

Write:

- `case-study.md`
- `defense.md`
- `claims.json`
- `evidence.json`

Markdown case study structure:

```md
# <Project name>: <subtitle>

> Evidence-backed case study compiled locally with Doxify.

## Snapshot

...

## The problem

...

## The approach

...

## Architecture

...

## The hard part

...

## What shipped

...

## Evidence

...

## What I would change

...

## Evidence appendix

- [E1] ...
- [E2] ...
```

Defense Markdown structure:

```md
# Interview defense pack: <Project name>

## Q1. ...

**Why this comes up:** ...
**Answer outline:**

- ...
- ...
- ...
  **Evidence:** [E2], [E5]
  **Gap:** ...
```

### 11.9 Template fallback

If the model fails or returns malformed output:

- use a section template that stitches evidence cards into neutral prose,
- mark the section as `template_fallback`,
- keep citations,
- let the user edit.

This guarantees the demo works even if the 1B model is slow or inconsistent.

Example fallback:

```md
## Snapshot

<Project> is a <stack> project with <N> commits and <M> tracked files [E1][E2]. The repository includes <features> [E3].
```

The fallback should be honest and boring, not fake.

---

## 12. Prompt design

### 12.1 System prompt

```text
You are a technical portfolio editor working inside a compiler.

You will receive evidence cards and a section goal. You may only use the
evidence cards provided. You must cite evidence for every sentence using
tokens like [E1] or [E2][E5].

Rules:
- Never invent a number, user count, performance result, team size, or
  deployment status.
- Never claim tests pass, a project is production-ready, or a project is
  deployed unless an evidence card explicitly says so.
- If the evidence is insufficient, write a short gap sentence and mark it
  [GAP], followed by a question for the user.
- Prefer concrete, plain language over marketing language.
- Do not use phrases like "revolutionary", "seamless", "cutting-edge", or
  "game-changing".
- Write in first person when describing the developer's work.
- Keep sentences short.
```

### 12.2 Section prompt

```text
Section: {{sectionTitle}}
Goal: {{sectionGoal}}
Project: {{projectName}}

Evidence cards:
{{evidenceCards}}

Write 2-4 paragraphs for this section.
Each sentence must end with one or more citation tokens.
If a sentence cannot be supported, write it as a [GAP] question instead.
Return only the section text.
```

### 12.3 Repair prompt

```text
The previous output had these problems:
{{problems}}

Rewrite the section using only the evidence cards below.
Every sentence must cite evidence.
Do not add new claims.
```

### 12.4 Defense prompt

```text
You are preparing a developer for a technical interview about this project.

Using only the claims and evidence below, write 1-2 interview questions.
For each question, provide:
- the question,
- why an interviewer would ask it,
- a 3-bullet answer outline,
- the evidence IDs that support the answer,
- a gap if the answer needs information not present in the evidence.

Do not invent outcomes or metrics.
Return JSON with this shape:
{
  "questions": [
    {
      "question": "...",
      "whyAsked": "...",
      "answerOutline": ["...", "...", "..."],
      "evidenceIds": ["E2", "E5"],
      "gap": "..."
    }
  ]
}
```

If the 1B model cannot produce reliable JSON, use a Markdown format and parse it with a small tolerant parser. The MVP should prefer the format the model can follow.

### 12.5 Model settings

Suggested Ollama options:

```json
{
  "model": "gemma3:1b",
  "stream": false,
  "options": {
    "temperature": 0.2,
    "top_p": 0.9,
    "num_ctx": 4096,
    "num_predict": 400,
    "repeat_penalty": 1.1
  }
}
```

Practical notes:

- Run one generation at a time.
- Keep prompts under 4k tokens.
- Limit evidence cards to 6 per call.
- Use 2–4 paragraphs per section.
- Retry once with a shorter prompt if the output is malformed.
- If the model is too slow, reduce the number of sections.

### 12.6 Why not a larger model

The target laptop has 8GB RAM and no useful GPU. `gemma3:1b` is already installed and is about 806MB. A larger model would be slower and may not fit comfortably.

The architecture is designed to work with a small model:

- deterministic extraction does the facts,
- retrieval does the context selection,
- the model does short rewriting,
- deterministic verification does the trust.

This is a feature, not a compromise. The DEV post should explain it.

---

## 13. Verification rules

### 13.1 Evidence hierarchy

1. **Deterministic metrics** — counts, dates, file existence, command output. Strongest.
2. **Exact code excerpts** — strong for structure and stated behavior.
3. **Commit messages** — strong for the author’s stated intent, not for runtime behavior.
4. **README statements** — medium; they are author claims, not proof.
5. **User attestation** — labeled; not code-verified.
6. **Model inference** — never shown as evidence.

### 13.2 What code can prove

- a file exists,
- a function/route/tool name exists,
- a dependency is listed,
- a model/schema exists,
- a test file exists,
- a count of records in a data file,
- a commit exists with a message and date,
- a deployment config file exists.

### 13.3 What code cannot prove

- that tests pass,
- that the app is deployed,
- that users exist,
- that performance is good,
- that the project is secure,
- that the project is “production-ready”,
- that a team size is accurate,
- that an award is real,
- that an outcome was achieved.

These require attestation or external evidence. Doxify must say so.

### 13.4 Claim examples

| Claim                            | Verdict        | Reason                                           |
| -------------------------------- | -------------- | ------------------------------------------------ |
| “Exposes nine MCP tools.”        | verified       | Counted from `src/utils/tools.js`.               |
| “Uses Zod for input validation.” | verified       | Import and schema usage in `src/utils/tools.js`. |
| “Has a smoke test.”              | verified       | `scripts/smoke-test.js` exists.                  |
| “All tests pass.”                | needs evidence | The tool did not run the tests.                  |
| “Includes OAuth.”                | rejected       | No OAuth implementation found.                   |
| “Indexes 10,000 scholarships.”   | rejected       | Catalog has 26 records.                          |
| “Handles millions of users.”     | needs evidence | No traffic or deployment evidence.               |
| “I led a team of five.”          | attested       | Code cannot prove team size.                     |

### 13.5 Gap questions

When a claim needs evidence, generate a specific question, not a generic one.

Good:

- “What was your role on this project?”
- “Do you have a verifiable user count or outcome?”
- “Was this deployed? Where?”
- “Did you run the test suite? What was the result?”

Bad:

- “Tell me more.”
- “Add evidence.”
- “Is this true?”

Specific questions are easier to answer and produce better attestations.

### 13.6 Attestation rules

- Attestations are stored separately from code evidence.
- Attestations are labeled `ATTESTED`.
- Attestations can support a claim, but the claim remains `ATTESTED`, not `VERIFIED`.
- The UI should show a small “user statement” badge.
- The exported case study should include a note:
  - “Claims marked ATTESTED are based on the author’s statement, not code evidence.”

This is honest and still useful.

---

## 14. Defense pack

### 14.1 Why it exists

The case study is only half the job. The other half is the interview.

Most portfolio tools stop at the document. Doxify continues into the conversation.

### 14.2 Question types

- **Design choice:** Why MCP instead of a REST API?
- **Tradeoff:** Why separate hard filters from soft scoring?
- **Failure mode:** What happens if MongoDB is down?
- **Testing:** How did you test the tool surface?
- **Scope:** What did you deliberately not build?
- **Reflection:** What would you change before production?
- **Evidence:** Which part of the repo proves this claim?

### 14.3 Answer outline rules

- 3 bullets max.
- Each bullet ties to evidence or a labeled gap.
- No invented metrics.
- If the answer needs user context, show a gap.
- The outline is a rehearsal aid, not a script.

### 14.4 Example questions for scholarship-mcp

1. Why expose this as an MCP server instead of a normal REST API?
2. How does the matching engine prevent ineligible scholarships from being recommended?
3. Why separate hard eligibility filters from soft scoring?
4. How does the smoke test exercise the tool surface?
5. What happens if the database is unavailable at startup?
6. What would you change before using this with real scholarship data?

These questions are grounded in the actual code and are likely to come up in an interview.

---

## 15. Export

### 15.1 Markdown case study

The primary export is Markdown because:

- it is portable,
- it fits a portfolio site, GitHub, DEV, or Notion,
- it is easy to edit,
- it does not require a template engine.

### 15.2 Evidence appendix

Append a compact evidence list:

```md
## Evidence appendix

- **E1** — Twenty commits over three days. `git log`, 2026-09-12 to 2026-09-14.
- **E2** — Nine registered MCP tools. `src/utils/tools.js:31-192`.
- **E3** — Three Mongoose models. `src/models/`.
- **E4** — Hard filters and weighted scoring. `src/services/match.js`.
- **E5** — Smoke test. `scripts/smoke-test.js`.
```

### 15.3 Claims JSON

The claims JSON is the machine-readable ledger. It is useful for:

- debugging,
- future integrations,
- showing the verification result in the UI,
- proving the tool is not just a text generator.

### 15.4 Optional HTML export

Stretch goal only. Do not build it until the core works.

If time allows, export a single self-contained HTML file with the same dossier aesthetic. This would be a nice portfolio artifact, but Markdown is enough for the hackathon.

---

## 16. Security and privacy

### 16.1 Local-only guarantees

- API binds to `127.0.0.1`.
- No telemetry.
- No analytics.
- No cloud API calls.
- No GitHub OAuth.
- No repository upload.
- Only network call: `http://127.0.0.1:11434` for Ollama.
- The app should work with Wi-Fi off.

### 16.2 Path safety

- Resolve the repo path with `pathlib.Path.resolve(strict=True)` and verify it is a directory.
- Reject `/`, the home directory, and the tool’s own repo.
- Reject paths outside the user’s selected root if a root is configured.
- Do not follow symlinks outside the repo.
- Use `asyncio.create_subprocess_exec("git", [...])` or `subprocess.run(["git", ...])`, never string interpolation into a shell and never `shell=True`.

### 16.3 Secret handling

Skip or redact:

- `.env`, `.env.*`
- `*.pem`, `*.key`, `*.p12`
- files with names containing `secret`, `credential`, `token`
- AWS keys, GitHub tokens, private keys, generic high-entropy strings
- database connection strings
- user-specified exclusion terms

Redaction should happen before evidence cards are created, not just before display.

Add a visible note:

> Doxify skips common secret files, but it is not a security scanner. Review the exported case study before publishing.

### 16.4 Output safety

The exported case study may contain:

- file paths,
- architecture details,
- code excerpts,
- commit messages.

The user must review it before publishing. The app should show a confirmation screen:

> This export contains excerpts from your repository. Review it before sharing.

### 16.5 Model safety

- The model never receives the whole repo.
- The model receives short evidence cards.
- The model output is treated as untrusted text.
- The verifier checks citations before display.
- The app does not execute model-generated code.

---

## 17. Build schedule

The schedule assumes evenings and a full weekend. Adjust if needed, but protect the core.

### 17.1 Thursday, October 22 — Foundation

Goals:

- create the project scaffold,
- define Pydantic models and the TypeScript mirror,
- implement repository validation,
- implement git scanning,
- implement evidence extraction,
- implement Ollama health check,
- build a minimal UI that shows evidence cards.

Acceptance criteria:

- `make dev` starts FastAPI and Next.js.
- Entering `scholarship-mcp` produces `evidence.json`.
- Evidence includes 20 commits, 9 tools, 3 models, 26 records, no README.
- The UI lists evidence cards.
- The app handles an invalid path gracefully.
- `ollama list` shows `gemma3:1b`.

Do not start generation until evidence extraction is solid.

### 17.2 Friday, October 23 — Generation and verification

Goals:

- job runner,
- section retrieval,
- section generation with citation tokens,
- citation parser,
- deterministic verifier,
- claim ledger,
- case-study UI with claim chips,
- Markdown export v1.

Acceptance criteria:

- A compile produces at least 5 sections.
- Every sentence has a citation or a gap.
- The false claims “OAuth” and “10,000 scholarships” are rejected or flagged.
- The true claims about 9 tools and 26 records are verified.
- The UI shows summary counts.
- Export writes `case-study.md`.

If the model is too slow, use template fallback for one section and keep the pipeline working end to end.

### 17.3 Saturday, October 24 — Defense, polish, tests

Goals:

- defense question generation,
- attestation flow,
- claim removal/rewrite,
- evidence inspector,
- export `defense.md` and `claims.json`,
- UI polish,
- unit tests,
- precomputed demo folder,
- README v1.

Acceptance criteria:

- At least 5 defense questions are generated.
- A gap claim can be answered and becomes `ATTESTED`.
- The UI is usable with keyboard only.
- `cd server && uv run pytest` passes.
- `cd server && uv run mypy app` passes.
- `cd web && npm run typecheck` passes.
- The precomputed demo contains all four export files.
- A fresh clone can run the app.

### 17.4 Sunday, October 25 — Demo, write-up, submit

Goals:

- record the demo video,
- write the DEV post,
- finish README,
- final QA,
- submit.

Acceptance criteria:

- Video is 3–5 minutes and shows the full flow.
- Video shows Wi-Fi off and a successful local compile.
- DEV post uses the challenge template and `#hf26challenge`.
- DEV post explains why open innovation matters.
- Repo is public and licensed.
- Submission is posted before the deadline.
- Deadline buffer: submit by Sunday night, not Monday morning.

### 17.5 If time slips

Cut in this order:

1. Optional HTML export.
2. Attestation flow (leave a “coming next” note).
3. Redaction beyond `.env`/key files.
4. Defense questions from 6 to 4.
5. Case study sections from 7 to 5.
6. UI polish.

Do not cut:

- evidence extraction,
- citations,
- verifier,
- false-claim demo,
- local Ollama,
- Markdown export,
- DEV post.

---

## 18. Testing

### 18.1 Unit tests

Use `pytest` (with `pytest-asyncio` for async pipeline tests). FastAPI route tests can use `fastapi.testclient.TestClient`, which uses `httpx` under the hood.

Test:

- citation token parsing (`[E1]`, `[E2][E5]`),
- invalid citation detection,
- keyword overlap scoring,
- numeric contradiction detection,
- forbidden-claim detection,
- secret path skipping,
- path validation,
- evidence card ID generation,
- summary counts.

### 18.2 Integration tests

Run the scanner against `scholarship-mcp` and assert:

- commit count is 20,
- first commit date is 2026-09-12,
- last commit date is 2026-09-14,
- README is absent,
- tool count is 9,
- model count is 3,
- scholarship record count is 26,
- smoke test is present.

These assertions are specific to the demo and should live in an integration test or a demo validation script, not in the core unit tests.

### 18.3 End-to-end test

With Ollama running:

1. create a session for `scholarship-mcp`,
2. wait for `done`,
3. assert at least 5 sections,
4. assert at least one verified claim,
5. assert “OAuth” is not verified,
6. assert “10,000” is not verified,
7. assert defense questions exist,
8. assert Markdown export exists.

If Ollama is not available, skip the E2E test with a clear message.

### 18.4 Manual QA

- Invalid path.
- Non-git directory.
- Repo with no commits.
- Repo with no README.
- Repo with a very large file.
- Repo with a `.env` file.
- Ollama down.
- Model missing.
- Browser refresh during compile.
- Export with `NEEDS EVIDENCE` claims.
- Attestation flow.
- Keyboard navigation.
- Mobile layout.
- Wi-Fi off.

### 18.5 Performance

Measure:

- scan time,
- evidence extraction time,
- generation time per section,
- total compile time.

Target: under 10 minutes on the 8GB CPU laptop.

If over 15 minutes:

- reduce sections,
- reduce evidence cards per section,
- reduce `num_predict`,
- use template fallback for the longest section.

### 18.6 Fresh clone test

Before submission:

```bash
git clone <repo> /tmp/doxify-test
cd /tmp/doxify-test

# Backend
cd server
uv sync
uv run pytest
uv run mypy app
cd ..

# Frontend
cd web
npm install
npm run typecheck
npm run build
cd ..

# Both services
make dev
```

Then compile a sample repo. Fix anything that only works in the original directory.

---

## 19. Demo video

Target length: 3–5 minutes.

### 19.1 Shot list

**0:00–0:20 — Hook**

- Show `scholarship-mcp` in the terminal.
- `git log --oneline | wc -l` → 20.
- `ls README.md` → missing.
- Say: “I built this in a weekend. I never wrote it up.”

**0:20–0:50 — The problem**

- Show a generic AI-generated case study with confident but unverifiable claims.
- Say: “This is the kind of thing that gets you destroyed in an interview.”

**0:50–1:20 — Start the compile**

- Open Doxify.
- Enter the repo path.
- Paste a rough draft with:
  - “Includes OAuth authentication.”
  - “Indexes 10,000 scholarships.”
- Click “Compile.”
- Show the stage list.

**1:20–2:20 — Evidence and draft**

- Show evidence cards: 20 commits, 9 tools, 3 models, 26 records, no README.
- Show the generated case study.
- Click a citation chip.
- Show the exact file and commit.
- Show the “OAuth” claim rejected.
- Show the “10,000” claim rejected with the 26-record evidence.
- Say: “The model writes; the compiler checks.”

**2:20–3:10 — Defense pack**

- Show interview questions.
- Read one question and its answer outline.
- Show a gap question.
- Answer it; show the claim become `ATTESTED`.
- Say: “It prepares you for the conversation, not just the document.”

**3:10–3:40 — Local proof**

- Turn off Wi-Fi.
- Compile again or show the model running locally.
- Show `ollama ps` or the local model call.
- Say: “No API keys, no upload, no per-token cost.”

**3:40–4:00 — Close**

- Show the export.
- Show the claim ledger.
- Say: “A case study you can defend.”

### 19.2 Recording notes

- Record at 1080p if possible; 720p is acceptable.
- Use a clean browser profile.
- Hide personal notifications.
- Use a large font in the terminal.
- Keep the mouse movements deliberate.
- Do not claim anything the demo does not show.
- If the compile is slow, cut the waiting and add a timestamp overlay.

---

## 20. DEV post

### 20.1 Title options

1. “I had 20 commits and no README. I built a local Gemma tool that writes a portfolio case study—and refuses to lie.”
2. “Most AI portfolio tools write stories. Mine checks the receipts first.”
3. “Doxify: a local-first portfolio case study compiler that runs on a 1B model.”
4. “I built a case study compiler that says ‘I can’t prove that’ before it says ‘I built this.’”

Use option 1 or 2 for the submission. They are specific and hook the reader.

### 20.2 Outline

**1. Hook**

- 20 commits.
- No README.
- A portfolio that never got written.
- Every AI tool wanted to write confident copy.
- The problem: confidence is not defensibility.

**2. What I built**

- Doxify.
- Local-first case study compiler.
- Input: local repo.
- Output: cited case study + claim ledger + defense pack.

**3. The demo**

- `scholarship-mcp`.
- 9 MCP tools, 3 models, 26 records, no README.
- Show a false claim being rejected.
- Show a true claim being cited.

**4. How it works**

- Scan.
- Evidence cards.
- Retrieve 6 cards per section.
- Generate with citation tokens.
- Verify deterministically.
- Ask gap questions.
- Generate defense questions.

Include a simple diagram.

**5. The hard part**

- Making a 1B model trustworthy.
- The model cannot hold the repo.
- Deterministic facts + small prompts + citation grammar + fail-closed checks.
- Template fallback.

**6. Why open innovation matters**

- Private repos and career claims.
- No upload, no API keys, no per-token cost.
- Offline.
- Model portability.
- Inspectable code.

**7. The lazy payoff**

- The user does not have to write from scratch.
- The compile runs while they do something else.
- They return to a draft and a checklist.
- “Slow and steady” means the tool is patient and careful, not instant and sloppy.

**8. What I would do next**

- More languages.
- Better semantic verification.
- HTML export.
- Repo comparison.
- Interview practice mode.

**9. My Agent Session**

- Document how the project was built with AI assistance.
- Be transparent about what the agent did and what was manually verified.
- Include the key prompts or decisions.
- Do not overclaim.

**10. Links**

- Repo.
- Demo video.
- Precomputed demo.
- Setup instructions.

### 20.3 Writing rules

- Use first person.
- Be specific.
- Show the false claim rejection.
- Include at least 3 screenshots.
- Include a code snippet of the citation grammar or verifier.
- Do not use “revolutionary,” “seamless,” or “game-changing.”
- Explain the limitations honestly.
- Mention the 8GB laptop and the 1B model.
- Mention that the tool is not a security scanner.
- Mention that attestations are labeled.

### 20.4 Tags

- `#hf26challenge`
- `#hacktoberfest`
- `#opensource`
- `#ai`
- `#gemma`
- `#ollama`
- `#portfolio`
- `#career`

Use the challenge template and tag exactly as required.

---

## 21. Submission checklist

Before submitting:

- [ ] New public repository created during the entry period.
- [ ] `README.md` explains setup, usage, architecture, and limitations.
- [ ] `LICENSE` added (MIT).
- [ ] `.gitignore` excludes `.doxify/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `node_modules/`, `.next/`, and secrets.
- [ ] No `.env` or credentials committed.
- [ ] `cd server && uv sync` works from a fresh clone.
- [ ] `cd web && npm install` works from a fresh clone.
- [ ] `cd server && uv run mypy app` passes.
- [ ] `cd web && npm run typecheck` passes.
- [ ] `cd server && uv run pytest` passes.
- [ ] `cd web && npm run build` passes.
- [ ] `make dev` starts the app.
- [ ] Ollama setup is documented.
- [ ] `gemma3:1b` is named explicitly.
- [ ] The demo uses `scholarship-mcp` or another local repo.
- [ ] Precomputed demo files are included.
- [ ] Demo video is recorded and uploaded.
- [ ] Video shows local/offline operation.
- [ ] DEV post is published with the challenge template.
- [ ] DEV post uses `#hf26challenge`.
- [ ] DEV post links to the repo and video.
- [ ] DEV post explains why open innovation matters.
- [ ] The project does not claim tests pass or deployment unless proven.
- [ ] The project does not claim real scholarships or real users.
- [ ] Submission is posted before 2026-10-26 7:59 AM WAT.

---

## 22. Risks and mitigations

### 22.1 The 1B model writes weak prose

Mitigation:

- evidence cards do most of the factual work,
- section prompts are short,
- template fallback exists,
- the user can edit,
- the value is verification, not literary quality.

### 22.2 The 1B model is slow

Mitigation:

- one job at a time,
- 4k context,
- 6 evidence cards,
- 400 output tokens,
- 5–7 sections,
- show progress,
- cut sections if needed.

### 22.3 RAM is tight

Observed: about 1.0Gi available and 4.6Gi swap used at planning time.

Mitigation:

- close heavy apps,
- use `gemma3:1b`,
- avoid multiple model calls in parallel,
- do not run the demo repo’s app and the compiler at the same time,
- use the precomputed demo if the laptop struggles during judging.

### 22.4 The lane is crowded

Mitigation:

- the story is anti-slop, not “AI writes your portfolio,”
- the demo shows a false claim being rejected,
- the output includes an interview defense pack,
- local-only is central, not decorative,
- the DEV post explains the difference clearly.

### 22.5 The demo repo has no README

Mitigation:

- that is the point,
- the tool reconstructs from code and commits,
- the case study explicitly says “no README found”,
- the narrative is stronger because of it.

### 22.6 The tool overclaims

Mitigation:

- deterministic verifier,
- forbidden-claim list,
- attestation labels,
- no claims about tests passing or deployment,
- no invented metrics,
- export warning.

### 22.7 Time runs out

Mitigation:

- cut lines are defined,
- core pipeline first,
- UI polish later,
- precomputed demo as a safety net,
- submit Sunday night.

### 22.8 Ollama is unavailable on the judge’s machine

Mitigation:

- precomputed demo files,
- video,
- clear setup instructions,
- a “bring your own model” note,
- the app can still show the precomputed session in read-only mode if implemented.

### 22.9 Privacy concerns

Mitigation:

- local-only architecture,
- no telemetry,
- no upload,
- secret skipping,
- export warning,
- no GitHub OAuth.

### 22.10 “Slow and Steady” theme is not obvious

Mitigation:

- make the compile stages visible,
- use the phrase “compiled, not generated,”
- show the user reviewing evidence,
- explain the slow/steady philosophy in the DEV post,
- the lazy payoff is the draft waiting for them.

---

## 23. Cut lines

If time is short, cut in this order:

1. Optional HTML export.
2. Attestation flow.
3. Advanced redaction.
4. Defense questions from 6 to 4.
5. Case study sections from 7 to 5.
6. Fancy animations.
7. Multiple themes.
8. Extra export formats.

Never cut:

- evidence extraction,
- citations,
- verifier,
- false-claim demo,
- local Ollama,
- Markdown export,
- README,
- DEV post.

---

## 24. Open questions

Most decisions are resolved; the rest can be made during implementation.

1. **Name:** Doxify, CaseFile, Proofwork, or something else?
   - Resolved: Doxify. It is memorable, fits the defense angle, and the user has locked it.

2. **Stack:** Python/FastAPI backend and Next.js frontend?
   - Resolved: yes. The backend is Python 3.14 + FastAPI + Pydantic; the frontend is Next.js (App Router) + React + TypeScript. Python 3.14, `uv`, Node 24, and npm are all available.
   - Remaining sub-decision: generate the frontend TypeScript types from FastAPI's `/openapi.json` with `openapi-typescript`, or maintain `web/lib/types.ts` by hand for the MVP. Recommendation: hand-maintain for the MVP, generate later if time allows.

3. **Output:** Markdown only or HTML too?
   - Recommendation: Markdown only for the MVP. HTML is a stretch goal.

4. **Should the tool run the repo’s tests?**
   - Recommendation: no. It can cite the existence of tests, but it must not claim they pass. Running arbitrary project tests is a security and time risk.

5. **Should the tool support private repos?**
   - It supports any local repo. The privacy story is strongest for private repos, but the demo uses a local repo that happens to lack a README.

6. **Should the demo include a precomputed session?**
   - Yes. It protects against slow laptops and gives judges something to inspect.

7. **Should the case study be first person?**
   - Yes. A portfolio case study is about the author’s work. The model should write “I” when describing the developer’s contributions, but only from evidence.

8. **Should the tool generate a cover letter or resume bullets?**
   - No. That is scope creep and moves into crowded resume-tool territory.

9. **Should the tool use embeddings?**
   - No. Keyword retrieval is enough for 6 cards per section and keeps the app small and local.

10. **Should the tool use a second model pass for verification?**
    - Optional. Deterministic checks are the source of truth. A second pass can be a tie-breaker, but it must not upgrade a failed claim.

---

## 25. First commands

These are suggestions for the implementation phase, not commands that have been run yet.

```bash
cd /home/ekomjah/Desktop/repos/doxify

# Confirm the local model and Python tooling
ollama list
ollama --version
python3 --version
uv --version
node --version
npm --version

# Backend scaffold
mkdir -p server/app/{routes,core,prompts} server/tests/fixtures
cd server
uv init --bare --name doxify-api
uv add fastapi "uvicorn[standard]" httpx
uv add --dev pytest pytest-asyncio mypy ruff
cd ..

# Frontend scaffold
npx create-next-app@latest web --typescript --app --no-tailwind --eslint --use-npm
cd web
npm install
cd ..

# Shared contract snapshot and demo output
mkdir -p shared demo/scholarship-mcp

# Start Ollama if it is not already running
ollama serve

# Pull the model if it is missing
ollama pull gemma3:1b
```

Do not commit `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `node_modules/`, `.next/`, `.doxify/`, or any `.env` file.

---

## Appendix A — scholarship-mcp evidence map

This appendix is the source material for the demo. It should be used to validate that the scanner extracts the right facts.

### A.1 Repository identity

- Path: `/home/ekomjah/Desktop/repos/scholarship-mcp`
- Commit count: 20
- First commit date: 2026-09-12
- Last commit date: 2026-09-14
- README: absent
- Primary language: JavaScript (ESM)
- Package manager: npm
- Runtime: Node.js

This appendix describes the **demo input repository**, not Doxify itself. Doxify’s backend is Python/FastAPI. The scanner is language-agnostic and reads `package.json` for JavaScript projects and `pyproject.toml`/`requirements.txt` for Python projects.

### A.2 Tools

File: `src/utils/tools.js`

Nine tools:

1. `search_scholarships`
2. `get_scholarship`
3. `match_scholarships`
4. `save_scholarship`
5. `list_saved_scholarships`
6. `add_research_note`
7. `list_research_notes`
8. `get_upcoming_deadlines`
9. `compare_scholarships`

The file imports `zod/v4` and defines `TOOLS` as an array of objects with:

- `name`
- `title`
- `description`
- `inputSchema`
- `annotations`
- `handler`

Read-only vs. write tools are annotated with `READ_ONLY` and `WRITE`.

### A.3 Models

Files:

- `src/models/scholarship.js`
- `src/models/saved-scholarship.js`
- `src/models/research-note.js`

The scholarship schema includes:

- title, provider, description
- amount min/max, currency
- deadline, rolling
- education levels, fields of study
- GPA minimum
- citizenship, countries
- first-generation-only, women-only
- number of awards, renewable
- application URL, application requirements
- timestamps
- text index on title/provider/description/fieldsOfStudy
- deadline index
- amountMax index

### A.4 MCP surface

Files:

- `src/mcp/server.js` — creates the server and registers tools, resources, and prompts.
- `src/mcp/tools.js` — loops over `TOOLS` and registers each tool.
- `src/mcp/prompt.js` — registers the `research-plan` prompt.
- `src/mcp/resource.js` — registers the `scholarship-record` resource template.

### A.5 Transport and lifecycle

File: `src/index.js`

- uses `createMcpExpressApp`
- uses `toNodeHandler`
- uses `createMcpHandler`
- exposes `/health`
- exposes `/mcp`
- handles `SIGINT` and `SIGTERM`
- closes HTTP, MCP handler, and Mongoose connection
- has a 5-second forced shutdown timer

### A.6 Matching engine

File: `src/services/match.js`

- `openDeadlineFilter()` excludes closed deadlines unless rolling or null.
- `SOFT_SCORES` weights:
  - education 20
  - GPA 15
  - citizenship 15
  - field 30
  - country 10
  - amount 10
  - eligibility tag 10
- `listMatches()` normalizes values and handles `"any"`.
- `scoreScholarship()` returns `matched`, `score`, `reasons`, `blocked`.
- Hard blocks include:
  - education level not accepted,
  - GPA below minimum,
  - citizenship not eligible,
  - first-generation-only mismatch,
  - women-only mismatch.
- `matchScholarships()` queries open deadlines, scores candidates, filters unmatched, sorts by score and amount, and limits results.

### A.7 Library services

File: `src/services/library.js`

- `saveScholarship()` upserts by researcher and scholarship.
- `listSavedScholarships()` populates scholarship fields.
- `addResearchNote()` validates the scholarship exists.
- `listResearchNotes()` populates scholarship title/provider.
- `getUpcomingDeadlines()` filters by date range.
- `compareScholarships()` accepts 2–3 IDs and returns selected fields.

### A.8 Seed data

Files:

- `data/scholarships.json` — 26 records.
- `scripts/seed.js` — seeds the catalog.

Do not claim the records are real scholarships. Say “26 seeded records” or “a 26-record catalog.”

### A.9 Smoke test

File: `scripts/smoke-test.js`

The smoke test:

- connects to the database,
- checks the catalog is non-empty,
- calls `search_scholarships`,
- extracts an ID,
- calls `get_scholarship`,
- calls `match_scholarships` with a sample profile,
- calls `save_scholarship`,
- calls `list_saved_scholarships`,
- calls `add_research_note`,
- calls `list_research_notes`,
- calls `get_upcoming_deadlines`,
- calls `compare_scholarships`,
- cleans up saved scholarships and notes.

Do not claim the smoke test passed unless it was actually run.

### A.10 Commit arc

```text
2026-09-12  feat: initial commit
2026-09-12  chore: install necessary packages and configure env files
2026-09-12  feat: add initial server setup with Express and MongoDB connection
2026-09-14  feat(models): add Scholarship, SavedScholarship, and ResearchNote schemas
2026-09-14  feat(services): add scholarship search and catalog read
2026-09-14  feat(services): add scholarship matching engine with scored reasons
2026-09-14  feat(services): add save, notes, deadlines, and compare helpers
2026-09-14  feat(utils): add MCP result wrapper and scholarship formatters
2026-09-14  feat(utils): add schemas and handlers for nine MCP tools
2026-09-14  feat(mcp): register nine scholarship research tools
2026-09-14  feat(mcp): add research plan prompt
2026-09-14  feat(mcp): add scholarship record resource template
2026-09-14  feat(mcp): assemble scholarship MCP server
2026-09-14  feat(index): serve MCP over streamable HTTP with graceful shutdown
2026-09-14  feat(data): add realistic scholarship catalog
2026-09-14  feat(scripts): seed catalog from data/scholarships.json
2026-09-14  chore(package): update build, dev, and seed npm scripts
2026-09-14  chore(data): remove empty scholarship.json placeholder
2026-09-14  feat(tests): add smoke test script for scholarship functionality
2026-09-14  Set default host to 0.0.0.0
```

This arc is the raw material for the “how it was built” section. The tool should summarize the arc, not quote all 20 commits.

### A.11 Evidence caveats

- The repo has no README. Do not invent one.
- The repo has no license file in the tracked files. Do not claim a license.
- The repo has no CI workflow. Do not claim CI.
- The repo has no deployment config. Do not claim deployment.
- The repo has no authentication. Do not claim auth.
- The repo has a `.env.example` with placeholder values. Do not expose it.
- The repo has a `package-lock.json`. Do not quote it.
- The repo has a `.vscode/mcp.json`. It may contain local config; inspect before including.

---

## Appendix B — sample case study outline for scholarship-mcp

This is the target shape of the generated case study. The model should fill it in with citations.

```md
# Scholarship MCP: Giving an AI agent real scholarship-research tools

## Snapshot

Scholarship MCP is a local MCP server for scholarship research. It exposes a typed tool surface for searching, matching, saving, and tracking scholarships, with a small research prompt and a resource template.

## The problem

Scholarship research is fragmented across websites, PDFs, and notes. An AI agent without tools can only talk about scholarships; it cannot query a catalog, score eligibility, save a shortlist, or track deadlines.

## The approach

The project wraps the research workflow in an MCP server. Each capability is a tool with a Zod input schema and a clear description. The server also exposes a scholarship record resource and a research-plan prompt.

## Architecture

The stack is Node.js, Express, MongoDB via Mongoose, and the MCP server SDK. The entry point serves MCP over streamable HTTP, exposes a health endpoint, and handles graceful shutdown.

## The hard part

The matching engine has to be explainable. Hard eligibility rules remove candidates, then weighted scoring ranks the rest with human-readable reasons. That separation keeps the results defensible.

## What shipped

Nine tools, three models, a research prompt, a resource template, a 26-record seed catalog, and a smoke test that exercises the tool surface.

## Evidence

The repository has 20 commits over three days. The tool surface, models, matching logic, and smoke test are all present in the code.

## What I would change

Add a README, connect a real data source, add authentication, and run the smoke test in CI.

## Evidence appendix

- E1 — 20 commits, 2026-09-12 to 2026-09-14.
- E2 — Nine MCP tools in `src/utils/tools.js`.
- E3 — Three Mongoose models in `src/models/`.
- E4 — Hard filters and weighted scoring in `src/services/match.js`.
- E5 — Smoke test in `scripts/smoke-test.js`.
- E6 — 26 seeded records in `data/scholarships.json`.
```

The model should not copy this outline verbatim. It should generate the prose from evidence. The outline is a target shape, not a template to fill with adjectives.

---

## Appendix C — sample defense questions for scholarship-mcp

1. **Why MCP instead of a normal REST API?**
   - Why asked: tests whether the MCP choice was deliberate.
   - Outline: tool surface for agents, typed schemas, resources/prompts, reusable across clients.

2. **How does the matching engine prevent ineligible scholarships from being recommended?**
   - Why asked: tests understanding of hard filters vs. soft scores.
   - Outline: `openDeadlineFilter`, hard blocks, `matched` flag, reasons and blocked arrays.

3. **Why separate hard eligibility filters from weighted scoring?**
   - Why asked: tests design tradeoffs.
   - Outline: eligibility is binary and legal/ethical; scoring is preference; separation makes results explainable.

4. **How does the smoke test exercise the tool surface?**
   - Why asked: tests whether the project was verified.
   - Outline: search, get, match, save, list, notes, deadlines, compare, cleanup.

5. **What happens if MongoDB is unavailable at startup?**
   - Why asked: tests failure handling.
   - Outline: `start()` awaits `connectDatabase()`; failure is caught and exits; no silent fallback.

6. **What would you change before using this with real scholarship data?**
   - Why asked: tests judgment and honesty.
   - Outline: real data source, validation, auth, rate limits, README, CI, privacy review.

Do not present these as facts about the author. They are questions generated from the code and evidence.

---

## Appendix D — references

Hackathon:

- Challenge hub: https://dev.to/challenges/hf26
- Week 3 challenge: https://dev.to/challenges/hacktoberfest-week3-2026-10-19
- Week 3 rules: https://dev.to/page/hacktoberfest-week3-2026-10-19-contest-rules
- Challenge tag: https://dev.to/t/hf26challenge

Local environment:

- Ollama: https://ollama.com
- Gemma 3: https://ai.google.dev/gemma
- MCP: https://modelcontextprotocol.io

Competitive research (examples, not endorsements):

- GitShowcase: https://gitshowcase.mfaeezshabbir.me/
- Gitfolio: https://gitfolio.dev/
- Jobr AI Portfolio Builder: https://jobr.pro/ai-portfolio-builder
- FolioLab: https://github.com/matmulai/foliolab
- Repo2Site: https://github.com/mtafoya-web/repo2site
- SerisLab: https://github.com/stharavi01/SerisLab
- Prooflink: https://devpost.com/software/prooflink
- GitSkins: https://github.com/asamassekou10/GitSkins
- GitStory: https://dev.to/bbtc3453/i-built-an-ai-that-turns-github-commits-into-stories-nfe
- GitNarrative: https://dev.to/grudged/i-built-gitnarrative-turn-your-git-commits-into-stories-ka0
- ClaimCheck: https://github.com/visione4906/ctaio-claimcheck
- Proofrail: https://github.com/DrDeese/Proofrail
- Checkmarked: https://checkmarked.dev/
- GitReal: https://github.com/satwik146/gitreal
- CareerForge: https://github.com/edwardjgriggs/careerforge
- ProofMap: https://github.com/snehagrian/proofmap
- GitHub Resume Assistant: https://github.com/justomsharma/github-resume-assistant
- ResumeProof: https://github.com/caihhhhhh/resume-proof
- claims-ledger: https://github.com/isatimur/claims-ledger
- ProofChain: https://github.com/LouVan/proofchain
- CodeBridge: https://github.com/saidulalam01/codebridge
- Repo Cloak: https://marketplace.visualstudio.com/items?itemName=ShazniShiraz.repo-cloak
- saw: https://github.com/kevinsanchh/saw

Demo repo:

- `/home/ekomjah/Desktop/repos/scholarship-mcp`

---

## Final recommendation

Build the smallest version that can produce this moment:

> The tool generates a case study, and when it reaches “Includes OAuth authentication,” it refuses to verify it, shows the evidence gap, and asks the user a question.

That moment is the product.

Everything else — the UI, the export, the defense pack — exists to make that moment useful.

If the implementation has to be cut, protect the evidence ledger, the citation grammar, the verifier, and the false-claim demo. Those four things make Doxify different from a generic AI writer.
