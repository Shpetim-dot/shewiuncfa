# Model providers

`app/providers.py` speaks three wire formats; the gateway (`gateway.py`) records usage and cost
for every call and the fallback chain in `cfa_core.llm` stays unchanged.

| Adapter | Used for | Endpoint | Auth |
|---|---|---|---|
| `openai` | OpenAI, Mistral, vLLM, LiteLLM, Hugging Face router, any OpenAI-compatible endpoint | `POST {base}/chat/completions` | `Authorization: Bearer` |
| `anthropic` | Claude models | `POST https://api.anthropic.com/v1/messages` | `x-api-key` + `anthropic-version: 2023-06-01` |
| `google` | Gemini models | `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `x-goog-api-key` |

## Choosing the adapter

Model ids are resolved in this order (`cfa_core.resolve_model`):

1. `hf:...` → Hugging Face router (OpenAI-compatible)
2. explicit prefix `anthropic:` / `claude:` / `gemini:` / `google:` / `openai:`
3. name pattern (`claude*` → anthropic, `gemini*` → google)
4. a provider id registered under *Models & usage → Providers* (OpenAI-compatible, key encrypted)
5. default `CFA_MODEL_BASE_URL` + `CFA_MODEL_API_KEY`

## Environment

```
CFA_MODEL_API_KEY=        # default OpenAI-compatible endpoint
CFA_MODEL_BASE_URL=https://api.openai.com/v1
CFA_MODEL_NAME=gpt-4o-mini
ANTHROPIC_API_KEY=        # or CFA_ANTHROPIC_KEY; base override CFA_ANTHROPIC_BASE_URL
GEMINI_API_KEY=           # or CFA_GEMINI_KEY / GOOGLE_API_KEY; base override CFA_GEMINI_BASE_URL
HF_TOKEN=                 # Hugging Face Inference Providers
CFA_MODEL_TIMEOUT=45      # seconds per attempt
CFA_MAX_TOKENS=700
```

`/api/health` reports `model_configured` from `providers.configured()`, so a deployment with only
an Anthropic key is reported as live.

## Normalised usage

Every adapter returns `{tokens_in, tokens_out}` from the provider's own usage block
(`prompt_tokens`/`completion_tokens`, `input_tokens`/`output_tokens`,
`promptTokenCount`/`candidatesTokenCount`). Cost is only computed when a price record exists
(`PUT /api/prices`, source required); otherwise the usage row keeps `cost = NULL` and the report
says the total is partial.

## Errors and retries

Three attempts with exponential backoff for 429/5xx; 401/402/403/404 stop immediately and are
translated into a readable message. Fallback models (`PUT /api/fallbacks`) run only after a
provider failure and are recorded as `fallback = 1`.

## Adding a provider

Implement the request/response mapping in `providers.complete`, add its key/base resolution in
`key_for`/`base_for`, and cover the wire format in `tests/test_providers.py` with an
`httpx.MockTransport`. Never add a network call to a test.
