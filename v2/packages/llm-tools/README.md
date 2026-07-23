# llm-tools (V2)

A real, read-only GRC tool — `generate_text` — that turns a prompt into generated text by **wrapping
the frozen generation stack**. It re-implements nothing and imports no SDK: it builds a
provider-agnostic `LLMRequest` and calls an **injected `GenerationProvider`** — a `generation-engine`
adapter (Claude / Gemini / Ollama / OpenAI) or the `GenerationEngine` that wraps one (retry / metrics
/ error translation). The composition root injects the provider; the tool depends only on the pure
`GenerationProvider` port (runtime deps: `tool-registry` + `pipeline-contracts`).

    Mission → ExecutionPort → RegistryExecutor → generate_text → GenerationProvider → Answer

## `generate_text` vs the Pipeline Tool

- **Pipeline Tool** — grounded RAG: retrieve, then generate, with citations. Use for factual GRC
  answers.
- **`generate_text` (this tool)** — **raw generation** for generative tasks (drafting a policy,
  summarizing, rewriting) where the capability supplies its own context. It carries **no citations**
  (`source_ids` empty, by design) — grounding is the Pipeline/Search tools' job.

## Contract

- **Input:** the step `instruction` is the prompt. An optional `system_prompt` (constructor) is
  threaded as a system segment.
- **Output:** a `ToolStepResult` (ADR 0049) — `output` is the generated text; `warnings` carries the
  answer's warnings.
- **Failure is safe:** an empty prompt, or a `GenerationError` from the provider, returns `ok=False`
  (the Mission fails safe, ADR 0042 §7) — the SDK exception never crosses the tool boundary.

## Usage

```python
from generation_engine import ClaudeGenerationProvider, GenerationEngine
from llm_tools import LLMTool
from tool_registry import ToolRegistry

provider = GenerationEngine(ClaudeGenerationProvider(...))   # retry/metrics around the adapter
registry = ToolRegistry()
registry.register(LLMTool(provider, system_prompt="You are a GRC policy author."))

# a step then names it: PlanStep(instruction="draft an acceptable use policy", tool="generate_text")
```

## Tests

`uv run pytest` drives the tool with a fake `GenerationProvider` and with the **real**
`GenerationEngine` wrapping it: request construction (TOOL family, prompt as the user message, system
prompt threaded), generation, fail-safe on provider error, and a mission **E2E** through the real
`RegistryExecutor`. No network, no SDK. `ruff` + `mypy --strict` clean.
