#!/usr/bin/env python3
"""Ambil ulang snapshot dokumentasi upstream deepagents.

Jalankan: python3 tools/fetch_upstream_docs.py

Mengambil markdown mentah per halaman — bukan ringkasan. Peringkas LLM pernah
mengarang satu kalimat yang tak ada di sumber; sejak itu snapshot ini selalu
diambil verbatim lewat HTTP biasa.
"""
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "references" / "upstream" / "deepagents-docs"
INDEX = "https://docs.langchain.com/oss/python/deepagents/llms.txt"
PAGE = re.compile(r"https://docs\.langchain\.com/oss/python/deepagents/[^)\s]+\.md")

# Dua entri indeks ini me-redirect ke halaman kanonik dan mengembalikan HTML
# lewat URL indeksnya; ambil langsung dari URL kanoniknya.
OVERRIDE = {
    "changelog-py.md": "https://docs.langchain.com/oss/python/releases/changelog.md",
    "changelog-js.md": "https://docs.langchain.com/oss/javascript/releases/changelog.md",
}


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "kb-fetch/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch(url: str) -> tuple[str, str | None]:
    rel = url.rsplit("/deepagents/", 1)[1]
    src = OVERRIDE.get(rel, url)
    try:
        body = get(src)
    except (urllib.error.URLError, TimeoutError) as e:
        return rel, f"gagal ambil: {e}"
    if "<!DOCTYPE" in body[:2000] or "<html" in body[:2000]:
        return rel, f"balasan HTML, bukan markdown (redirect?): {src}"
    path = DEST / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return rel, None


def citing_files(page: str) -> list[str]:
    """Berkas KB yang menyitasi nomor baris di halaman upstream ini.

    Sitasi berbentuk `nama.md` baris N menunjuk ke posisi, bukan ke isi.
    Sekali halaman upstream berubah, nomornya bisa meleset tanpa satu pun
    cek gagal — pernah terjadi, 32 sitasi sekaligus. Jadi setiap halaman
    yang berubah harus menyebut siapa yang perlu ditinjau ulang.
    """
    needle = f"`{Path(page).name}` baris"
    out = []
    for f in sorted((ROOT / "references").rglob("*.md")):
        if f.is_relative_to(DEST):
            continue
        if needle in f.read_text(encoding="utf-8"):
            out.append(f.relative_to(ROOT).as_posix())
    return out


def main() -> int:
    urls = sorted(set(PAGE.findall(get(INDEX))))
    if not urls:
        print("FAIL: indeks tidak memuat satu pun halaman .md")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    before = {f.relative_to(DEST).as_posix(): f.read_text(encoding="utf-8")
              for f in DEST.rglob("*.md") if f.name != "README.md"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, urls))

    errs = [(rel, e) for rel, e in results if e]
    for rel, e in errs:
        print(f"FAIL: {rel}: {e}")
    print(f"\n{len(results) - len(errs)}/{len(results)} halaman tersimpan di "
          f"{DEST.relative_to(ROOT)}")
    if errs:
        return 1

    changed = [rel for rel, _ in results if rel in before
               and before[rel] != (DEST / rel).read_text(encoding="utf-8")]
    if not changed:
        print("Tidak ada halaman yang berubah.")
        return 0

    print(f"\n{len(changed)} halaman berubah:")
    for rel in changed:
        cites = citing_files(rel)
        print(f"  {rel}" + (f"  -> tinjau ulang: {', '.join(cites)}" if cites
                            else "  (tidak disitasi)"))
    print("\nSitasi `baris N` ke halaman di atas mungkin meleset. Verifikasi "
          "sebelum commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
