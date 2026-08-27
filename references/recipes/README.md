# `deepagents` recipes

`deepagents` code that actually runs (not snippets written from memory),
paired with `references/systems/deepagents.md` (T1). Each script stands on
its own, has an `if __name__ == "__main__":` block, and opens with a
docstring naming what it demonstrates, which archetype it serves, and
which concept it illustrates.

## Running them

```bash
cd references/recipes
uv sync
uv run python 01_minimal_agent.py
uv run python 02_custom_middleware.py
uv run python 03_subagents.py
uv run python 04_custom_backend.py
```

## Verification rule

Every script **always** builds a real agent - `create_deep_agent(...)`,
real middleware, a real backend, and (where relevant) real subagent
config - then prints a construction summary. That alone proves every API
name, signature, and parameter it uses genuinely exists: a wrong parameter
makes construction raise, and the failure is immediately visible.

Construction *is* the verification, and it **needs no credentials at
all**. The four scripts deliberately never call a model: no
`agent.invoke(...)`, no environment variable is read, nothing touches the
network. This skill as a whole never asks for an API key.

All four must exit with `exit 0` in any environment, including CI with no
credentials whatsoever. That is what is verified - **not** that a model
was actually called.
