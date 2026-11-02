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

The generated transcript is ignored by git. Existing GitHub Pages deployment
does **not** execute the model or publish this local output. Thus the public room
will say no meeting is connected until a separate server-side execution and
publication path is configured. The browser never receives the API key.

Output is atomic. A failed run leaves the previous completed file intact; it is
still a dated snapshot, never evidence of a successful new run. The room's source
expiry prevents indefinite display. Do not run concurrent writers to one output.

Provider reference: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
