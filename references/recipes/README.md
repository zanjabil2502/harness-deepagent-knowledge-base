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

Setelah konstruksi, skrip mengecek env var `ANTHROPIC_API_KEY`:

- **Tidak ada**: cetak satu baris bahwa invokasi live dilewati karena tidak
  ada kredensial, lalu keluar dengan exit code 0. Ini bukan kegagalan.
- **Ada**: jalankan satu giliran nyata (`agent.invoke(...)`) dan cetak
  respons model.

Di lingkungan CI/dev tanpa `ANTHROPIC_API_KEY`, keempat skrip tetap harus
selesai (`exit 0`) lewat jalur konstruksi — itulah yang diverifikasi task ini,
**bukan** bahwa model benar-benar dipanggil.
