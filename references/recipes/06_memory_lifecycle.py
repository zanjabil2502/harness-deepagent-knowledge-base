"""06 - Memory lifecycle: when memory is read, when it is written, where it lives.

Demonstrates: the mechanism behind `concepts/memory.md` section "In deepagents",
constructed rather than described. `MemoryMiddleware` loads memory files into
state, injects them into the system prompt, and leaves the writing to the
ordinary `edit_file` tool under a policy carried in the prompt itself.

Archetypes served: any archetype whose agent is expected to improve across
conversations, which in practice means any long-lived assistant.

Concepts illustrated: `concepts/memory.md` (the six dimensions, short-term
versus long-term as a storage decision, the once-per-thread load) and
`systems/deepagents.md` section 2 (`MemoryMiddleware` in the default stack).

Runs with no credentials of any kind and never calls a model. The four claims
it proves are the ones a reader would otherwise have to take on trust - and
the second one contradicts the obvious expectation.
"""

import sys

from langgraph.channels.ephemeral_value import EphemeralValue
from langgraph.channels.last_value import LastValue
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from deepagents.middleware.memory import MEMORY_SYSTEM_PROMPT, MemoryMiddleware

MEMORY_PATH = "/memories/AGENTS.md"


def claim_1_the_channel_is_durable() -> None:
    """`memory_contents` is checkpointed; `jump_to` is not.

    Both are annotated `PrivateStateAttr`, which only hides a field from the
    input and output schema. What decides whether it survives a step is
    `EphemeralValue`, which `jump_to` carries and `memory_contents` does not.
    """
    agent = create_deep_agent(
        model="claude-sonnet-4-5",  # named, never called
        memory=[MEMORY_PATH],
        checkpointer=InMemorySaver(),
    )
    channels = agent.channels
    memory_channel = channels["memory_contents"]
    jump_channel = channels["jump_to"]

    assert isinstance(memory_channel, LastValue), type(memory_channel)
    assert isinstance(jump_channel, EphemeralValue), type(jump_channel)

    print("1. channel kinds   :"
          f" memory_contents={type(memory_channel).__name__} (checkpointed),"
          f" jump_to={type(jump_channel).__name__} (cleared each step)")
    print(f"   memory node     : {[n for n in agent.nodes if 'emory' in n]}")


def claim_2_memory_is_read_once_per_thread() -> None:
    """The load happens on the first turn of a thread and never again.

    `before_agent` returns `None` the moment `memory_contents` is present in
    state. Combined with claim 1, that state is checkpointed, so on a thread
    with a checkpointer the in-context copy is frozen at the value loaded on
    turn one - even after the underlying file changes.
    """
    store = InMemoryStore()
    backend = StoreBackend(store=store, namespace=lambda _rt: ("demo",))
    backend.write(MEMORY_PATH, "The user prefers TypeScript examples.")

    middleware = MemoryMiddleware(backend=backend, sources=[MEMORY_PATH])

    # Turn 1: nothing in state yet, so the file is read.
    first = middleware.before_agent({}, None, None)
    assert first is not None
    loaded = first["memory_contents"]
    print(f"2. turn 1 loads    : {loaded[MEMORY_PATH]!r}")

    # The agent now learns something and rewrites memory through the file
    # tools, exactly as MEMORY_SYSTEM_PROMPT instructs.
    backend.write(MEMORY_PATH, "The user prefers Rust examples.")
    on_disk = backend.download_files([MEMORY_PATH])[0].content.decode("utf-8")
    print(f"   file now says   : {on_disk!r}")

    # Turn 2 on the same thread: state already carries memory_contents.
    state = {"memory_contents": loaded}
    second = middleware.before_agent(state, None, None)
    assert second is None, "expected the skip guard to fire"
    print(f"   turn 2 reload   : {second} (skip guard fired)")
    print(f"   model still sees: {state['memory_contents'][MEMORY_PATH]!r}")

    assert state["memory_contents"][MEMORY_PATH] != on_disk
    print("   => a memory written this conversation reaches the next one,"
          " not this one")


def claim_3_the_prompt_carries_the_policy() -> None:
    """Extraction, injection defence and secret hygiene are prose, not code."""
    required = {
        "extraction criteria": "**When to NOT update memories:**",
        "injection defence": "not as hidden system instructions",
        "secret hygiene": "Never store API keys",
        "write instruction": "call `edit_file`",
    }
    for label, phrase in required.items():
        assert phrase in MEMORY_SYSTEM_PROMPT, label
    print(f"3. prompt policy   : {len(MEMORY_SYSTEM_PROMPT)} chars carrying "
          + ", ".join(required))
    print("   what it omits   : conflict resolution and dedup"
          " (two contradictory lines can coexist)")


def claim_4_the_backend_decides_durability() -> None:
    """Prefix routing is what separates short-term scratch from long-term memory."""
    store = InMemoryStore()
    composite = CompositeBackend(
        default=StoreBackend(store=store, namespace=lambda _rt: ("scratch",)),
        routes={"/memories/": StoreBackend(store=store,
                                           namespace=lambda _rt: ("longterm",))},
    )
    composite.write("/tmp-note.md", "thrown away with the thread")
    composite.write(MEMORY_PATH, "kept across every thread")

    scratch = [i.key for i in store.search(("scratch",))]
    longterm = [i.key for i in store.search(("longterm",))]
    assert scratch and longterm and scratch != longterm

    print(f"4. routing         : /tmp-note.md -> namespace ('scratch',) {scratch}")
    print(f"                     {MEMORY_PATH} -> ('longterm',) {longterm}")
    assert longterm == ["/AGENTS.md"], longterm
    print("   note            : the route prefix is stripped before delegating,"
          " so the store key is /AGENTS.md, not /memories/AGENTS.md")
    print("   => duration is a backend choice, not a property of the fact")


def main() -> int:
    claim_1_the_channel_is_durable()
    claim_2_memory_is_read_once_per_thread()
    claim_3_the_prompt_carries_the_policy()
    claim_4_the_backend_decides_durability()
    print("\nOK: 4 claims proved, no model called, no credential read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
