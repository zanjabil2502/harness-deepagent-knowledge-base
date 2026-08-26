> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Models

> Configure model providers and parameters for Deep Agents

Deep Agents work with any [LangChain chat model](/oss/python/langchain/models) that supports [tool calling](/oss/python/langchain/models#tool-calling).

## Supported models

Specify models in `provider:model` format (for example, `google_genai:gemini-3.6-flash`, `openai:gpt-5.4`, or `anthropic:claude-sonnet-4-6`). The provider prefix selects the LangChain integration, and everything after the colon is passed through to that provider as the model identifier. For valid provider strings, see the `model_provider` parameter of [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model). For provider-specific configuration, see [chat model integrations](/oss/python/integrations/chat).

The model identifier must match the format expected by the provider. Some providers use simple names like `gpt-5.5`; others use namespaced IDs or deployment paths like `zai-org/GLM-5.2`, so the full Deep Agents string would be `baseten:zai-org/GLM-5.2`. Check the provider's model catalog or integration docs for the current identifiers.

### Suggested models

These models perform well on the [Deep Agents eval suite](https://github.com/langchain-ai/deepagents/tree/main/libs/evals#readme), which tests basic agent operations. Passing these evals is necessary but not sufficient for strong performance on longer, more complex tasks.

| Provider                                                  | Models                                                  |
| --------------------------------------------------------- | ------------------------------------------------------- |
| [Google](/oss/python/integrations/providers/google)       | `gemini-3.1-pro-preview`, `gemini-3.6-flash`            |
| [OpenAI](/oss/python/integrations/providers/openai)       | `gpt-5.5`, `gpt-5.4`                                    |
| [Anthropic](/oss/python/integrations/providers/anthropic) | `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6` |
| Open-weight                                               | `GLM-5.2`, `Kimi-K2.7 Code`, `MiniMax-M3`               |

Open-weight models are available through providers like [Baseten](/oss/python/integrations/providers/baseten), [Fireworks](/oss/python/integrations/chat/fireworks), [OpenRouter](/oss/python/integrations/providers/openrouter), and [Ollama](/oss/python/integrations/providers/ollama).

### Model evaluations

The [Deep Agents eval suite](https://github.com/langchain-ai/deepagents/tree/main/libs/evals#readme) tests popular models:

<div className="deepagents-eval-category-matrix">
  | Model                                            |                                                                        Overall |                                                                        File Ops |                                                                       Retrieval |                                                                       Tool Use |                                                                         Memory |                                                                   Conversation |                                                                   Summarization |
  | :----------------------------------------------- | -----------------------------------------------------------------------------: | ------------------------------------------------------------------------------: | ------------------------------------------------------------------------------: | -----------------------------------------------------------------------------: | -----------------------------------------------------------------------------: | -----------------------------------------------------------------------------: | ------------------------------------------------------------------------------: |
  | google\_genai:gemini-3.6-flash                   |     [82%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** | **[90%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |     [54%](https://github.com/langchain-ai/deepagents/actions/runs/25290479270) |     [38%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |
  | openai:gpt-5.4                                   |     [18%](https://github.com/langchain-ai/deepagents/actions/runs/24906955930) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** |     [18%](https://github.com/langchain-ai/deepagents/actions/runs/24906955930) |     [51%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583) |     [38%](https://github.com/langchain-ai/deepagents/actions/runs/24425363630) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** |
  | openai:gpt-5.5                                   |     [80%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |     [84%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |     [64%](https://github.com/langchain-ai/deepagents/actions/runs/25345307822) | **[52%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |
  | anthropic:claude-opus-4-6                        |     [26%](https://github.com/langchain-ai/deepagents/actions/runs/24906955930) |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** |     [26%](https://github.com/langchain-ai/deepagents/actions/runs/24906955930) | **[69%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** |     [22%](https://github.com/langchain-ai/deepagents/actions/runs/24363491527) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/24172638583)** |
  | anthropic:claude-opus-4-7                        |     [80%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |     [82%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |                                                                              — |     [48%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |
  | baseten:moonshotai/Kimi-K2.6                     |     [79%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906) |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906)** |     [84%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906) |                                                                              — |     [43%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906) |      [60%](https://github.com/langchain-ai/deepagents/actions/runs/25475600906) |
  | baseten:zai-org/GLM-5                            |     [77%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424)** |     [89%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424) |     [44%](https://github.com/langchain-ai/deepagents/actions/runs/23872647281) |     [24%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424) |      [60%](https://github.com/langchain-ai/deepagents/actions/runs/25403850424) |
  | fireworks:accounts/fireworks/models/glm-5p1      |     [81%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650)** |     [87%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650) |                                                                              — |     [33%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650) |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25461031650) |
  | fireworks:accounts/fireworks/models/minimax-m2p7 |     [79%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412)** | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412)** |     [85%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412) |                                                                              — |     [43%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412) |      [60%](https://github.com/langchain-ai/deepagents/actions/runs/25403894412) |
  | ollama:minimax-m2.7:cloud                        |     [73%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |      [90%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |     [82%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |     [38%](https://github.com/langchain-ai/deepagents/actions/runs/23872647281) |     [29%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |      [60%](https://github.com/langchain-ai/deepagents/actions/runs/24106499785) |
  | openrouter:deepseek/deepseek-v4-flash            |     [81%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395)** |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395) | **[90%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395)** |                                                                              — |     [33%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395) |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25677815395) |
  | openrouter:minimax/minimax-m2.7                  |     [80%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535)** |     [89%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |                                                                              — |     [43%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |      [60%](https://github.com/langchain-ai/deepagents/actions/runs/25455998535) |
  | openrouter:z-ai/glm-5.1                          | **[89%](https://github.com/langchain-ai/deepagents/actions/runs/25387853856)** |      [92%](https://github.com/langchain-ai/deepagents/actions/runs/25234719085) | **[100%](https://github.com/langchain-ai/deepagents/actions/runs/25234686782)** |     [89%](https://github.com/langchain-ai/deepagents/actions/runs/25387853856) |                                                                              — |     [33%](https://github.com/langchain-ai/deepagents/actions/runs/25225620506) |      [80%](https://github.com/langchain-ai/deepagents/actions/runs/25235579950) |
</div>

For more information, see the [Eval runs](https://github.com/langchain-ai/deepagents/actions/workflows/evals.yml).

## Configure model parameters

Pass a model string to [`create_deep_agent`](https://reference.langchain.com/python/deepagents/graph/create_deep_agent) in `provider:model` format, or pass a configured model instance for full control. Under the hood, model strings are resolved via [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model).

To configure model-specific parameters, use [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model) or instantiate a provider model class directly:

<CodeGroup>
  ```python init_chat_model theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
  from langchain.chat_models import init_chat_model
  from deepagents import create_deep_agent

  model = init_chat_model(
      model="google_genai:gemini-3.6-flash",
      thinking_level="medium",  # [!code highlight]
  )
  agent = create_deep_agent(model=model)
  ```

  ```python Provider package theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
  from langchain_google_genai import ChatGoogleGenerativeAI
  from deepagents import create_deep_agent

  model = ChatGoogleGenerativeAI(
      model="gemini-3.1-pro-preview",
      thinking_level="medium",  # [!code highlight]
  )
  agent = create_deep_agent(model=model)
  ```
</CodeGroup>

<Note>
  Available parameters vary by provider. See the [chat model integrations](/oss/python/integrations/chat) page for provider-specific configuration options.
</Note>

### Provider profiles

A [`ProviderProfile`](/oss/python/deepagents/profiles#provider-profiles) packages initialization parameters that apply when you provide a `provider:model` string when creating the deep agent. It does not apply when you pass a preconfigured model with [`init_chat_model`](https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model).

You can register at two levels, and both can coexist:

* **Provider level** — a bare provider key like `"openai"` applies to every model from the `openai` provider.
* **Model level** — a `provider:model` key like `"openai:gpt-5.4"` applies only to that specific model, and merges on top of any matching provider-level profile.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from deepagents import ProviderProfile, register_provider_profile

# Provider-wide default: every openai model gets temperature=0.
register_provider_profile(
    "openai",
    ProviderProfile(init_kwargs={"temperature": 0}),
)

# Model-level override: gpt-5.5 additionally gets a specific reasoning effort.
# Inherits temperature=0 from the provider-level profile above.
register_provider_profile(
    "openai:gpt-5.5",
    ProviderProfile(init_kwargs={"reasoning_effort": "medium"}),
)
```

See [Profiles](/oss/python/deepagents/profiles) for the full field list, merge semantics, and plugin packaging.

<Tip>
  For shaping how the *agent* behaves once the model is built, use a [harness profile](/oss/python/deepagents/profiles#harness-profiles).
</Tip>

## Select a model at runtime

If your application lets users choose a model (for example using a dropdown in the UI), use [middleware](/oss/python/langchain/middleware) to swap the model at runtime without rebuilding the agent.

Pass the user's model selection through [runtime context](/oss/python/langchain/models#dynamic-model-selection), then use a `wrap_model_call` middleware to override the model on each invocation using the [`@wrap_model_call`](https://reference.langchain.com/python/langchain/agents/middleware/types/wrap_model_call) decorator:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from dataclasses import dataclass
from typing import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent


@dataclass
class Context:
    model: str


@wrap_model_call
def configurable_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    model_name = request.runtime.context.model
    model = init_chat_model(model_name)
    return handler(request.override(model=model))


agent = create_deep_agent(
    model="google_genai:gemini-3.6-flash",
    middleware=[configurable_model],
    context_schema=Context,
)

# Invoke with the user's model selection
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Hello!"}]},
    context=Context(model="openai:gpt-5.5"),
)
```

<Tip>
  For more dynamic model patterns (for example routing based on conversation complexity or cost optimization), see [Dynamic model](/oss/python/langchain/models#dynamic-model-selection) in the LangChain agents guide.
</Tip>

## Learn more

* [Models in LangChain](/oss/python/langchain/models): chat model features including tool calling, structured output, and multimodality

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to Claude, VSCode, and more via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/deepagents/models.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
