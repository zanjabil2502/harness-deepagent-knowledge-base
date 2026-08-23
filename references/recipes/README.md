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
Skill ini secara keseluruhan tidak pernah meminta API key; satu-satunya tempat
`ANTHROPIC_API_KEY` disebut adalah keempat skrip demo di direktori ini, dan
hanya sebagai jalur opsional:

- **Tanpa key** (keadaan normal): skrip mencetak bahwa konstruksi terverifikasi,
  lalu keluar dengan exit code 0. Bukan kegagalan, bukan pula sesuatu yang
  kurang — pembuktian API-nya sudah selesai di titik ini.
- **Dengan key**: skrip melanjutkan satu giliran nyata (`agent.invoke(...)`) dan
  mencetak respons model. Berguna kalau ingin melihatnya berjalan, tidak
  menambah apa pun pada verifikasi nama/signature API.

Di lingkungan CI/dev tanpa `ANTHROPIC_API_KEY`, keempat skrip tetap harus
selesai (`exit 0`) lewat jalur konstruksi — itulah yang diverifikasi task ini,
**bukan** bahwa model benar-benar dipanggil.
