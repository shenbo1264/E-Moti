# LLM Expression Operations

## Purpose

The LLM expression provider improves Xingxi's speech, expression cues, motion cues, and read-only interaction intent. It does not own growth state, inventory, relationship, memory, goals, coins, or saves.

## Configure DeepSeek

```powershell
$env:DEEPSEEK_API_KEY="your-local-key"
python tools\llm_provider_diagnostics.py --provider deepseek --model deepseek-v4-flash --base-url https://api.deepseek.com
```

## Provider Matrix

Use the provider matrix before live smoke tests. It distinguishes missing keys, authentication failure, quota or rate limits, timeouts, invalid responses, and local servers that are not running.

Recommended development routes:

- DeepSeek for low-cost cloud smoke.
- OpenRouter as an alternate cloud smoke route.
- Ollama or LM Studio as a local no-key fallback.

## Recommended Provider Path

1. Use `python tools\llm_provider_matrix.py --dry-run` to confirm settings shape.
2. Use a local Ollama or LM Studio server when cloud credentials are unavailable.
3. Use DeepSeek or OpenRouter for cloud smoke only after the key is current.
4. Treat missing key, auth failure, quota, timeout, invalid JSON, unsafe event, and state mutation as distinct failures.

Dry run, no provider calls:

```powershell
python tools\llm_provider_matrix.py --dry-run --report artifacts\llm_smoke\provider-matrix-dry-run.json --markdown artifacts\llm_smoke\provider-matrix-dry-run.md
```

Live route probe:

```powershell
python tools\llm_provider_matrix.py --timeout-seconds 5 --report artifacts\llm_smoke\provider-matrix-live.json --markdown artifacts\llm_smoke\provider-matrix-live.md
```

`ready` in dry-run mode means the local configuration is present. `ready` in live mode means the provider model-list route responded successfully. Reports never include API key values.

## Dry Run

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run
```

The dialogue smoke default prompts come from
`tests\fixtures\llm_conversation_scenarios.json`. The fixture is versioned and
covers comfort, celebration, boredom, focus, tiredness, gift, shop, character
switch, and confused user input. The generated report includes
`scenario_version`, `scenario_ids`, per-turn `scenario_id`, visual action
coverage, fallback count, unsafe event count, speech length violations, and the
state mutation guard.

Review an existing dialogue smoke or cue probe report:

```powershell
python tools\review_llm_smoke_report.py artifacts\llm_smoke\dialogue-smoke-dry-run.json --json artifacts\llm_smoke\dialogue-smoke-review.json --markdown artifacts\llm_smoke\dialogue-smoke-review.md
```

Review short-session companion quality without calling a provider:

```powershell
python tools\review_llm_session_quality.py artifacts\llm_smoke\dialogue-smoke-dry-run.json --json artifacts\llm_smoke\session-quality-review.json --markdown artifacts\llm_smoke\session-quality-review.md
```

The session quality review flags flat repeated speech, low expression diversity, source smoke failures, and any state mutation reported by the smoke guard. Use it after a live or dry-run dialogue smoke to separate provider connectivity from perceived companion performance.

## Live Cue Probe

```powershell
python tools\llm_expression_cue_probe.py --provider deepseek --timeout-seconds 45 --min-speech-chars 8 --max-speech-chars 80 --report artifacts\llm_smoke\deepseek-expression-cue-probe-latest.json
```

## Pass Criteria

- `ok=true`
- `fallback_count=0`
- `speech_quality.violations=[]`
- `state_mutation_check.ok=true`
- expression cues cover joy, sadness, sleepy, focused, and surprised

## Failure Handling

- `missing_api_key`: configure the local environment variable only.
- `http_401` or `auth_failed`: replace the local API key and rerun the provider matrix.
- `http_429` or `quota_or_rate_limited`: wait, reduce request rate, or switch provider.
- `timeout`: increase timeout or use a local provider for demo rehearsal.
- provider timeout: keep local fallback speech enabled and do not change state.
- unsafe event: inspect the smoke report, parser tests, and typed event schema before retrying.
