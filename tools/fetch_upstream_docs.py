#!/usr/bin/env python3
"""Re-fetch the snapshot of the upstream deepagents documentation.

Run: python3 tools/fetch_upstream_docs.py

It fetches each page's raw markdown -- not a summary. An LLM summariser once
invented a sentence that wasn't in the source; ever since, this snapshot is
always taken verbatim over plain HTTP.
"""
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = REPO_ROOT / "references" / "upstream" / "deepagents-docs"
INDEX_URL = "https://docs.langchain.com/oss/python/deepagents/llms.txt"
PAGE_URL_RE = re.compile(r"https://docs\.langchain\.com/oss/python/deepagents/[^)\s]+\.md")

# These two index entries redirect to a canonical page and return HTML
# through their index URL; fetch them from the canonical URL directly.
URL_OVERRIDES = {
    "changelog-py.md": "https://docs.langchain.com/oss/python/releases/changelog.md",
    "changelog-js.md": "https://docs.langchain.com/oss/javascript/releases/changelog.md",
}


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "kb-fetch/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_page(url: str) -> tuple[str, str | None]:
    rel = url.rsplit("/deepagents/", 1)[1]
    src = URL_OVERRIDES.get(rel, url)
    try:
        body = http_get(src)
    except (urllib.error.URLError, TimeoutError) as e:
        return rel, f"fetch failed: {e}"
    if "<!DOCTYPE" in body[:2000] or "<html" in body[:2000]:
        return rel, f"an HTML response, not markdown (a redirect?): {src}"
    path = DEST_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return rel, None


def citing_files(page: str) -> list[str]:
    """The KB files citing line numbers in this upstream page.

    A citation of the form `name.md` line(s) N points at a position, not at
    content. Once an upstream page changes, those numbers can be off with no
    check failing -- it happened once, to 32 citations at a time. So every
    changed page must name who needs reviewing.
    """
    name = Path(page).name
    needles = (f"`{name}` line", f"`{name}` baris")
    out = []
    for f in sorted((REPO_ROOT / "references").rglob("*.md")):
        if f.is_relative_to(DEST_DIR):
            continue
        txt = f.read_text(encoding="utf-8")
        if any(n in txt for n in needles):
            out.append(f.relative_to(REPO_ROOT).as_posix())
    return out


def main() -> int:
    urls = sorted(set(PAGE_URL_RE.findall(http_get(INDEX_URL))))
    if not urls:
        print("FAIL: the index contains no .md page at all")
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    before = {f.relative_to(DEST_DIR).as_posix(): f.read_text(encoding="utf-8")
              for f in DEST_DIR.rglob("*.md") if f.name != "README.md"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch_page, urls))

    errs = [(rel, e) for rel, e in results if e]
    for rel, e in errs:
        print(f"FAIL: {rel}: {e}")
    print(f"\n{len(results) - len(errs)}/{len(results)} pages saved in "
          f"{DEST_DIR.relative_to(REPO_ROOT)}")
    if errs:
        return 1

    changed = [rel for rel, _ in results if rel in before
               and before[rel] != (DEST_DIR / rel).read_text(encoding="utf-8")]
    if not changed:
        print("No page changed.")
        return 0

    print(f"\n{len(changed)} pages changed:")
    for rel in changed:
        cites = citing_files(rel)
        print(f"  {rel}" + (f"  -> review: {', '.join(cites)}" if cites
                            else "  (not cited)"))
    print("\nLine-number citations into the pages above may be off. Verify "
          "before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
