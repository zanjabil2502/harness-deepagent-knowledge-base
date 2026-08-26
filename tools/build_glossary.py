#!/usr/bin/env python3
"""Bangun references/GLOSSARY.md — pintu masuk lookup istilah.

Jalankan: python3 tools/build_glossary.py

Dua bagian, dua sumber kebenaran yang berbeda:

- **Istilah** dideklarasikan di `TERMS` di bawah. Definisinya ditulis
  tangan karena ini kosakata prosa, bukan simbol yang bisa diekstrak.
  Yang dicek mesin: berkas kanoniknya ada, dan benar-benar memuat
  istilahnya. Konsep yang dipindah atau diganti nama menggagalkan build.
- **Simbol deepagents** diturunkan dari `references/deepagents/graph/graph.json`
  ber-irisan dengan token berbacktick di KB. Grafnya yang menentukan apa
  yang dianggap simbol nyata, jadi tidak ada derau dari backtick biasa,
  dan lokasi `file:line`-nya datang dari AST, bukan ingatan.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "references"
GRAPH = REF / "deepagents" / "graph" / "graph.json"
OUT = REF / "GLOSSARY.md"
TOKEN = re.compile(r"`([A-Za-z_][\w.]*)`")

# (istilah, definisi satu baris, berkas kanonik relatif ke references/)
TERMS = [
    ("archetype", "One of 7 kinds of AI assistant, produced by cutting the 6 discriminating axes; it fixes the harness constraints from the outset.", "archetypes/README.md"),
    ("blast radius", "Seberapa jauh aksi agent bisa menyentuh dunia: mesin user, sandbox, data SaaS, atau sistem luar. Salah satu dari 6 sumbu, dan setengah dari kriteria layak-dihentikan.", "concepts/human-in-the-loop.md"),
    ("blueprint", "Keluaran utama mode membangun: enam keputusan harness yang dinyatakan eksplisit sebelum satu baris kode ditulis.", "blueprint-template.md"),
    ("by-reference", "Aturan bahwa transkrip menyimpan `artifact_id` + versi, bukan isi artefaknya; byte-nya hidup di storage.", "concepts/artifacts-and-canvas.md"),
    ("dynamic subagent", "Subagent yang di-dispatch dari dalam kode, bukan dipilih model per giliran; melewati gerbang approval per-dispatch.", "concepts/code-orchestration.md"),
    ("fail-closed", "Mode kegagalan di mana guardrail yang tidak bisa dijalankan menolak aksi. Aman, dengan ongkos ketersediaan.", "concepts/guardrails.md"),
    ("fail-deferred", "Mode kegagalan ketiga: aksi ditahan menunggu penegakan yang belum tersedia. Wajib dipasangkan timeout dan kebijakan saat habis, kalau tidak ia fail-open yang tertunda.", "concepts/guardrails.md"),
    ("fail-open", "Mode kegagalan di mana guardrail yang tidak bisa dijalankan membiarkan aksi lanjut. Murah, dan diam-diam meniadakan gerbangnya.", "concepts/guardrails.md"),
    ("golden transcript", "Transkrip acuan yang dipakai eval untuk menilai trajektori penuh, bukan cuma jawaban akhir.", "concepts/evaluation.md"),
    ("harness", "Lapisan di sekeliling model yang menentukan bentuk loop, konteks, permukaan tool, delegasi, dan guardrail — yang dirancang skill ini.", "concepts/agent-loop.md"),
    ("idempotency key", "Kunci yang membuat pengiriman ulang turn yang sama tidak menghasilkan eksekusi ganda; unik per user.", "concepts/persistence-schema.md"),
    ("intent vs ekspresi", "Pemisahan antara maksud yang netral bahasa (kode stabil) dan teks yang dilihat manusia (mengikuti locale). Dasar seluruh penanganan multilingual.", "concepts/multilingual.md"),
    ("kompaksi", "Meringkas riwayat percakapan jadi ringkasan terstruktur saat mendekati batas jendela konteks; berbeda dari offload yang memindahkan isi ke filesystem.", "concepts/context-engineering.md"),
    ("kontrak hasil", "Apa persis yang mengalir balik dari subagent ke pemanggil — transkrip penuh atau ringkasan tersaring — beserta apa yang sengaja tidak boleh mengalir balik.", "concepts/delegation.md"),
    ("eviction / offload", "Memindahkan input atau hasil tool yang besar ke backend dan menggantinya dengan pointer di konteks aktif. KB memakai \"eviction\"; dokumentasi upstream menyebutnya \"offloading\" — hal yang sama.", "concepts/context-engineering.md"),
    ("policy-as-data", "Kebijakan dinyatakan sebagai data yang bisa dibaca, diaudit, dan diubah tanpa deploy — bukan cabang `if` di dalam engine.", "concepts/policy-as-data.md"),
    ("progressive disclosure", "Skill memuat frontmatter di system prompt, body saat aktivasi, berkas rujukan hanya saat instruksinya menyuruh — tiap lapis punya anggaran sendiri.", "concepts/skill-composition.md"),
    ("PTC", "Programmatic tool calling: tool agent diekspos sebagai fungsi di dalam kode yang dijalankan interpreter, sehingga satu tool call bisa memanggil banyak tool.", "concepts/code-orchestration.md"),
    ("reattach", "Client yang terputus menyambung kembali ke turn yang sedang berjalan tanpa kehilangan event yang sudah lewat.", "concepts/streaming-protocol.md"),
    ("tail stack", "Slot middleware yang dirakit `create_deep_agent` **setelah** `middleware=[...]` milik user; posisinya menentukan apa yang masih bisa disaring dan digerbangi.", "deepagents/middleware.md"),
]

HEAD = """# Glosarium — lookup istilah dan simbol

Dibangkitkan `tools/build_glossary.py`. **Jangan sunting tangan**; ubah
`TERMS` di skrip itu lalu jalankan ulang.

Ini pintu masuk mode ketiga skill ini: bukan alur merancang atau
membangun, melainkan mencari arti satu istilah atau lokasi satu simbol.

```bash
python3 tools/build_glossary.py
```
"""


def load_graph():
    """Simbol code dari graf: label -> {(source_file, source_location)}."""
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    sym = defaultdict(set)
    for n in g["nodes"]:
        # Node modul (label berakhiran .py) selalu menunjuk L1 berkasnya —
        # benar, tapi bukan entri kamus. Yang dicari: kelas dan fungsi.
        if (n.get("file_type") == "code" and n.get("source_file")
                and not n["label"].endswith(".py")):
            sym[n["label"]].add((n["source_file"], n.get("source_location", "")))
    return sym


def kb_files():
    """Berkas KB yang benar-benar kita tulis.

    `upstream/` salinan vendor; `deepagents/graph/` keluaran mesin yang
    mendaftar simbol tanpa membahasnya — mencantumkannya sebagai "dibahas
    KB di" menyesatkan, dan menarik masuk simbol yang tak pernah dijelaskan.
    """
    skip = {"upstream", "graph"}
    return [f for f in sorted(REF.rglob("*.md"))
            if not skip & set(f.parts) and f != OUT]


def check_terms() -> list[str]:
    """Istilah yang berkas kanoniknya hilang atau tak lagi memuatnya."""
    errs = []
    for term, _, canon in TERMS:
        f = REF / canon
        probe = re.split(r" vs | / ", term)[0].lower()
        if not f.exists():
            errs.append(f"{term!r}: berkas kanonik {canon} tidak ada")
        elif probe not in f.read_text(encoding="utf-8").lower():
            errs.append(f"{term!r}: {canon} tidak lagi memuat {probe!r}")
    return errs


def main() -> int:
    if not GRAPH.exists():
        print(f"FAIL: {GRAPH.relative_to(ROOT)} tidak ada")
        return 1

    errs = check_terms()
    if errs:
        for e in errs:
            print("FAIL:", e)
        return 1

    sym = load_graph()
    mentions = defaultdict(set)
    for f in kb_files():
        for m in TOKEN.finditer(f.read_text(encoding="utf-8")):
            if m.group(1) in sym:
                mentions[m.group(1)].add(f.relative_to(REF).as_posix())

    lines = [HEAD, "## Istilah", "",
             "| Istilah | Arti | Dibahas di |", "|---|---|---|"]
    for term, gist, canon in sorted(TERMS, key=lambda x: x[0].lower()):
        lines.append(f"| **{term}** | {gist} | [`{canon}`]({canon}) |")

    lines += [
        "",
        "## Simbol deepagents",
        "",
        f"{len(mentions)} simbol yang disebut KB dan ada di graf AST source. "
        "Kolom lokasi datang dari `deepagents/graph/graph.json`, relatif ke akar "
        "paket `deepagents` di `references/recipes/.venv/`; kesinkronannya "
        "dengan source terpasang dijaga `tools/check_kb.py`.",
        "",
        "| Simbol | Didefinisikan di | Dibahas KB di |",
        "|---|---|---|",
    ]
    for name in sorted(mentions, key=str.lower):
        loc = ", ".join(f"`{a}:{b}`" if b else f"`{a}`"
                        for a, b in sorted(sym[name]))
        refs = ", ".join(f"[`{r}`]({r})" for r in sorted(mentions[name]))
        lines.append(f"| `{name}` | {loc} | {refs} |")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {OUT.relative_to(ROOT)} — {len(TERMS)} istilah, "
          f"{len(mentions)} simbol")
    return 0


if __name__ == "__main__":
    sys.exit(main())
