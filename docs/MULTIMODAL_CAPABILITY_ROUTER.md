# Multimodal Capability Router

This public skeleton surface documents a local-first multimodal routing pattern.
It is not a private runtime dump and it does not include local memory, tokens,
logs, payloads, vector stores, or machine-specific paths.

## Routing Contract

- Text input routes to the chat model.
- Image input routes to a dedicated vision model, then the resulting description
  is passed into the chat model.
- Speech input routes through STT, then the chat model, then optional TTS.
- Long reflection and dream work route to the chat model with a larger budget.
- Fast reactions may use a smaller reaction model when latency matters.

## Public-Safe Environment Keys

These keys are names only. Values are deployment-specific and must stay outside
the public repository when they contain secrets or local paths.

```text
ESTER_CAPABILITY_PROFILE=local-multimodal
LMSTUDIO_MODEL=<chat-model>
ESTER_VISION_PROVIDER=local
ESTER_VISION_MODEL=<vision-model>
ESTER_VISION_PRELOAD=1
ESTER_VISION_KEEP_ALIVE=-1
ESTER_VISION_MAX_TOKENS=1200
STT_ENABLE=1
STT_MODEL=<speech-model>
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_LANG=en
ESTER_TTS_ENABLED=1
ESTER_TG_TTS_COMMAND_ENABLED=0
ESTER_FAST_MODEL=<optional-fast-model>
```

## Public Endpoints

- `GET /capabilities/router/status`
- `GET /capabilities/router/<kind>`

The status payload is configuration-derived. It reports model names and routing
shape only; it must not expose tokens, private messages, memory contents, or
local files.
