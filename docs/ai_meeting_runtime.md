# Research model meeting

The optional runtime now implements a real OpenAI HTTPS transport, separate from
the V233–V240 offline contracts. It has not been exercised against a paid API in
CI. A fixture test is not evidence that a real model ran.

The first connected team is ATLAS, QUANT, GUARDIAN and COMMANDER. The other six
planned roles are not model participants yet. These are roles of the configured
model, not independently trained systems. No self-training is implemented.

## Execution

Prepare a fresh V236 bundle through the existing research pipeline. It must contain
validated BTC/ETH/SOL observations with a source timestamp no older than eight
hours. Use `model_adapter_contract_v236.py` on the V235 consistency review JSON.

```sh
python agents/model_adapter_contract_v236.py path/to/review.json path/to/requests.json
python agents/ai_meeting_runtime.py path/to/requests.json web/ai_meeting.json --enable-live --model YOUR_SUPPORTED_MODEL
python -m http.server 8000 --directory web --bind 127.0.0.1
```

Set `OPENAI_API_KEY` in the local process environment before running. Never paste
it into a browser, HTML, repository, transcript or command argument. The CLI does
not read browser credentials. The selected model must support strict JSON schema
in Chat Completions. Authentication, model access and billing are separate from
a ChatGPT subscription.

Each explicit run makes at most **seven sequential API calls** (potentially paid):
three independent observations, three peer reviews using all first-round results,
and a COMMANDER conclusion using all six prior statements. There are no retries,
tools, orders, recurring runs or workflow calls to the provider. Each request has
a 30-second timeout and a 2,000 completion-token ceiling; input tokens also count.
The source is revalidated before each call and before publication.

An insufficient-data objection cannot be overruled. GUARDIAN's review objection
also limits the final research status. Both the model's original conclusion and
the effective status are retained. Schema validation does not prove the model's
claims are true: hallucinations and correlated errors remain possible.

## Room connection

Open `http://127.0.0.1:8000/office_3d.html`, then expand **별도 모델 회의 기록**.
The room loads `ai_meeting.json` once and shows the seven statements and effective
research status. Missing, invalid and expired snapshots show no discussion rows.
Expired source data is checked every minute and on return to the foreground.
Reload after a successful new run. Existing rule-based panels remain separate.

`LIVE_PROVIDER` labels a completed provider call chain, not ongoing autonomous
agents. Injected test providers are always labeled `OFFLINE_FIXTURE` with
`model_inference_performed: false`. No generated fixture is deployed as a live meeting.

The generated transcript is ignored by git. Public GitHub Pages execution is
now available through the explicit manual workflow described below. Without a
successful manual live run the public room reports no connected meeting.
The browser never receives the API key.

Output is atomic. A failed run leaves the previous completed file intact; it is
still a dated snapshot, never evidence of a successful new run. The room's source
expiry prevents indefinite display. Do not run concurrent writers to one output.

Provider reference: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

## Manual execution and publication with GitHub Actions

1. In repository **Settings → Secrets and variables → Actions**, create the
   repository secret `OPENAI_API_KEY`. Enter the key only in GitHub's secret form.
2. In **Actions → SPACE BAR Manual AI Meeting Publication → Run workflow**, select
   **main**, enable **run_ai_meeting**, and enter a supported model in **ai_model**.
   Enabling this option authorizes one meeting with up to seven paid API calls
   and public publication of its research statements.
3. A successful run deploys the room and transcript together. Reload
   `https://sojw29.github.io/space-bar-ai-trading/office_3d.html` and expand
   **별도 모델 회의 기록**.

The dedicated model workflow has only a manual trigger and the default checkbox
is off. A run without authorization fails before provider calls. The separate
Browser Room GitHub Pages workflow handles pushes and schedules without keys or
model calls. Missing secrets/models and non-main live runs fail before provider
calls. The model name is passed through an environment
variable and a quoted argument, never interpolated into shell code. No secrets or
intermediate request bundles are uploaded as artifacts.

The live path collects public completed-candle indicators, prepares the V233–V236
request bundle, executes the meeting, then validates the entire transcript against
that exact bundle before uploading Pages. Unavailable data, provider failures,
partial output or failed validation stop the new deployment. The previous public
site remains in place; no success is inferred from an old snapshot.

Normal deployments fetch the previous transcript only from the fixed public Pages
origin and keep it only while it passes live-only schema, timestamps, roles,
seven-phase sequence and final-veto validation. Fixtures, redirects, oversized,
expired or malformed records are not retained. Retention performs no model calls.
The source-based eight-hour limit still applies; retaining does not refresh dates.
This relies on the existing Pages origin as the trusted publisher, not a signature
or independent proof of model provenance. If retrieval is unavailable, the next
normal deployment shows no connected meeting rather than an unvalidated record.

CI exercises mocked provider and carry-over paths only. A successful paid run
and provider/model access must still be verified in the configured repository.

## Execution diagnostics

The manual workflow now appends an **AI 회의 실행 진단** section to its Actions
job summary, even after an earlier step fails. During model execution, logs show
the current role/phase and validated response count. A bounded status JSON in
`RUNNER_TEMP` is atomically updated before and after each attempted call; it is
not uploaded with the public site. An interrupted run may leave `RUNNING` status,
which never means the meeting completed.

The CLI also supports `--diagnostics path/to/status.json`. This path must differ
from both source and transcript output (including symlink/hardlink aliases).
Only allowlisted status fields and error codes are recorded; raw HTTP bodies,
exception messages, API keys, prompts, model text and model names are excluded.
The summary renderer rejects malformed, oversized and unexpected fields.

Codes distinguish authentication/access failures, model-or-endpoint lookup,
request rejection, rate-or-quota limits, upstream errors, timeouts, output
truncation, refusals and input/configuration errors. HTTP categories are hints,
not a definitive diagnosis of billing or model compatibility. No automatic
retry is added. Attempts and validated responses are separate counters and do
not prove how many calls were billed.

A `COMPLETED` runtime status means the local transcript was created. Exact-bundle
public validation and Pages deployment remain later steps. If no valid status is
available (for example configuration/data preparation failed before runtime),
the summary says so instead of inferring that no call occurred or that publication
succeeded. On failure, an older completed transcript is not treated as this run's
result.

Execution diagnostics use the `MEETING_DIAGNOSTICS_2` schema with an execution ID,
start timestamp and last-update timestamp. Local CLI runs generate a new UUID;
`--execution-id` can supply a bounded workflow `run_id-run_attempt` identifier.
The manual workflow passes that same ID to runtime and summary renderer. Its
summary rejects a different run or retry, even if that record says COMPLETED.
The renderer also rejects timestamps in the future, reversed timestamp order,
records more than eight hours since the last update, and old diagnostics without
identity/time fields. These records produce an unknown-status notice.

For local summaries, `--expected-execution-id` is optional. Without it the summary
describes the selected dated record and is not proof it belongs to a current run.
IDs provide correlation, not cryptographic authentication. Neither runtime
completion nor matching identity proves Pages deployment succeeded.

Diagnostic progress must also match the sequential seven-call plan. The last role
and phase must match the attempted-call number, with at most one unvalidated
response. Input/configuration stages cannot contain model attempts. Publication
requires all seven responses, and COMPLETED requires the COMMANDER conclusion
plus the completed stage. A RUNNING or FAILED record after seven responses still
does not mean the transcript was published. Inconsistent records fall back to
unknown status; legitimate between-call freshness failures and interrupted calls
remain valid diagnostics.

## Input rehearsal without model calls

In Actions, run **SPACE BAR AI Meeting Input Readiness (No Model Calls)**.
No API key or model selection is required. This manual-only, read-permission
workflow collects public completed-candle indicators and compiles the same source
brief used by live execution, then runs source validation → handoff → consistency
review → model request preparation → transport preflight. All temporary files stay
in RUNNER_TEMP; there is no Pages upload/deployment or model invocation.

The Actions summary reports each preparation stage. `INPUTS_READY` means only
that current data can produce validated requests for four roles (a live meeting
would make up to seven calls). It does not check credentials, model access, model
compatibility, billing, actual model quality or trade readiness. Public data can
still be unavailable due to source/network restrictions; collection failure is
not converted into a successful check. Missing reports show an explicit unknown
status. Reports older than their eight-hour data window are not rendered as ready.

For a local existing V229 brief:

```sh
python agents/ai_meeting_readiness.py check path/to/commander_brief.json path/to/readiness.json
python agents/ai_meeting_readiness.py summary path/to/readiness.json path/to/summary.md
```

Invalid input returns a nonzero exit code with a sanitized blocked diagnostic.
The input and output cannot be the same file or aliases. Exceptions and source
text are not copied into the summary. The existing paid/publication workflow is
unchanged and still requires explicit authorization.

Readiness uses the current clock before every preparation stage and once more
before returning a ready result. Data expiring mid-check or immediately after
the last stage produces a blocked report, and backward clock movement is labeled
`CLOCK_CHANGED`. The report timestamp is the final observation time rather than
the start time. The exact eight-hour boundary remains inclusive; consumers must
still revalidate the timestamp when displaying an older report. An explicit
`now` argument remains available for deterministic local replays/tests; live CLI
checks do not freeze the clock at file-read time.
