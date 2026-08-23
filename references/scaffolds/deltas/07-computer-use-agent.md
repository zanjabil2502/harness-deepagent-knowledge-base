# Delta 07 — Computer-Use Agent

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/07-computer-use-agent.md`](../../archetypes/07-computer-use-agent.md)
§Bangun ini pakai deepagents.

## Ganti

- **Tool surface**: `tools=[click_tool, type_tool, screenshot_tool, ...]`
  custom, dipetakan ke backend automasi browser eksternal (Playwright/CDP)
  — deepagents sendiri tidak menyediakan tool computer-use bawaan. `_base`
  tidak memasang `tools=`. `[code]` sumber signature `create_deep_agent`
  (`tools`), archetype 07.
- **Backend**: `StoreBackend(namespace=...)` (`_base`) → backend keluarga
  sandbox yang sama levelnya dengan delta 02 (mis. `DaytonaSandbox` atau
  setara) membungkus proses browser — sesi browser yang crash/di-abuse
  tidak boleh menyentuh compute lain. `[code]` sumber
  `libs/partners/daytona/README.md`.

## Tambah

- **Safety gate**: `interrupt_on={"submit_form": True, "click":
  {"allowed_decisions": ["approve", "reject"]}}` — `_base` tidak memasang
  `interrupt_on`. `[code]` pola `allowed_decisions` per-tool dikutip
  `test_hitl.py`.
- **Loop verifikasi**: tool `verify_state` yang wajib dipanggil setelah
  tiap tool aksi UI, ditegakkan lewat konvensi instruksi `system_prompt`
  (bukan middleware — deepagents tidak punya middleware yang menegakkan
  urutan pemanggilan tool). `[ours]` archetype 07: vanilla
  `create_deep_agent` mengasumsikan tool call itu sendiri sudah membawa
  hasilnya (`ToolMessage`) tanpa fase verifikasi terpisah; kita menyimpang
  karena computer-use tidak punya jaminan bahwa hasil aksi = hasil yang
  terlihat di layar. `PatchToolCallsMiddleware` (sudah ada di stack default
  `_base`) tidak relevan untuk ini — perannya cuma menambal `ToolMessage`
  dangling di riwayat, bukan menegakkan urutan eksekusi tool.

## Buang

- **Isolasi lewat "proses/container terpisah per user"** (pola delta 01) —
  tidak dibutuhkan, backend sandbox sudah menyediakan isolasi per sesi
  browser secara bawaan (sama alasan delta 02, `sandboxing.md` baris
  microVM).
