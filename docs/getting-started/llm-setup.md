# LLM Backend Setup (Optional)

An LLM backend unlocks **receipt OCR**, **recipe suggestions (L3–L4)**, and **style auto-classification**. Everything else works without one.

You can use any OpenAI-compatible inference server: Ollama, vLLM, LM Studio, a local llama.cpp server, or a commercial API.

## BYOK — Bring Your Own Key

BYOK means you provide your own LLM backend. Paid AI features are unlocked at **any tier** when a valid backend is configured. You pay for your own inference; Kiwi just uses it.

## Choosing a backend

| Backend | Best for | Notes |
|---------|----------|-------|
| **Ollama** | Local, easy setup | Recommended for getting started |
| **vLLM** | Local, high throughput | Better for faster hardware |
| **OpenAI API** | No local GPU | Requires paid API key |
| **Anthropic API** | No local GPU | Requires paid API key |

## Ollama setup (recommended)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model — llama3.1 8B works well for recipe tasks
ollama pull llama3.1

# Verify it's running
ollama list
```

In your Kiwi `.env`:

```bash
LLM_BACKEND=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=llama3.1
```

!!! note "Docker networking"
    Use `host.docker.internal` instead of `localhost` when Ollama is running on your host and Kiwi is in Docker.

## OpenAI-compatible API

```bash
LLM_BACKEND=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o-mini
```

## Verify the connection

In the Kiwi **Settings** page, the LLM status indicator shows whether the backend is reachable. A green checkmark means OCR and L3–L4 recipe suggestions are active.

## What LLM is used for

| Feature | LLM required |
|---------|-------------|
| Receipt OCR (line-item extraction) | Yes |
| Recipe suggestions L1 (pantry match) | No |
| Recipe suggestions L2 (substitution) | No |
| Recipe suggestions L3 (style templates) | Yes |
| Recipe suggestions L4 (full generation) | Yes |
| Style auto-classifier | Yes |

L1 and L2 suggestions use deterministic matching — they work without any LLM configured. See [Recipe Engine](../reference/recipe-engine.md) for the full algorithm breakdown.

## Model recommendations

- **Receipt OCR**: any model with vision capability (LLaVA, GPT-4o, etc.)
- **Recipe suggestions**: 7B–13B instruction-tuned models work well; larger models produce more creative L4 output
- **Style classification**: small models handle this fine (3B+)
