---
name: tag-formula
description: Emit mathematical expressions as LaTeX in a ```math block so the app renders real notation instead of ASCII approximations. Use for equations, derivations, statistical formulas, and symbolic definitions - including requests phrased as rumus, formula, persamaan, matematika, fórmula, or 数式.
---

# Emit mathematics as a `math` block

## When to use it

Use it when the notation **carries meaning** that is lost written as ordinary
text: fractions, roots, sigmas, integrals, matrices, subscripts/superscripts,
Greek letters.

Don't use it for simple arithmetic that reads clearly in a sentence ("up 12%
from 1,240 to 1,390"). Notation for something that needs no notation slows the
reader down.

## The shape

A standalone equation uses a fenced `math` block, with no `$$` inside it:

````
```math
\text{skor} = \frac{\sum_{i=1}^{n} w_i \cdot x_i}{\sum_{i=1}^{n} w_i}
```
````

A symbol embedded in a sentence uses inline `$…$`: "the weight $w_i$
normalises each component". Don't use a block for a single symbol; don't use
inline for a multi-level equation.

## The rules

**Define every symbol.** After the block, state what each variable means and
its units. A formula with no symbol list can't be verified by the reader.

**Variable names are language-neutral, their explanation follows the
conversation's language.** Mathematical symbols are already universal - don't
translate $x$ into $k$ because the language changed. What gets translated is
only the explanatory prose and the content of `\text{…}`.

**Wrap words in `\text{…}`.** A bare word in math mode renders as a
letter-by-letter multiplication: `skor` becomes $s\cdot k\cdot o\cdot r$.

**Don't use `\href`, `\includegraphics`, `\input`, or `\write`.** All of them
reach beyond mathematics and are refused by a safe renderer.

**Stick to the standard macros** KaTeX/MathJax knows. Full LaTeX packages
(`amsmath` beyond the common set, `tikz`, custom environments) aren't
available in a web renderer and either fail silently or produce a red block.

**Step-by-step derivations use `aligned`**, one step per line, aligned on the
`=`:

````
```math
\begin{aligned}
  p &= \frac{1}{1 + e^{-z}} \\
  z &= \beta_0 + \beta_1 x
\end{aligned}
```
````

**One equation per block.** Two unrelated formulas are two blocks with prose
between them, not one block with multiple lines.

## After the block

State **what the formula does** in one sentence, then list its symbols. A
reader who can't parse the notation must still understand its point.
