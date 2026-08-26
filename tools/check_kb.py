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
# Aset skill yang di-scaffold ke project. Batasnya bukan selera kami:
# spesifikasi Agent Skills menuntut `name` sama dengan nama direktori dan
# menganjurkan SKILL.md di bawah 500 baris; deepagents melewati berkas di
# atas 10 MB saat discovery tanpa error. Ketiganya gagal diam-diam kalau
# dilanggar, jadi dicek di sini. Lihat references/deepagents/best-practices.md §5.
SKILL_ASSETS = REF / "scaffolds" / "skills"
ASSET_MAX_LINES = 500
ASSET_MAX_BYTES = 10 * 1024 * 1024
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

OURS = re.compile(r"\[ours\]")
# Baris roster [ours] di conformance.md: | n | `path:l1,l2,...` | ... |
ROSTER_ROW = re.compile(r"^\|[^|]*\|\s*`([\w/\-.]+\.md):([\d,\s]+)`")
ROSTER = REF / "deepagents" / "conformance.md"
# references/deepagents/ menampung pointer (per-archetype.md) dan meta (conformance.md)
# tentang label itu sendiri; roster hanya mendaftar klaim substantif di luar folder ini.
ROSTER_EXEMPT_DIR = "deepagents"
# references/upstream/ = salinan verbatim dokumentasi vendor. Bukan tulisan kita,
# jadi tidak tunduk pada frame section, label sumber, maupun roster [ours];
# link internalnya juga memakai path absolut situs vendor, bukan path repo.
UPSTREAM_DIR = "upstream"


def authored(f):
    """Berkas KB yang kita tulis sendiri (bukan salinan upstream)."""
    return f.relative_to(REF).parts[0] != UPSTREAM_DIR


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
        files += [f for f in sorted(REF.rglob("*.md")) if authored(f)]
    for f in files:
        if not f.exists() or ".venv" in f.parts:
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


def check_ours_roster(errs):
    """Tiap `[ours]` wajib terdaftar di roster conformance.md, tempat alternatif
    vanilla dan alasan menyimpang dicatat. Dicek dua arah: lokasi yang didaftar
    roster harus benar-benar memuat `[ours]`, dan tiap `[ours]` harus terdaftar."""
    if not ROSTER.exists():
        errs.append(f"{ROSTER.relative_to(ROOT)}: roster [ours] tidak ada")
        return

    rostered = set()
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        m = ROSTER_ROW.match(line)
        if not m:
            continue
        for n in m.group(2).split(","):
            n = n.strip()
            if n.isdigit():
                rostered.add((m.group(1), int(n)))

    actual = set()
    for f in sorted(REF.rglob("*.md")):
        if not authored(f):
            continue
        rel = f.relative_to(REF).as_posix()
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if OURS.search(line):
                actual.add((rel, i))

    for rel, n in sorted(rostered - actual):
        errs.append(f"roster [ours] menunjuk {rel}:{n} yang tidak memuat [ours] (basi?)")
    for rel, n in sorted(actual - rostered):
        if rel.split("/")[0] == ROSTER_EXEMPT_DIR:
            continue
        errs.append(f"{rel}:{n}: [ours] tidak terdaftar di roster conformance.md")


def check_skill_assets(errs):
    """Aset skill wajib patuh spesifikasi Agent Skills — pelanggarannya senyap."""
    if not SKILL_ASSETS.is_dir():
        return
    for d in sorted(p for p in SKILL_ASSETS.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        rel = f.relative_to(ROOT)
        if not f.exists():
            errs.append(f"{d.relative_to(ROOT)}/: tidak ada SKILL.md")
            continue
        txt = f.read_text(encoding="utf-8")
        m = FRONTMATTER.match(txt)
        if not m:
            errs.append(f"{rel}: tidak ada frontmatter YAML")
            continue
        fm = {}
        for ln in m.group(1).splitlines():
            if ln.startswith((" ", "\t")):
                continue  # lanjutan nilai multi-baris, bukan kunci baru
            k, sep, v = ln.partition(":")
            if sep:
                fm[k.strip()] = v.strip()
        if fm.get("name") != d.name:
            errs.append(f"{rel}: name={fm.get('name')!r} tidak sama dengan direktori {d.name!r}")
        if not fm.get("description"):
            errs.append(f"{rel}: frontmatter tanpa description")
        n = len(txt.splitlines())
        if n > ASSET_MAX_LINES:
            errs.append(f"{rel}: {n} baris, maksimum {ASSET_MAX_LINES}")
        if len(txt.encode()) > ASSET_MAX_BYTES:
            errs.append(f"{rel}: melebihi 10 MB, akan dilewati saat discovery")


def main():
    errs = []
    check_frames(errs)
    check_links(errs)
    check_skill_size(errs)
    check_ours_roster(errs)
    check_skill_assets(errs)
    for e in errs:
        print("FAIL:", e)
    print(f"\n{len(errs)} masalah" if errs else "\nOK: semua cek lulus")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
