---
name: tag-chart
description: Emit quantitative data as a validated ```chart JSON block so the app renders a real chart instead of describing numbers in prose. Use when the answer shows a trend over time, compares magnitudes across categories, or breaks a total into parts — including requests phrased as chart, grafik, diagram batang, gráfico, or 図表.
---

# Emit quantitative data as a `chart` block

## When to use it

Use it when what matters is the **shape of the numbers** rather than their
exact values: a trend over time, a comparison of magnitudes across categories,
the composition of a total.

Don't use it when the reader needs to read exact values — that is a table
(`tag-table`). Don't use it for one or two numbers; a sentence is clearer. If
both are needed (the shape **and** the values), emit a chart then a table
rather than a chart with a value label on every point.

## The shape

A fenced block with the info string `chart`, its content a single JSON
document.

````
```chart
{
  "v": 1,
  "type": "line",
  "caption": "Pengguna aktif bulanan",
  "x": {"key": "period", "label": "Bulan", "type": "date"},
  "series": [
    {"key": "active", "label": "Aktif",     "unit": "user"},
    {"key": "new",    "label": "Pendaftar", "unit": "user"}
  ],
  "data": [
    {"period": "2026-01", "active": 1240, "new": 180},
    {"period": "2026-02", "active": 1390, "new": 210},
    {"period": "2026-03", "active": 1610, "new": 265}
  ]
}
```
````

(As in `tag-table`, the example's labels are Indonesian on purpose while its
keys stay language-neutral.)

### The fields

| Field | Required | Content |
|---|---|---|
| `v` | yes | The schema version. Always `1`. |
| `type` | yes | `line` \| `bar` \| `area` \| `pie` \| `scatter`. |
| `x.key` | yes | A language-neutral identifier for the category/time axis. |
| `x.label` | yes | The axis text, in the conversation's language. |
| `x.type` | no | `date` \| `text` \| `number`. Defaults to `text`. |
| `series[].key` | yes | A language-neutral identifier; it becomes the key in each `data` object. |
| `series[].label` | yes | The series name in the legend, in the conversation's language. |
| `series[].unit` | no | The unit (`user`, `IDR`, `%`, `ms`). The renderer uses it for the axis and tooltips. |
| `data[]` | yes | Objects containing `x.key` plus each `series[].key`. |
| `caption` | no | One explanatory line. |
| `note` | no | The data's source, assumptions, or limits. |

For `pie`, use exactly **one** series; each `data` entry becomes one slice.

## The rules

**Keys are language-neutral, labels follow the conversation's language** —
exactly as in `tag-table`. Changing language means changing `label`, never
`key`.

**Mixed units need separate axes or separate charts.** Putting currency and
percentages on one axis produces a misleading graph. If the units differ in
scale, emit two blocks.

**Raw numbers, unformatted.** `1240`, not `"1,240"`. Percentages as the number
itself (`12.4` with `"unit": "%"`), not `0.124`.

**Data points ordered** by `x`. The renderer doesn't re-sort them.

**Missing values are written `null`**, not `0`. Zero is a measurement; `null`
is the absence of one, and a line diving to zero because the data hasn't
arrived yet is a graphical lie.

**Above ~200 data points, don't inline it** — aggregate first (per week, per
month), or store it as an artifact.

## After the block

One or two sentences stating what the shape shows — the trend's direction, an
inflection point, a gap between series. Not a re-reading of the numbers.
