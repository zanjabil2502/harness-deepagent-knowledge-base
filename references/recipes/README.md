# Recipes `deepagents`

Kode `deepagents` yang benar-benar jalan (bukan cuplikan dari ingatan),
dipasangkan dengan `references/systems/deepagents.md` (T1). Tiap skrip berdiri
sendiri, punya blok `if __name__ == "__main__":`, dan diawali docstring yang
menyebut apa yang didemokan, arketipe mana yang terbantu, dan konsep mana
yang diilustrasikan.

## Menjalankan

```bash
cd references/recipes
uv sync
uv run python 01_minimal_agent.py
uv run python 02_custom_middleware.py
uv run python 03_subagents.py
uv run python 04_custom_backend.py
```

## Aturan verifikasi

Tiap skrip **selalu** membangun agent nyata — `create_deep_agent(...)`,
middleware, backend, dan (bila relevan) config subagent nyata — lalu
mencetak ringkasan konstruksi. Ini sudah cukup untuk membuktikan tiap nama
API, signature, dan parameter yang dipakai benar-benar ada: kalau ada
parameter yang salah, konstruksi akan raise dan kegagalannya langsung
terlihat.

Konstruksi itulah verifikasinya, dan ia **tidak butuh kredensial apa pun**.
Keempat skrip sengaja tidak memanggil model: tidak ada `agent.invoke(...)`,
tidak ada environment variable yang dibaca, tidak ada yang menyentuh jaringan.
Skill ini secara keseluruhan tidak pernah meminta API key.

Keempatnya harus selesai dengan `exit 0` di lingkungan mana pun, termasuk CI
tanpa kredensial apa pun. Itulah yang diverifikasi — **bukan** bahwa model
benar-benar dipanggil.
