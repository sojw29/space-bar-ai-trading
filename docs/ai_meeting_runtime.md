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

Partial HTTP reads, disconnected HTTP responses and malformed HTTP status lines
are converted to `PROVIDER_CONNECTION_INTERRUPTED`. Their raw exception text and
partial response content are not emitted in CLI errors, diagnostics or summaries.
An interruption stops subsequent calls without retrying, records attempted versus
validated response counts, and does not replace a previous completed transcript.
A failed first call does not create a completed output. The diagnostic does not
establish whether a provider billed an interrupted request.

## Public candle source selection after the Bybit 403 failure

The confirmed readiness run 41558873829 failed on Bybit public OHLCV HTTP 403,
before any OpenAI call. A key replacement cannot repair that market-data request.

The readiness and paid meeting workflows now expose `market_provider` (`okx` or
`bybit`), defaulting explicitly to `okx`. Choose `main` and start a **new Run
workflow** to use this code; re-running an old failure keeps its old commit.
Scheduled Pages indicator collection explicitly uses OKX too. The CLI retains
Bybit as its backwards-compatible default and accepts `--provider okx`.
There is no automatic fallback, proxy, regional mirror, mixed-venue dataset or
change to trading permissions.

OKX uses the official public `/api/v5/market/candles` endpoint with BTC-USDT-SWAP,
ETH-USDT-SWAP and SOL-USDT-SWAP at 5m. Only `confirm=1` rows are used; `volCcy`
(base-currency volume for derivatives) is selected, not contract-count `vol`.
The existing OHLC consistency, finite values, candle continuity, freshness and
minimum completed-history checks remain active. Responses are size bounded.

The allowlisted `market_source` ID is propagated through interpretation, brief,
audit, adapter requests, preflight, actual model context and completed transcript.
Preflight rejects divergent source IDs; publication compares the report's source
against the exact request bundle. Room panels and readiness summaries display the
venue. Historical local records retain source; cross-venue or known-vs-unrecorded
comparisons/charts are blocked. Clear older local history if you want to begin a
new consistent history for one venue. Legacy fixtures without a source remain
supported but are labeled unrecorded rather than relabeled as Bybit or OKX.

An OKX observation is not a Bybit observation. Independent exchange prices and
volumes can differ. Source access still depends on the execution environment;
collection errors stop readiness/live preparation before model calls, rather than
being treated as validated data. No OpenAI key is used by public candle collection.

Source contract: https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks

All three symbols now use one collection-start cutoff for completed bars, so a
5-minute boundary during sequential requests does not advance only part of the
batch. Their final completed-candle timestamps must match exactly. An off-grid,
fractional or boolean candle epoch is rejected rather than silently coerced.
Before publication, the collector rechecks freshness against completion time
and rejects backward clock movement. Source-marked snapshots receive the same
timestamp alignment/completion/freshness validation again during interpretation.
A lagging symbol blocks publication; retry a new readiness run after the data
source has caught up. There is no automatic retry or padding of missing candles.

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

Public candle requests reject HTTP redirects, including redirects on the same host.
A redirect fails collection without retries or venue fallback; no redirected response
is published with the selected exchange's provenance. The fixed official endpoint
must return its own successful response.

## Runtime transcript and local 3D meeting viewer

The two research views remain distinct:

1. `GET /api/v1/meeting` reports an **offline quality gate** from
   `reports/v65/quality.json`; it is not an AI model transcript.
2. `GET /api/v1/meeting/transcript` reads a **completed, locally stored**
   seven-step transcript from `reports/ai_meeting/latest.json`. The
   `/office3d` meeting panel now requests this endpoint and displays the
   validated analysis, peer review and COMMANDER conclusion as plain text.
   The endpoint never runs a model and never submits orders.

### Local operator steps (not a live-trading workflow)

First prepare a fresh, valid V236 request bundle using the existing research
pipeline and input-readiness checks. To explicitly run a paid research meeting,
use the existing runtime with your own supported model and authorization:

```sh
python agents/ai_meeting_runtime.py path/to/fresh_v236_bundle.json reports/ai_meeting/latest.json --model YOUR_SUPPORTED_MODEL --enable-live
python agents/dashboard_api_v28.py --help
```

The first command is **optional** and may make up to seven paid API calls.
Set `OPENAI_API_KEY` only in the local process environment; never commit it.
The dashboard's actual launch options are shown by `--help`. Open
`/office3d` on the local dashboard server. A missing, oversized, stale,
malformed, or inconsistent transcript yields HTTP 503 and an unconnected
meeting display; no automatic retries or provider calls occur. The report
must have a source timestamp no older than eight hours, valid provenance,
seven ordered statements, and a consistent final verdict. A successful
HTTP response does **not** mean any trade was authorized.

The runtime accepts any caller-selected destination, but the local API
reads `reports/ai_meeting/latest.json` under the repository root by default.
To display a runtime output stored elsewhere, explicitly select that same file:

```sh
python agents/dashboard_api_v28.py --meeting-transcript path/to/completed-meeting.json
```

This option reads a local file only; it does not invoke a provider or synchronize
remote output. Missing or invalid selected files return HTTP 503 without falling
back to the default report. The same transcript validation applies.
Writing `web/ai_meeting.json` or publishing to GitHub Pages does not
populate this local API. Launch the dashboard from the repository root
so other relative paths resolve as intended. A completed report generated
on a remote GitHub Actions runner is **not automatically synchronized**
to your local machine. Do not copy private diagnostics or API credentials
into the web directory.

The UI distinguishes `LIVE_PROVIDER` from `OFFLINE_FIXTURE`; a fixture
is not evidence of real model inference. Neither view is live trading.
Actual browser rendering and an end-to-end paid-provider run still require
separate, explicitly authorized verification.


### Check local setup before a paid meeting

```sh
python agents/ai_meeting_setup.py path/to/fresh_v236_bundle.json --model YOUR_SUPPORTED_MODEL
```

This reads a bounded existing bundle and validates its freshness/contracts plus
local model-name and OPENAI_API_KEY presence. It performs no network requests,
model calls, output publication or orders and never prints the key or source
contents. LOCAL_SETUP_VALID means local checks only: credential validity, model
access, billing and supported model behavior remain unverified. BLOCKED returns
exit status 1 with a sanitized code. Source data can expire after this check;
the runtime still validates it again when explicitly invoked.


### Prepare the runtime input from an existing brief

```sh
python agents/ai_meeting_prepare.py path/to/commander_brief.json path/to/meeting_bundle.json
python agents/ai_meeting_setup.py path/to/meeting_bundle.json --model YOUR_SUPPORTED_MODEL
```

Preparation combines the existing source validation, handoff, consistency review,
V236 adapter and dry-run transport checks. No credentials or model calls are
needed to prepare the bundle. It checks freshness at each stage and immediately
before atomic publication, preserves an existing output on validation failure,
and rejects source/output aliases. The bundle is an unexecuted request, not a
completed meeting transcript; never select it as the dashboard transcript.
After local setup succeeds, the separate runtime command with explicit
`--enable-live` is still required to run a paid meeting. Preparation never invokes
that command automatically. A blocked preparation does not make an older output
current; check the exit status and let the runtime revalidate before inference.
