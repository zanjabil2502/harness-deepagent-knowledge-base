# 4. Research/Analyst

## Definisi

Agent yang menjalankan loop search → read → synthesize untuk menghasilkan
jawaban tertulis yang **wajib bersitasi**, dengan budget token/waktu
eksplisit karena satu topik riset bisa memicu puluhan pencarian. Delegasi
lazim dipakai untuk paralelisasi sub-topik, tapi tujuannya tetap satu
dokumen sintesis di akhir, bukan aksi di sistem lain.

Batas terhadap tetangga: beda dari **General Task Agent** (03) karena
artefak keluarannya selalu jawaban/laporan tertulis dengan provenance,
bukan campuran file/aksi bebas; beda dari **In-App Copilot** (05) karena
tidak terikat ke satu produk/API tertentu — sumbernya web/dokumen terbuka;
beda dari **Workflow Agent** (06) karena horizon-nya satu sesi riset, bukan
proses berulang tanpa akhir.

## Posisi di 6 sumbu

| Sumbu | Nilai |
|---|---|
| Blast radius | Dunia luar (web search, retrieval dokumen), read-only |
| Artefak | Jawaban/laporan tertulis dengan sitasi |
| Horizon | Satu sesi riset (bisa panjang, tapi berakhir di satu laporan) |
| Kendali manusia | Review hasil akhir; jarang approve tiap pencarian |
| Permukaan domain | General atau vertikal (legal, finansial, akademik) |
| Antarmuka | Chat, dengan panel sumber/sitasi |

## Konsekuensi harness

1. **Loop shape: search → read → synthesize eksplisit**, bukan ReAct bebas
   — tiap iterasi harus jelas fase mana yang sedang berjalan supaya budget
   bisa dialokasikan per fase, bukan dihabiskan di satu fase saja.
2. **Budget token/iterasi keras dibatasi per sub-riset** — tanpa batas,
   satu sub-topik bisa menyedot seluruh anggaran sebelum topik lain
   sempat diproses; batas eksplisit memaksa breadth-first coverage.
3. **Provenance wajib melekat di tiap klaim**, bukan ditambahkan belakangan
   — kalau sitasi dipasang setelah sintesis selesai, klaim dan sumbernya
   gampang tidak lagi berkorespondensi 1:1.
4. **Delegation untuk paralelisasi sub-topik**, dengan hasil subagent
   berupa ringkasan + daftar sumber (bukan transkrip pencarian mentah)
   supaya context penyintesis utama tidak tenggelam di detail pencarian.

## Sistem contoh

- **deep_research (deepagents)** `[code]` — contoh resmi yang mendefinisikan
  `research_sub_agent` dengan tool `tavily_search` + `think_tool`, dan
  membatasi lingkup lewat `max_concurrent_research_units = 3` serta
  `max_researcher_iterations = 3` di level orchestrator. Ini adalah
  implementasi terbaca dari arketipe ini, bukan sekadar deskripsi
  perilaku. Sumber: `examples/deep_research/research_agent.ipynb`
  (langchain-ai/deepagents).
- **Perplexity** `[inferred]` — dari perilaku produk: jawaban selalu
  disertai daftar sumber bernomor yang bisa ditelusuri balik ke hasil
  pencarian.
- **OpenAI Deep Research** `[inferred]` — dari perilaku produk: sesi riset
  panjang (menit-jam) yang mengeluarkan satu laporan terstruktur dengan
  sitasi di akhir, bukan jawaban instan.
- **Elicit** `[inferred]` — dari perilaku produk: berfokus pada literatur
  akademik, jawaban ditautkan ke paper spesifik per klaim.

## Jebakan khas

1. **Sitasi halusinasi** — model menyebut sumber yang tidak pernah benar-benar
   diambil di langkah retrieval, karena tidak ada penegakan bahwa setiap
   sitasi harus menunjuk ke hasil tool call nyata dalam transkrip.
2. **Budget habis di satu sub-topik yang "menarik"** — tanpa batas iterasi
   per subagent, riset melebar tak terkendali ke satu cabang dan topik
   lain di brief awal tidak pernah tersentuh.
3. **Sumber berkualitas rendah tidak difilter** — loop search→read yang
   naif memperlakukan semua hasil pencarian setara, sehingga blog
   spekulatif dan dokumentasi resmi mendapat bobot sitasi yang sama.
4. **Sintesis akhir kehilangan jejak ke pencarian asal** — kalau ringkasan
   subagent tidak membawa metadata sumber, penyintesis utama harus
   menebak/mengarang ulang sitasi saat menyusun laporan akhir.

## Bangun ini pakai deepagents

- **Delegation**: subagent riset didefinisikan sebagai dict
  `{"name": "research-agent", "description": "...", "system_prompt": ...,
  "tools": [web_search_tool, think_tool]}`, dipanggil lewat tool `task`
  bawaan `SubAgentMiddleware`. `[code]` — sumber:
  `examples/deep_research/research_agent.ipynb`.
- **Budget/loop limit**: batas eksplisit di level orchestrator seperti
  `max_concurrent_research_units` dan `max_researcher_iterations` —
  dikontrol di kode pemanggil subagent, bukan parameter bawaan
  `create_deep_agent`. `[code]` — sumber sama.
- **Tool surface**: tool pencarian sempit (`web_search`) + `think_tool`
  untuk memaksa langkah refleksi sebelum lanjut mencari — bukan tool
  bash luas seperti Workspace Agent, karena blast radius arketipe ini
  read-only terhadap dunia luar. `[code]`.
- **Provenance/output**: `response_format` di `create_deep_agent` untuk
  memaksa skema keluaran terstruktur (mis. daftar klaim + sitasi), bukan
  teks bebas — parameter ini ada di signature `create_deep_agent`.
  `[code]` — sumber: `graph.py`. `[ours]` Kami menambahkan validasi
  post-hoc yang mencocokkan tiap sitasi di `response_format` terhadap
  hasil tool call `web_search` di transkrip; vanilla `response_format`
  hanya memvalidasi bentuk skema, bukan bahwa isinya benar-benar berasal
  dari tool call nyata — celah itu yang membuat sitasi halusinasi
  (Jebakan #1) mungkin lolos kalau tidak ditambal.

## Sumber

- deepagents `examples/deep_research/research_agent.ipynb`, `graph.py` —
  `[code]` — Context7 `/langchain-ai/deepagents`,
  https://github.com/langchain-ai/deepagents
- Perplexity, OpenAI Deep Research, Elicit — `[inferred]` — perilaku
  produk closed-source.
