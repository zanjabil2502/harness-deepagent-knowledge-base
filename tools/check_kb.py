#!/usr/bin/env python3
"""Validator struktur KB. Jalankan: python3 tools/check_kb.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "references"

FRAMES = {
    "archetypes": [
        "## Definisi", "## Posisi di 6 sumbu", "## Konsekuensi harness",
        "## Sistem contoh", "## Jebakan khas",
        "## Bangun ini pakai deepagents", "## Sumber",
    ],
    "concepts": [
        "## Masalah", "## Pola", "## Trade-off", "## Di deepagents", "## Sumber",
    ],
    "systems": [
        "## Arketipe", "## 1. Loop shape", "## 2. Context", "## 3. Tool surface",
        "## 4. Delegation", "## 5. State & resume", "## 6. Safety gate",
        "## 7. Capability routing & policy", "## Sumber",
    ],
}
EXEMPT = {"README.md", "_template.md", "INDEX.md"}
LABEL = re.compile(r"\[(code|docs|inferred|ours)\]")
LINK = re.compile(r"\]\((?!https?:|mailto:)([^)#]+)")
SKILL_MAX_LINES = 150


def check_frames(errs):
    for group, heads in FRAMES.items():
        folder = REF / group
        if not folder.is_dir():
            errs.append(f"references/{group}/: folder belum ada")
            continue
        for f in sorted(folder.rglob("*.md")):
            if f.name in EXEMPT:
                continue
            txt = f.read_text(encoding="utf-8")
            rel = f.relative_to(ROOT)
            for h in heads:
                if h not in txt:
                    errs.append(f"{rel}: hilang section '{h}'")
            if not LABEL.search(txt):
                errs.append(f"{rel}: tidak ada label sumber [code]/[docs]/[inferred]")


def check_links(errs):
    files = [ROOT / "SKILL.md", ROOT / "README.md"]
    if REF.is_dir():
        files += sorted(REF.rglob("*.md"))
    for f in files:
        if not f.exists() or ".git" in f.parts:
            continue
        for m in LINK.finditer(f.read_text(encoding="utf-8")):
            target = (f.parent / m.group(1).strip()).resolve()
            if not target.exists():
                errs.append(f"{f.relative_to(ROOT)}: link mati -> {m.group(1)}")


def check_skill_size(errs):
    skill = ROOT / "SKILL.md"
    if not skill.exists():
        errs.append("SKILL.md: belum ada")
        return
    n = len(skill.read_text(encoding="utf-8").splitlines())
    if n > SKILL_MAX_LINES:
        errs.append(f"SKILL.md: {n} baris, maksimum {SKILL_MAX_LINES}")


def main():
    errs = []
    check_frames(errs)
    check_links(errs)
    check_skill_size(errs)
    for e in errs:
        print("FAIL:", e)
    print(f"\n{len(errs)} masalah" if errs else "\nOK: semua cek lulus")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
