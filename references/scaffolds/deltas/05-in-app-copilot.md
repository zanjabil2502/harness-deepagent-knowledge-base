# Delta 05 — In-App Copilot

Basis: [`../_base.md`](../_base.md). File ini **hanya** selisihnya. Rasional
lengkap: [`../../archetypes/05-in-app-copilot.md`](../../archetypes/05-in-app-copilot.md)
§Bangun ini pakai deepagents.

## Ganti

- **Tool surface**: `tools=[...]` custom, tiap tool adalah wrapper tipis ke
  satu endpoint API produk tuan rumah, dipetakan manual — filesystem
  bawaan deepagents dimatikan total lewat
  `permissions=[FilesystemPermission(operations=["read", "write"],
  paths=["/**"], mode="deny")]` (`operations` cuma menerima
  `"read"`/`"write"`, keduanya wajib diisi — bukan parameter opsional.
  `[code]` sumber `deepagents/middleware/filesystem.py`, dibaca langsung
  dari `references/recipes/.venv`). `execute` tidak perlu ditutup terpisah
  — sama seperti delta 04, backend `_base` (`StoreBackend`) tidak
  mengimplementasikan `SandboxBackendProtocol`, jadi tool itu tidak pernah
  terdaftar. `_base` tidak memasang `tools=` dan tidak mematikan filesystem
  sama sekali. `[code]` sumber signature `create_deep_agent` (`tools`,
  `permissions`), archetype 05.
- **Backend**: `StoreBackend(namespace=...)` (`_base`, durable per-user) →
  `StateBackend` default (thread-scoped, tidak durable) — tidak ada
  artefak file yang perlu bertahan lintas thread; sumber kebenaran tetap di
  produk tuan rumah, bukan di agent. `[code]` sumber `ARCHITECTURE.md`.
- **Context**: bukan `memory=[...]` lintas sesi — context datang dari state
  aplikasi tuan rumah yang disuntikkan lewat `context_schema` per
  panggilan. `[code]` parameter `context_schema` ada di signature
  `create_deep_agent`.

## Tambah

- **Safety gate**: tool `undo_<aksi>` eksplisit dipasangkan ke tiap tool
  aksi produk, dipanggil dari UI host — bukan `interrupt_on`. `[ours]`
  archetype 05: vanilla `HumanInTheLoopMiddleware` dirancang untuk
  approve/edit/reject **sebelum** eksekusi; kita menyimpang ke pola "aksi
  dulu, undo tersedia" karena horizon pendek arketipe ini membuat jeda
  approval terasa sebagai regresi UX dibanding produk tuan rumah yang sudah
  cepat.

## Buang

- **`ScopeMiddleware` membaca `x-user-id` dari header mentah** (`_base`) —
  tetap dipakai untuk identitas request, tapi **tidak** dipakai untuk
  `StoreBackend.namespace` (backend-nya sudah `StateBackend`, tidak butuh
  namespace) — dicatat eksplisit supaya tidak ada kode sisa yang
  mengasumsikan namespace per-user yang sebenarnya sudah tidak dipakai.
- **`memory=[...]` lintas sesi** — dinyatakan eksplisit TIDAK dipasang
  (bukan cuma "kebetulan tidak ada" seperti di `_base`) karena horizon
  pendek arketipe ini tidak punya memory lintas dokumen yang perlu
  dipertahankan agent (`## Konsekuensi harness` archetype 05, poin 4).
