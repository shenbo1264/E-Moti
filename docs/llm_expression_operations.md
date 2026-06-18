# LLM Expression Operations

## Purpose

The LLM expression provider improves Xingxi's speech, expression cues, motion cues, and read-only interaction intent. It does not own growth state, inventory, relationship, memory, goals, coins, or saves.

## Configure DeepSeek

```powershell
$env:DEEPSEEK_API_KEY="your-local-key"
python tools\llm_provider_diagnostics.py --provider deepseek --model deepseek-v4-flash --base-url https://api.deepseek.com
```

## Dry Run

```powershell
python tools\llm_dialogue_smoke.py --provider deepseek --dry-run
```

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
- provider timeout: keep local fallback speech enabled and do not change state.
- unsafe event: inspect the smoke report, parser tests, and typed event schema before retrying.
