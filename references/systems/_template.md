# `systems/` template

Copy this file for each new system in the `systems/` grid. Replace every
instruction sentence with real content, and delete the label line once every
claim in the body carries its own.

> Label every claim: [code] / [docs] / [inferred]

## Archetype

Name this system's archetype (hybrids allowed) and give a short reason based on
the 6 discriminating axes.

## 1. Loop shape

Describe its loop shape: ReAct / plan-execute / loop-until-done, and who
decides it stops.

## 2. Context

Describe the compaction, summarisation, or filesystem-as-memory strategy this
system uses.

## 3. Tool surface

Describe whether this system uses many narrow tools or few broad ones, and why
that design was chosen.

## 4. Delegation

Describe whether there are subagents or a flat architecture, and how a
delegation's result returns to its caller.

## 5. State & resume

Describe the todo, scratchpad, checkpoint, and resume mechanisms in use.

## 6. Safety gate

Describe when this system asks for human permission and what is sandboxed.

## 7. Capability routing & policy

Describe how the system decides which skill/mode is used: prose + model
judgement, a declarative manifest, or a classifier.

## Sources

Cite the source of every claim: repo/commit for `[code]`, a link to official
documentation for `[docs]`, or a note that it is concluded from the product's
behaviour for `[inferred]`.
