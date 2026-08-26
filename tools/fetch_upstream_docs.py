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

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "references" / "upstream" / "deepagents-docs"
INDEX = "https://docs.langchain.com/oss/python/deepagents/llms.txt"
PAGE = re.compile(r"https://docs\.langchain\.com/oss/python/deepagents/[^)\s]+\.md")

# These two index entries redirect to a canonical page and return HTML
# through their index URL; fetch them from the canonical URL directly.
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
        return rel, f"fetch failed: {e}"
    if "<!DOCTYPE" in body[:2000] or "<html" in body[:2000]:
        return rel, f"an HTML response, not markdown (a redirect?): {src}"
    path = DEST / rel
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
    for f in sorted((ROOT / "references").rglob("*.md")):
        if f.is_relative_to(DEST):
            continue
        txt = f.read_text(encoding="utf-8")
        if any(n in txt for n in needles):
            out.append(f.relative_to(ROOT).as_posix())
    return out


def main() -> int:
    urls = sorted(set(PAGE.findall(get(INDEX))))
    if not urls:
        print("FAIL: the index contains no .md page at all")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    before = {f.relative_to(DEST).as_posix(): f.read_text(encoding="utf-8")
              for f in DEST.rglob("*.md") if f.name != "README.md"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, urls))

    errs = [(rel, e) for rel, e in results if e]
    for rel, e in errs:
        print(f"FAIL: {rel}: {e}")
    print(f"\n{len(results) - len(errs)}/{len(results)} pages saved in "
          f"{DEST.relative_to(ROOT)}")
    if errs:
        return 1

    changed = [rel for rel, _ in results if rel in before
               and before[rel] != (DEST / rel).read_text(encoding="utf-8")]
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
