# Observability

Doxify is local-first. Sentry monitoring is **off by default** and only starts
when you provide an explicit `SENTRY_DSN`. Without a DSN, Doxify writes no
telemetry and does not contact Sentry.

When enabled, monitoring sends a deliberately narrow slice of operational data:
command errors, timings, redacted structured logs, and model/HTTP spans. It does
not send prompts, completions, repository contents, evidence text, environment
variables, user identity, cookies, request bodies, query strings, or local
absolute paths.

## Enable locally

```bash
export SENTRY_DSN="https://<key>@<host>/<project>"
export SENTRY_ENVIRONMENT="development"
export SENTRY_TRACES_SAMPLE_RATE="1.0"
doxify self-check --json
```

Disable it at any time with `DOXIFY_SENTRY=0` or an empty `SENTRY_DSN`. The
default sample rate is `0.2`; use `1.0` for a smoke test and lower values for
normal use.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SENTRY_DSN` | unset | Opt-in switch. Monitoring never starts without it. |
| `DOXIFY_SENTRY` | `1` | Set to `0` to force monitoring off even with a DSN. |
| `SENTRY_ENVIRONMENT` | `development` | Sentry environment name. |
| `SENTRY_RELEASE` | `doxify@<version>` | Release name. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.2` | Transaction sample rate, clamped to `0..1`. |
| `SENTRY_SEND_LOGS` | `1` | Send WARNING+ structured logs as Sentry logs. |
| `SENTRY_MONITOR_SLUG` | unset | Default Sentry cron monitor slug. No check-in without a slug. |
| `SENTRY_DEBUG` | `0` | Print Sentry SDK debug output. Do not enable in CI. |
| `DOXIFY_LOG_LEVEL` | `WARNING` | Local log threshold (`DEBUG`, `INFO`, `WARNING`, ...). |
| `DOXIFY_LOG_FORMAT` | `human` | `human` or `json` stderr output. |

## What is collected

Errors:

- exception type and redacted message;
- sanitized stack frames with source context, local variables, and absolute
  paths removed;
- safe tags such as `command`, `stage`, `outcome`, `exit_code`, `provider`, and
  `model`;
- a `doxify` context containing only command, stage, and provider.

Traces:

- command transactions named `doxify.<command>`;
- stage spans, model spans, and HTTP client spans;
- safe measurements such as command duration, model duration, and token usage;
- safe span data limited to `doxify.*`, `gen_ai.*`, and HTTP method/status keys.

Logs:

- structured events such as `model.response` and `model.error`;
- only allowlisted fields (`model`, `provider`, `status`, token counts, duration,
  command, stage, exit code, and Scout summary counts);
- no prompt, completion, source snippet, or repository path.

The SDK is initialized with `data_collection` explicitly disabling user info,
cookies, request headers, request bodies, URL query params, GraphQL documents
and variables, GenAI inputs/outputs, database query data, queues, stack-frame
variables, and frame context lines. `default_integrations=False` avoids
automatic instrumentation that could collect more than intended.

## Dashboards

Create a `Doxify Observability` dashboard in the Sentry project with these
widgets:

| Widget | Dataset | Query / metric |
|---|---|---|
| Command errors | Errors | `event.type:error` grouped by `command` |
| Command latency | Traces | p50/p95 of `doxify.command.duration_ms` by `command` |
| Stage latency | Traces | p95 span duration grouped by `stage` |
| Model latency | Traces | p95 of `doxify.model.duration_ms` by `model` |
| Token usage | Traces | sum of `gen_ai.usage.total_tokens` by `model` |
| Fallback rate | Logs | count of `model.error` with `status:fallback` |
| Scout quality | Logs | average `replay_score`, count by `status` |
| Nightly health | Crons | check-in status for `doxify-nightly` |

Sentry does not probe local CLI processes. Use Crons for scheduled health
checks instead of Uptime.

## Crons

`doxify self-check` can report a cron check-in when given a monitor slug:

```bash
doxify self-check --monitor-slug doxify-nightly --json
```

The monitor config is `0 3 * * *` UTC with a 10-minute check-in margin and a
15-minute maximum runtime. Without `--monitor-slug` or `SENTRY_MONITOR_SLUG`,
no check-in is sent.

The nightly GitHub workflow is `.github/workflows/sentry-nightly.yml`. Add the
project DSN as the `SENTRY_DSN` repository secret; if the secret is absent the
workflow still runs with monitoring disabled.

## Verify a smoke test

```bash
export SENTRY_DSN="https://<key>@<host>/<project>"
export SENTRY_TRACES_SAMPLE_RATE=1.0
uv run doxify self-check --json
sentry trace list <org>/<project>
```

For an end-to-end trace with a child span, scan a disposable repository:

```bash
uv run doxify scan /tmp/scout-demo --out /tmp/doxify-sentry-scan --force
```

Then inspect the transaction in Sentry and confirm that no prompt, source
snippet, token, absolute path, or query string is present.
