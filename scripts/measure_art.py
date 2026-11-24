#!/usr/bin/env python3
"""measure-art: count creative and CAD files locally. Counts only, never content.

Usage:
  measure_art.py <root> [<root> ...] --out DIR [--label NAME] [--tag K:V] [--cutoff 2025-01-01] [--force]

Walks the given folders (disks, shares, synced folders) and writes:
  measure.json  schema october.measure/v1, kind "art"
  report.md     human-readable summary

What it counts: files and bytes by application (Figma, Blender, Unity, FBX,
Photoshop, After Effects, Illustrator, Canva exports, SketchUp, AutoCAD, other
CAD, Maya, 3ds Max, Substance, ...), native working files versus exports,
distinct works (versions of one file grouped), engine projects (Unity, Unreal,
Godot), sizes, dates (file times, plus internal dates and versions read from
headers where the format carries them), duplicates and cloud-only placeholders.

What it never writes: file or folder names, paths, layer names, text, or
image content. Only a few header bytes are read to identify formats and
versions. Progress is checkpointed per top-level folder in <out>/.state so an
interrupted run resumes.

Python 3.9+ standard library only. No network calls.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import struct
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

TOOL = "measure-art"
VERSION = "0.2.0"
SCHEMA = "october.measure/v1"
SKETCH_K = 256

# extension -> (application, role). Roles: native (editable working file), export (flattened or
# interchange output), engine (engine scene/asset), texture (image inside an engine project),
# backup (application autosave/backup).
APPS = {
    "Figma": {".fig": "native", ".jam": "native"},
    "Sketch": {".sketch": "native"},
    "Adobe XD": {".xd": "native"},
    "Photoshop": {".psd": "native", ".psb": "native"},
    "Illustrator": {".ai": "native", ".ait": "native"},
    "InDesign": {".indd": "native", ".idml": "native"},
    "After Effects": {".aep": "native", ".aet": "native", ".aepx": "native"},
    "Premiere Pro": {".prproj": "native"},
    "Blender": {".blend": "native", ".blend1": "backup", ".blend2": "backup"},
    "Maya": {".ma": "native", ".mb": "native"},
    "3ds Max": {".max": "native"},
    "Cinema 4D": {".c4d": "native"},
    "Houdini": {".hip": "native", ".hipnc": "native", ".hiplc": "native"},
    "ZBrush": {".ztl": "native", ".zpr": "native"},
    "Substance": {".spp": "native", ".sbs": "native", ".sbsar": "export"},
    "Krita / Procreate / Affinity / Clip Studio": {".kra": "native", ".procreate": "native", ".afdesign": "native",
                                                   ".afphoto": "native", ".clip": "native"},
    "SketchUp": {".skp": "native", ".skb": "backup"},
    "AutoCAD": {".dwg": "native", ".dxf": "export", ".dwl": "backup", ".bak": None},
    "SolidWorks": {".sldprt": "native", ".sldasm": "native", ".slddrw": "native"},
    "Fusion / Inventor": {".f3d": "native", ".ipt": "native", ".iam": "native", ".idw": "native"},
    "CATIA / Creo / NX": {".catpart": "native", ".catproduct": "native", ".prt": "native", ".asm": None},
    "Rhino": {".3dm": "native"},
    "FreeCAD": {".fcstd": "native"},
    "CAD interchange": {".step": "export", ".stp": "export", ".iges": "export", ".igs": "export", ".x_t": "export",
                        ".sat": "export", ".3mf": "export"},
    "FBX": {".fbx": "export"},
    "3D interchange": {".obj": "export", ".gltf": "export", ".glb": "export", ".stl": "export", ".dae": "export",
                       ".usd": "export", ".usda": "export", ".usdc": "export", ".usdz": "export", ".abc": "export",
                       ".ply": "export"},
    "Unity": {".unity": "engine", ".prefab": "engine", ".mat": "engine", ".anim": "engine", ".controller": "engine",
              ".asset": "engine", ".unitypackage": "export", ".shadergraph": "engine", ".vfx": "engine"},
    "Unreal": {".uasset": "engine", ".umap": "engine", ".uproject": "engine"},
    "Godot": {".tscn": "engine", ".tres": "engine", ".scn": "engine"},
    "Image export": {".png": "export", ".jpg": "export", ".jpeg": "export", ".webp": "export", ".gif": "export",
                     ".tga": "export", ".tif": "export", ".tiff": "export", ".exr": "export", ".hdr": "export",
                     ".bmp": "export", ".svg": "export", ".dds": "export", ".heic": "export"},
    "Video export": {".mp4": "export", ".mov": "export", ".webm": "export", ".avi": "export", ".mkv": "export",
                     ".m4v": "export"},
    "PDF export": {".pdf": "export"},
    "Audio": {".wav": "export", ".mp3": "export", ".ogg": "export", ".flac": "export", ".aif": "export",
              ".aiff": "export"},
    "Font": {".ttf": "export", ".otf": "export"},
}
EXT = {}
for app, exts in APPS.items():
    for ext, role in exts.items():
        if role:
            EXT[ext] = (app, role)
CAD_APPS = {"SketchUp", "AutoCAD", "SolidWorks", "Fusion / Inventor", "CATIA / Creo / NX", "Rhino", "FreeCAD", "CAD interchange"}
SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", "Library", "Temp", "Logs", "obj", "Intermediate",
             "DerivedDataCache", "Saved", ".godot", ".import", "Adobe After Effects Disk Cache", "Media Cache Files",
             "Media Cache", "Peak Files", "Auto-Save", "Adobe Premiere Pro Auto-Save"}
XMP_EXTS = {".psd", ".psb", ".ai", ".aep", ".indd", ".prproj", ".tif", ".tiff", ".jpg", ".jpeg", ".pdf"}
XMP_DATE = re.compile(rb"xmp:CreateDate(?:>|=\")(\d{4})-(\d{2})")
XMP_CREATOR = re.compile(rb"<dc:creator>\s*<rdf:Seq>\s*<rdf:li[^>]*>([^<]{1,200})</rdf:li>")
XMP_TOOL = re.compile(rb"xmp:CreatorTool(?:>|=\")(Adobe (?:Photoshop|Illustrator|After Effects|InDesign|Premiere Pro)(?: CC)?(?: \d{2,4}(?:\.\d)?)?)")
DESIGN_ROLES = {"native", "export"}
NOT_DESIGN_APPS = {"Audio", "Font"}
RENDER_APPS = {"Image export", "Video export", "Canva export", "PDF export"}


class Opts:
    simple = False


OPTS = Opts()
CANVA_NAME = re.compile(r"^(untitled design|copy of untitled design)( \(\d+\))?\.", re.I)
VERSION_SUFFIX = re.compile(r"([ _.-]*(v|ver|version|rev|r)?[ _.-]*\d{1,3}|[ _.-]*(final|old|new|copy|backup|wip|draft|edit|export|latest|\(\d+\)))+$", re.I)
DATE_IN_NAME = re.compile(r"(19|20)\d{2}[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")
DWG_VERSIONS = {"AC1009": "R12", "AC1012": "R13", "AC1014": "R14", "AC1015": "2000", "AC1018": "2004",
                "AC1021": "2007", "AC1024": "2010", "AC1027": "2013", "AC1032": "2018"}


def log(msg: str) -> None:
    print(f"[{TOOL}] {msg}", file=sys.stderr, flush=True)


def h(value, n: int = 16) -> str:
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()[:n]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def work_key(name: str) -> str:
    """Group versions of one piece of work: hero_v3_final.psd and hero.psd -> 'hero'."""
    stem = name.rsplit(".", 1)[0].lower()
    stem = DATE_IN_NAME.sub("", stem)
    prev = None
    while prev != stem:
        prev = stem
        stem = VERSION_SUFFIX.sub("", stem).strip(" _.-")
    return stem or name.lower()


def read_head(p: Path, n: int = 4096, tail: int = 0) -> bytes:
    try:
        with p.open("rb") as f:
            data = f.read(n)
            if tail:
                try:
                    f.seek(-tail, 2)
                    data += f.read(tail)
                except OSError:
                    pass
            return data
    except OSError:
        return b""


def probe(p: Path, ext: str, size: int) -> dict:
    """Header-only probes. Returns small vocabulary facts: version strings, internal dates, Canva origin."""
    out = {}
    if ext == ".blend":
        head = read_head(p, 12)
        if head.startswith(b"BLENDER") and len(head) >= 12:
            v = head[9:12].decode("ascii", "replace")
            out["version"] = f"Blender {v[0]}.{v[1:]}" if v.isdigit() else None
        elif head[:2] == b"\x1f\x8b" or head[:4] == b"\x28\xb5\x2f\xfd":
            out["version"] = "Blender (compressed)"
    elif ext == ".fbx":
        head = read_head(p, 32)
        if head.startswith(b"Kaydara FBX Binary"):
            out["version"] = f"FBX {struct.unpack('<I', head[23:27])[0] / 1000:.1f} binary"
        else:
            m = re.search(rb"FBX (\d)\.(\d)", head)
            out["version"] = f"FBX {m.group(1).decode()}.{m.group(2).decode()} ascii" if m else "FBX ascii"
    elif ext == ".dwg":
        code = read_head(p, 6).decode("ascii", "replace")
        out["version"] = f"DWG {DWG_VERSIONS.get(code, 'other')}"
    elif ext in (".step", ".stp"):
        head = read_head(p, 4096).decode("latin-1")
        m = re.search(r"FILE_NAME\s*\(\s*'[^']*'\s*,\s*'(\d{4}-\d{2}-\d{2})", head)
        if m:
            out["internal_date"] = m.group(1)
    elif ext in (".psd", ".psb"):
        head = read_head(p, 26)
        if head[:4] == b"8BPS" and len(head) >= 26:
            hgt, wid = struct.unpack(">II", head[14:22])
            out["megapixels"] = round(wid * hgt / 1e6, 1)
    elif ext == ".skp":
        head = read_head(p, 200)
        m = re.search(rb"\{\x00(\d)\x00(\d)?\x00?\.\x00", head)
        out["version"] = "SketchUp" if not m else "SketchUp " + (m.group(1) + (m.group(2) or b"")).decode()
    elif ext == ".pdf":
        data = read_head(p, 65536, tail=65536 if size > 131072 else 0)
        if b"Canva" in data:
            out["canva"] = True
    elif ext == ".png":
        data = read_head(p, 4096)
        if b"Canva" in data:
            out["canva"] = True
    if ext in XMP_EXTS:  # Adobe and many exporters embed an XMP packet near the start or the end
        data = read_head(p, 262144, tail=262144 if size > 524288 else 0)
        m = XMP_DATE.search(data)
        if m:
            out["internal_date"] = f"{m.group(1).decode()}-{m.group(2).decode()}-01"
        c = XMP_CREATOR.search(data)
        if c:
            out["creator"] = h(c.group(1).decode("utf-8", "replace").strip().lower(), 12)
        tl = XMP_TOOL.search(data)
        if tl:
            out["tool"] = tl.group(1).decode("ascii", "replace")
    return out


def list_zip(p: Path, u: dict) -> None:
    """Count creative files inside a zip from its member index. Nothing is extracted."""
    try:
        with zipfile.ZipFile(p) as z:
            u["zip"]["zips"] += 1
            for info in z.infolist():
                if info.is_dir():
                    continue
                u["zip"]["members"] += 1
                mext = "." + info.filename.rsplit(".", 1)[-1].lower() if "." in info.filename else ""
                if mext in EXT:
                    u["zip"]["creative_members"] += 1
                    u["zip"]["creative_uncompressed_bytes"] += info.file_size
                    u["zip_apps"][EXT[mext][0]] += 1
    except (zipfile.BadZipFile, OSError, RuntimeError):
        u["zip"]["unreadable_zips"] += 1


def quick_fp(p: Path, size: int) -> str | None:
    if size == 0:
        return None
    data = read_head(p, 65536, tail=65536 if size > 131072 else 0)
    return hashlib.sha256(str(size).encode() + data).hexdigest()[:24] if data else None


# --------------------------------------------------------------------------
# accumulate one unit (a top-level folder)
# --------------------------------------------------------------------------


def new_unit() -> dict:
    return {"apps": {}, "years": Counter(), "first": None, "last": None, "pre": 0, "dated": 0, "fps": [], "dups": 0,
            "dup_bytes": 0, "placeholders": 0, "unreadable": 0, "works": {}, "engine_projects": [], "versions": Counter(),
            "internal_years": Counter(), "canva": 0, "folders_with_native": set(), "exports_with_native": 0,
            "bytes_total": 0, "files_total": 0, "other_files": 0, "other_bytes": 0, "megapixels": [],
            "designs": set(), "designs_native": set(), "creator_months": {}, "creators": set(), "tools": Counter(),
            "zip": Counter(), "zip_apps": Counter()}


def scan_unit(top: Path, cutoff: dt.datetime, shallow: bool = False) -> dict:
    u = new_unit()
    seen = set()
    natives_by_folder = defaultdict(set)   # folder -> work keys of native files
    exports_by_folder = defaultdict(list)  # folder -> work keys of exports
    engine_root = None
    if top.is_file():
        walker = [(str(top.parent), [], [top.name])]
    elif shallow:  # only the loose files directly inside a root
        walker = [(str(top), [], sorted(f for f in os.listdir(top) if (top / f).is_file()))]
    else:
        walker = os.walk(top)
    for root, dirs, files in walker:
        rp = Path(root)
        if isinstance(dirs, list) and dirs:
            names = set(dirs) | set(files)
            if {"Assets", "ProjectSettings"} <= names:
                pv = rp / "ProjectSettings" / "ProjectVersion.txt"
                ver = None
                if pv.is_file():
                    m = re.search(r"m_EditorVersion:\s*(\d+\.\d+)", pv.read_text("utf-8", "replace"))
                    ver = m.group(1) if m else None
                u["engine_projects"].append({"engine": "Unity", "version": ver})
                engine_root = rp
            elif any(f.endswith(".uproject") for f in files):
                u["engine_projects"].append({"engine": "Unreal", "version": None})
            elif "project.godot" in files:
                u["engine_projects"].append({"engine": "Godot", "version": None})
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.startswith(".") or name.endswith(".meta"):
                continue
            p = rp / name
            try:
                st = p.lstat()
            except OSError:
                u["unreadable"] += 1
                continue
            if not p.is_file():
                continue
            size = st.st_size
            u["files_total"] += 1
            u["bytes_total"] += size
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            app_role = EXT.get(ext)
            if app_role is None:
                u["other_files"] += 1
                u["other_bytes"] += size
                if ext == ".zip" and not OPTS.simple and getattr(st, "st_blocks", 1):
                    list_zip(p, u)
                continue
            app, role = app_role
            in_engine = engine_root is not None and (engine_root == rp or engine_root in rp.parents)
            if in_engine and app == "Image export":
                role = "texture"
            facts = probe(p, ext, size) if size and getattr(st, "st_blocks", 1) and not OPTS.simple else {}
            if facts.get("canva") or (app in ("Image export", "PDF export", "Video export") and CANVA_NAME.match(name)):
                app, role = "Canva export", "export"
                u["canva"] += 1
            a = u["apps"].setdefault(app, {"files": 0, "bytes": 0, "roles": Counter()})
            a["files"] += 1
            a["bytes"] += size
            a["roles"][role] += 1
            if facts.get("version"):
                u["versions"][facts["version"]] += 1
            if facts.get("internal_date"):
                u["internal_years"][facts["internal_date"][:4]] += 1
                if facts.get("creator"):
                    u["creator_months"].setdefault(facts["internal_date"][:7], set()).add(facts["creator"])
            if facts.get("creator"):
                u["creators"].add(facts["creator"])
            if facts.get("tool"):
                u["tools"][facts["tool"]] += 1
            if facts.get("megapixels"):
                u["megapixels"].append(facts["megapixels"])
            when = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc)
            if 1990 <= when.year <= 2100:
                u["dated"] += 1
                u["years"][str(when.year)] += 1
                iso = when.strftime("%Y-%m-%d")
                u["first"] = iso if u["first"] is None or iso < u["first"] else u["first"]
                u["last"] = iso if u["last"] is None or iso > u["last"] else u["last"]
                u["pre"] += when < cutoff
            folder = h(str(rp), 12)
            wk = work_key(name)
            if role in DESIGN_ROLES and app not in NOT_DESIGN_APPS:
                dkey = h(f"{folder}|{wk}", 12)
                u["designs"].add(dkey)
                if role == "native":
                    u["designs_native"].add(dkey)
            if size > 0 and getattr(st, "st_blocks", 1) == 0:
                u["placeholders"] += 1
                continue
            if OPTS.simple:
                continue  # listing only
            fp = quick_fp(p, size)
            if fp:
                if fp in seen:
                    u["dups"] += 1
                    u["dup_bytes"] += size
                seen.add(fp)
                u["fps"].append(fp)
            if role == "native":
                key = h(f"{app}|{folder}|{wk}", 12)
                u["works"].setdefault(app, set()).add(key)
                natives_by_folder[folder].add(wk)
                u["folders_with_native"].add(folder)
            elif role == "export" and app not in ("Audio", "Font"):
                exports_by_folder[folder].append(wk)
    for folder, keys in exports_by_folder.items():
        nat = natives_by_folder.get(folder, set())
        u["exports_with_native"] += sum(1 for k in keys if k in nat)
    # make JSON-friendly; keep only a bottom-k sketch of fingerprints
    u["fps_count"] = len(set(u["fps"]))
    u["fps"] = sorted({h(f) for f in u["fps"]})[:SKETCH_K]
    u["works"] = {k: sorted(v) for k, v in u["works"].items()}
    u["folders_with_native"] = len(u["folders_with_native"])
    for k in ("designs", "designs_native", "creators"):
        u[k] = sorted(u[k])
    u["creator_months"] = {k: sorted(v) for k, v in u["creator_months"].items()}
    for k in ("tools", "zip", "zip_apps"):
        u[k] = dict(u[k])
    for a in u["apps"].values():
        a["roles"] = dict(a["roles"])
    for k in ("years", "versions", "internal_years"):
        u[k] = dict(u[k])
    return u


def merge(units: list) -> dict:
    m = new_unit()
    m["years"], m["versions"], m["internal_years"] = Counter(), Counter(), Counter()
    designs, designs_native, creators, creator_months = set(), set(), set(), defaultdict(set)
    works = defaultdict(set)
    fps = set()
    m["folders_with_native"] = 0
    fps_count = 0
    for u in units:
        for app, a in u["apps"].items():
            t = m["apps"].setdefault(app, {"files": 0, "bytes": 0, "roles": Counter()})
            t["files"] += a["files"]; t["bytes"] += a["bytes"]; t["roles"].update(a["roles"])
        m["years"].update(u["years"]); m["versions"].update(u["versions"]); m["internal_years"].update(u["internal_years"])
        for k in ("pre", "dated", "dups", "dup_bytes", "placeholders", "unreadable", "canva", "exports_with_native",
                  "bytes_total", "files_total", "other_files", "other_bytes", "folders_with_native"):
            m[k] += u[k]
        for k, cmp in (("first", min), ("last", max)):
            if u[k]:
                m[k] = u[k] if m[k] is None else cmp(m[k], u[k])
        for app, keys in u["works"].items():
            works[app].update(keys)
        fps.update(u["fps"])
        fps_count += u["fps_count"]
        designs.update(u.get("designs", [])); designs_native.update(u.get("designs_native", []))
        creators.update(u.get("creators", []))
        for k, v in u.get("creator_months", {}).items():
            creator_months[k].update(v)
        m["tools"].update(u.get("tools", {})); m["zip"].update(u.get("zip", {})); m["zip_apps"].update(u.get("zip_apps", {}))
        m["engine_projects"] += u["engine_projects"]
        m["megapixels"] += u["megapixels"]
    m["works"] = works
    m["designs"], m["designs_native"], m["creators"], m["creator_months"] = designs, designs_native, creators, creator_months
    m["fps"] = sorted(fps)[:SKETCH_K]
    m["fps_count"] = fps_count
    return m


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------


def build_doc(m: dict, label: str, tags: list, cutoff: str, roots: int, mode: str = "full") -> dict:
    apps = {}
    for app, a in sorted(m["apps"].items(), key=lambda kv: -kv[1]["bytes"]):
        apps[app] = {"files": a["files"], "bytes": a["bytes"], "native": a["roles"].get("native", 0),
                     "export": a["roles"].get("export", 0), "engine": a["roles"].get("engine", 0),
                     "texture": a["roles"].get("texture", 0), "backup": a["roles"].get("backup", 0),
                     "distinct_works": len(m["works"].get(app, ()))}
    native = sum(a["native"] for a in apps.values())
    exports = sum(a["export"] for a in apps.values())
    works = sum(a["distinct_works"] for a in apps.values())
    engine = Counter(f"{p['engine']} {p['version'] or ''}".strip() for p in m["engine_projects"])
    mp = sorted(m["megapixels"])
    creative_bytes = sum(a["bytes"] for a in apps.values()) or 0
    designs = len(m["designs"])
    peak_month, peak = (max(((k, len(v)) for k, v in m["creator_months"].items()), key=lambda kv: (kv[1], kv[0]))
                        if m["creator_months"] else (None, None))
    return {
        "schema": SCHEMA, "kind": "art", "tool": TOOL, "tool_version": VERSION, "mode": mode,
        "measured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label, "tags": tags, "cutoff": cutoff,
        "span": {"first": m["first"], "last": m["last"]},
        "totals": {
            "roots": roots, "files_scanned": m["files_total"], "bytes_scanned": m["bytes_total"],
            "creative_files": sum(a["files"] for a in apps.values()),
            "creative_bytes": sum(a["bytes"] for a in apps.values()),
            "native_files": native, "export_files": exports,
            "engine_asset_files": sum(a["engine"] for a in apps.values()),
            "texture_files": sum(a["texture"] for a in apps.values()),
            "backup_files": sum(a["backup"] for a in apps.values()),
            "distinct_works": works, "native_files_per_work": round(native / works, 2) if works else None,
            "folders_with_native_files": m["folders_with_native"],
            "exports_with_native_source_nearby": m["exports_with_native"],
            "cad_files": sum(a["files"] for k, a in apps.items() if k in CAD_APPS),
            "canva_exports": m["canva"],
            "engine_projects": len(m["engine_projects"]),
            "duplicate_files": m["dups"], "duplicate_bytes": m["dup_bytes"],
            "placeholders_not_downloaded": m["placeholders"], "unreadable": m["unreadable"],
            "other_files": m["other_files"], "other_bytes": m["other_bytes"],
            "distinct_designs": designs,
            "designs_with_native_share": round(len(m["designs_native"]) / designs, 3) if designs else None,
            "cad_bytes_share": round(sum(a["bytes"] for k, a in apps.items() if k in CAD_APPS) / creative_bytes, 3) if creative_bytes else None,
            "render_and_image_bytes_share": round(sum(a["bytes"] for k, a in apps.items() if k in RENDER_APPS) / creative_bytes, 3) if creative_bytes else None,
        },
        "zip_contents": dict(m["zip"], by_application=dict(m["zip_apps"].most_common())) if m["zip"] else None,
        "authors": {"distinct_creators_in_metadata": len(m["creators"]) if not OPTS.simple else None,
                    "peak_creators_in_a_month": peak, "peak_month": peak_month,
                    "note": "from XMP metadata in Adobe and similar files; names are hashed, never stored"},
        "creator_tools": dict(m["tools"].most_common(20)),
        "by_application": apps,
        "engine_projects": dict(engine),
        "format_versions": dict(Counter(m["versions"]).most_common(30)),
        "by_year": dict(sorted(m["years"].items())),
        "internal_dates_by_year": dict(sorted(m["internal_years"].items())),
        "pre_cutoff_share": round(m["pre"] / m["dated"], 3) if m["dated"] else None,
        "photoshop_median_megapixels": mp[len(mp) // 2] if mp else None,
        "fingerprints": {"file_sketch": m["fps"], "file_count": m["fps_count"]},
        "privacy": {"names": "not emitted", "paths": "not emitted", "content": "headers only, never stored"},
    }


def human_bytes(n) -> str:
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}"
        n /= 1024


def fmt(n) -> str:
    if n is None:
        return "n/a"
    return f"{n:.1%}" if isinstance(n, float) and n <= 1 else f"{n:,}"


def render(d: dict) -> str:
    t = d["totals"]
    L = [f"# Creative file measurement: {d['label']}", "",
         f"Measured {d['measured_at'][:10]} with {TOOL} {VERSION}. Counts only: no file names, paths or content.", "",
         "## 1. Headline", "",
         f"- {fmt(t['creative_files'])} creative files ({human_bytes(t['creative_bytes'])}): "
         f"{fmt(t['native_files'])} native working files, {fmt(t['export_files'])} exports, "
         f"{fmt(t['engine_asset_files'])} engine assets",
         f"- {fmt(t['distinct_works'])} distinct works ({fmt(t['native_files_per_work'])} native files per work); "
         f"{fmt(t['engine_projects'])} engine projects",
         f"- File dates {d['span']['first']} to {d['span']['last']}; {fmt(d['pre_cutoff_share'])} before {d['cutoff']}",
         f"- Full run: **{d['recommendation']['full_run']}** ({'; '.join(d['recommendation']['reasons']) or 'little to measure'})"
         if d.get("mode") == "simple" else f"- Mode: {d.get('mode', 'full')}",
         f"- {fmt(t['duplicate_files'])} duplicate copies ({human_bytes(t['duplicate_bytes'])}); "
         f"{fmt(t['placeholders_not_downloaded'])} cloud placeholders not counted", "",
         "## 2. By application", "",
         "| application | files | size | native | export | engine | texture | backup | distinct works |",
         "|---|---|---|---|---|---|---|---|---|"]
    for app, a in d["by_application"].items():
        L.append(f"| {app} | {fmt(a['files'])} | {human_bytes(a['bytes'])} | {fmt(a['native'])} | {fmt(a['export'])} | "
                 f"{fmt(a['engine'])} | {fmt(a['texture'])} | {fmt(a['backup'])} | {fmt(a['distinct_works'])} |")
    L += ["", f"Distinct designs (native and exports grouped): {fmt(t['distinct_designs'])}; with a native working file: "
          f"{fmt(t['designs_with_native_share'])}. CAD is {fmt(t['cad_bytes_share'])} of creative bytes; renders and images "
          f"{fmt(t['render_and_image_bytes_share'])}."]
    if d.get("zip_contents"):
        z = d["zip_contents"]
        L += [f"Inside {fmt(z.get('zips', 0))} zip files (listed, not extracted): {fmt(z.get('members', 0))} members, "
              f"{fmt(z.get('creative_members', 0))} creative ({human_bytes(z.get('creative_uncompressed_bytes', 0))} uncompressed)."]
    au = d.get("authors") or {}
    if au.get("distinct_creators_in_metadata"):
        L += [f"Distinct creators in file metadata: {fmt(au['distinct_creators_in_metadata'])}; peak {fmt(au['peak_creators_in_a_month'])} "
              f"in {au['peak_month']} (estimate)."]
    if d.get("creator_tools"):
        L += ["Authoring tools in metadata: " + ", ".join(f"{k} {fmt(v)}" for k, v in d["creator_tools"].items())]
    L += ["", "## 3. Engine projects", ""]
    L += [f"- {k}: {fmt(v)}" for k, v in d["engine_projects"].items()] or ["- none found"]
    L += ["", "## 4. Format versions (from file headers)", ""]
    L += [f"- {k}: {fmt(v)}" for k, v in d["format_versions"].items()] or ["- none read"]
    L += ["", "## 5. Dates", "", "| year | files (modification time) |", "|---|---|"]
    L += [f"| {y} | {fmt(n)} |" for y, n in d["by_year"].items()]
    if d["internal_dates_by_year"]:
        L += ["", "Internal dates written by the authoring tool (STEP headers):", ""]
        L += [f"- {y}: {fmt(n)}" for y, n in d["internal_dates_by_year"].items()]
    L += ["", "## 6. Caveats", "",
          "- Distinct works group files whose names differ only by version suffixes (v2, final, copy, dates) in the same folder.",
          "- File modification times can be reset by copies and syncs. Treat them as a lower bound on age.",
          "- Canva exports are detected from PDF/PNG metadata and Canva's default file naming, so some will be missed.",
          "- Engine caches (Library, Intermediate, ...) are skipped; `.meta` sidecar files are not counted.",
          f"- Other files not counted as creative: {fmt(t['other_files'])} ({human_bytes(t['other_bytes'])}).", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Count creative and CAD files locally. Counts only.")
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="art")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--cutoff", default="2025-01-01")
    ap.add_argument("--mode", choices=["simple", "full"], default="full",
                    help="simple = listing and file metadata only, no header reads or hashing (recommended first run); full = default")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    OPTS.simple = a.mode == "simple"
    out = a.out.expanduser().resolve()
    cutoff = dt.datetime.strptime(a.cutoff, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    state = out / ".state" / f"{re.sub(r'[^A-Za-z0-9._-]+', '-', a.label)}--{a.mode}.jsonl"
    state.parent.mkdir(parents=True, exist_ok=True)
    if a.force and state.exists():
        state.unlink()
    done = {}
    if state.exists():
        for line in state.read_text("utf-8").splitlines():
            try:
                rec = json.loads(line)
                done[rec["unit"]] = rec["data"]
            except (ValueError, KeyError):
                continue
    roots = [r.expanduser().resolve() for r in a.roots]
    for r in roots:
        if not r.exists():
            ap.error(f"root does not exist: {r.name}")
    units = []
    for r in roots:
        names = {p.name for p in r.iterdir()} if r.is_dir() else set()
        if not r.is_dir() or {"Assets", "ProjectSettings"} <= names or any(n.endswith(".uproject") for n in names):
            units.append(r)  # a single file or an engine project: one unit
        else:
            units.append(("files-only", r))
            units += sorted(p for p in r.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_DIRS)
    t0 = time.time()
    for i, unit in enumerate(units, 1):
        key = h(f"{unit[0]}:{unit[1]}" if isinstance(unit, tuple) else str(unit))
        if key in done:
            continue
        data = scan_unit(unit[1], cutoff, shallow=True) if isinstance(unit, tuple) else scan_unit(unit, cutoff)
        with state.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"unit": key, "data": data}) + "\n")
        done[key] = data
        log(f"unit {i}/{len(units)} done ({time.time() - t0:.0f}s)")
    merged = merge(list(done.values()))
    doc = build_doc(merged, a.label, a.tag, a.cutoff, len(roots), a.mode)
    doc["recommendation"] = recommend(doc)
    text = json.dumps(doc)
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|/(Users|home|Volumes)/", text):
        log("privacy check FAILED, nothing written")
        return 2
    atomic_write(out / "measure.json", json.dumps(doc, indent=2))
    atomic_write(out / "report.md", render(doc))
    log(f"wrote {out / 'measure.json'} and {out / 'report.md'}")
    if OPTS.simple:
        log(f"full run: {doc['recommendation']['full_run']}")
    return 0


def recommend(d: dict) -> dict:
    t = d["totals"]
    reasons = []
    for cond, why in ((t["native_files"] >= 500, "500+ native working files"),
                      (t["distinct_works"] >= 100, "100+ distinct works"),
                      ((d["pre_cutoff_share"] or 0) >= 0.3, "30%+ dated before the cutoff"),
                      ((t["designs_with_native_share"] or 0) >= 0.3, "30%+ of designs keep a native file"),
                      (t["engine_projects"] + t["cad_files"] > 0, "engine projects or CAD present")):
        if cond:
            reasons.append(why)
    verdict = ("already full" if d["mode"] == "full" else
               "recommended" if len(reasons) >= 3 else "optional" if len(reasons) == 2 else "not worth it")
    return {"full_run": verdict, "reasons": reasons, "estimated_full_run_minutes": int(1 + t["files_scanned"] / 20_000)}


if __name__ == "__main__":
    sys.exit(main())
