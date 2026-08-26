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


def main() -> int:
    urls = sorted(set(PAGE.findall(get(INDEX))))
    if not urls:
        print("FAIL: indeks tidak memuat satu pun halaman .md")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, urls))

    errs = [(rel, e) for rel, e in results if e]
    for rel, e in errs:
        print(f"FAIL: {rel}: {e}")
    print(f"\n{len(results) - len(errs)}/{len(results)} halaman tersimpan di "
          f"{DEST.relative_to(ROOT)}")
    if not errs:
        print("Berikutnya: git diff --stat references/upstream/ — halaman yang "
              "berubah menandai klaim [docs] yang perlu ditinjau.")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
