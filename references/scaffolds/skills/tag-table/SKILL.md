---
name: tag-table
description: Emit tabular data as a validated ```table JSON block so the app renders a real table instead of markdown pipes. Use when the answer compares items across attributes, lists records with repeated fields, or shows a matrix - including requests phrased as tabel, tabla, 表, or "show me a table".
---

# Emit tabular data as a `table` block

## When to use it

Use it when the answer holds **several entities sharing the same
attributes**: a comparison, a list of records, a matrix, a columnar summary.

Don't use it for: a single key-value pair (write it as prose or a list),
hierarchical text that isn't data (use headings), or numbers along a time
series that read better as a chart - use `tag-chart` for that.

## The shape

Emit a fenced block with the info string `table`. Its content is a single JSON
document.

````
```table
{
  "v": 1,
  "caption": "Perbandingan paket langganan",
  "columns": [
    {"key": "plan",    "label": "Paket",       "type": "text"},
    {"key": "price",   "label": "Harga/bulan", "type": "number", "align": "right"},
    {"key": "seats",   "label": "Kursi",       "type": "number", "align": "right"},
    {"key": "sso",     "label": "SSO",         "type": "bool"}
  ],
  "rows": [
    {"plan": "Starter",  "price": 0,      "seats": 3,   "sso": false},
    {"plan": "Team",     "price": 250000, "seats": 25,  "sso": false},
    {"plan": "Business", "price": 900000, "seats": 100, "sso": true}
  ]
}
```
````

(The example's labels are Indonesian on purpose: the `key`s stay
language-neutral while the `label`s follow the conversation's language - the
rule below.)

### The fields

| Field | Required | Content |
|---|---|---|
| `v` | yes | The schema version. Always `1`. |
| `columns[].key` | yes | A language-neutral identifier, `snake_case`. It becomes the key in each `rows` object. |
| `columns[].label` | yes | The header text, **in the conversation's language**. |
| `columns[].type` | yes | `text` \| `number` \| `date` \| `bool`. |
| `columns[].align` | no | `left` \| `right` \| `center`. Default: `right` for `number`, `left` otherwise. |
| `rows[]` | yes | Objects with exactly the keys from `columns[].key`. |
| `caption` | no | One explanatory line above the table. |
| `note` | no | One note line below the table (a source, an assumption, units). |

## The rules

**Keys are language-neutral, labels follow the conversation's language.**
`key` is a machine identifier and never changes whether the answer is in
Indonesian, English, or anything else. Only `label` and `caption` change.
Never use a label as a key.

**Every row carries every key.** An unknown value is written `null`, not
omitted and not filled with `"-"`. A renderer distinguishing "empty" from
"zero" depends on this.

**Numbers are numbers.** `250000`, not `"Rp250.000"`. Units and currency
formatting are the renderer's business; put the unit in `label` or `note`.
Dates use ISO-8601 (`2026-01-15`), not a local format.

**Above ~50 rows, don't inline it.** Store it as an artifact and reference it
with one sentence plus a link. A long table floods the context and is
unreadable in a chat.

**One table per block.** Two comparisons that don't share columns are two
blocks, not one table with empty columns everywhere.

## After the block

A block doesn't explain itself. Include one or two prose sentences stating its
**finding** - what the reader should see - rather than re-reading its cells.
