#!/usr/bin/env python3
"""Validator struktur KB. Jalankan: python3 tools/check_kb.py"""
import hashlib
import json
import subprocess
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "references"

FRAMES = {
    "archetypes": [
        "## Definition", "## Position on the 6 axes", "## Harness consequences",
        "## Example systems", "## Common pitfalls",
        "## Building this with deepagents", "## Sources",
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
# references/deepagents/graph/ adalah indeks simbol→file:line dari source
# deepagents. Nilainya
# bergantung sepenuhnya pada kesinkronan dengan source yang terpasang: begitu
# paketnya berubah, sitasi `file.py:NNN` di seluruh KB bisa meleset tanpa satu
# pun cek gagal. manifest.json menyimpan md5 tiap berkas saat graf dibangun,
# jadi drift-nya bisa dibuktikan, bukan diasumsikan.
MANIFEST = REF / "deepagents" / "graph" / "manifest.json"
DA_SRC = next(
    iter(sorted(ROOT.glob("references/recipes/.venv/lib/python*/site-packages/deepagents"))),
    None,
)
GLOSSARY = REF / "GLOSSARY.md"
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


def tracked_files():
    """Berkas yang benar-benar ikut saat repo di-clone.

    check_links memeriksa filesystem, jadi tautan ke berkas yang sengaja
    tidak di-track tetap terlihat hidup di mesin penulisnya dan mati bagi
    semua orang lain — kegagalan yang tak terlihat sampai ada yang clone.
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return set(out.stdout.split("\0")) - {""}


def check_links(errs):
    tracked = tracked_files()
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
            elif tracked is not None and target.is_file():
                try:
                    rel = target.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                if rel not in tracked:
                    errs.append(
                        f"{f.relative_to(ROOT)}: link ke berkas tak ter-track "
                        f"-> {m.group(1)} (hidup di sini, mati bagi yang clone)"
                    )


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


def check_graph_sync(errs):
    """Graf AST harus cocok dengan source deepagents yang terpasang."""
    if not MANIFEST.exists():
        errs.append("references/deepagents/graph/manifest.json: tidak ada")
        return
    if DA_SRC is None or not DA_SRC.is_dir():
        print("LEWAT: venv references/recipes/ belum ada, sinkronisasi graf tidak dicek")
        return
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rel, meta in sorted(manifest.items()):
        f = DA_SRC / rel
        if not f.exists():
            errs.append(f"graf: {rel} ada di graf tapi tidak di source terpasang")
        elif hashlib.md5(f.read_bytes()).hexdigest() != meta.get("ast_hash"):
            errs.append(
                f"graf: {rel} berubah sejak graf dibangun — "
                "bangun ulang graf dan tinjau sitasi baris yang menunjuk berkas ini"
            )
    for f in sorted(DA_SRC.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(DA_SRC).as_posix()
        if rel not in manifest:
            errs.append(f"graf: {rel} ada di source tapi belum masuk graf")


def check_glossary(errs):
    """GLOSSARY.md dibangkitkan; ia harus identik dengan hasil bangun ulang."""
    if not GLOSSARY.exists():
        errs.append("references/GLOSSARY.md: belum dibangkitkan "
                    "(python3 tools/build_glossary.py)")
        return
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_glossary
    except ImportError:
        errs.append("tools/build_glossary.py: tidak bisa diimpor")
        return
    for e in build_glossary.check_terms():
        errs.append(f"GLOSSARY: {e}")
    before = GLOSSARY.read_text(encoding="utf-8")
    if build_glossary.main() != 0:
        errs.append("GLOSSARY: build_glossary gagal")
        return
    if GLOSSARY.read_text(encoding="utf-8") != before:
        errs.append("references/GLOSSARY.md: basi — hasil bangun ulang berbeda, "
                    "commit ulang berkasnya")


def main():
    errs = []
    check_frames(errs)
    check_links(errs)
    check_skill_size(errs)
    check_ours_roster(errs)
    check_skill_assets(errs)
    check_graph_sync(errs)
    check_glossary(errs)
    for e in errs:
        print("FAIL:", e)
    print(f"\n{len(errs)} masalah" if errs else "\nOK: semua cek lulus")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
