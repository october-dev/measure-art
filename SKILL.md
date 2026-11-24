---
name: measure-art
description: Count creative and CAD files locally - Figma, Blender, Unity/Unreal/Godot projects, FBX and other 3D, Photoshop, Illustrator, After Effects, Canva exports, SketchUp, AutoCAD, SolidWorks and other CAD - and write counts only (files by application, native vs export, distinct works, engine projects, sizes, dates, format versions, duplicates) into measure.json + report.md. Start with --mode simple (listing and file metadata only, minutes) to see whether a full run is worth it. Use when the user asks to "count our art/design/3D/CAD files", "inventory creative assets", "how many Blender/PSD/Unity files do we have", or to prepare inputs for master-valuate. Never emits file names or content.
---

# measure-art

Inventories creative working files **on this machine**. The script walks folders and reads a few **header bytes** per file to identify formats and versions. It never opens layers, scenes or images and never makes network calls. The output holds counts, sizes, dates and version strings, plus one-way fingerprints for dedupe.

## Two modes

| mode | what runs | time |
|---|---|---|
| `--mode simple` (**recommended first run**) | directory listing and file metadata only (size, modification time, extension, folder grouping). No header reads, no hashing, no zip listing. Ends with a **full-run recommendation**. | minutes, even on large disks |
| `--mode full` (default) | adds header probes (format versions, STEP and XMP dates, XMP creators and tools, Canva detection), zip member listing, duplicate detection and fingerprints for master-valuate | longer; about one file header per file |

## Steps

1. **Find the roots.** Ask where the creative files live: disks, NAS shares, synced Dropbox or Drive folders, engine project folders. One run can take several roots. Use one run per **collection** you want to show separately, for example `--label studio-nas` and `--label laptop-backup`.
2. **Make files local.** Cloud-only files (iCloud, Dropbox Smart Sync, Drive streaming) are counted as `placeholders_not_downloaded` and never read, because reading them would trigger a download. If that number is large, ask the user to make the folders available offline and re-run.
3. **Simple run first** (`--mode simple`, same arguments), then read the "Full run" line in `report.md` with the user. **Full run:**
   ```bash
   python3 <skill-dir>/scripts/measure_art.py <root> [<root> ...] --out <out-dir> --label <label> [--tag project:<name>] [--cutoff 2025-01-01]
   ```
   The output folder must be outside the roots. For large disks, run in the background (`nohup ... > run.log 2>&1 &`). Each top-level folder is checkpointed in `<out-dir>/.state/`, so a re-run resumes, and `--force` starts over.
4. **Review with the user.** Read `report.md` together. Check that the application mix matches what the user expects, and that `native_files` is not near zero (exports alone are worth much less to buyers). Check whether `duplicate_files` points at backups of backups.
5. **Hand off.** `measure.json` goes to **master-valuate**. Delete `.state/` before sharing.

## What is counted

| role | meaning | examples |
|---|---|---|
| native | editable working file | `.blend`, `.psd`, `.aep`, `.ai`, `.fig`, `.skp`, `.dwg`, `.sldprt`, `.3dm`, `.ma`, `.max`, `.spp` |
| export | flattened or interchange output | `.fbx`, `.obj`, `.glb`, `.png`, `.mp4`, `.pdf`, `.step`, `.dxf` |
| engine | engine scene or asset | `.unity`, `.prefab`, `.mat`, `.uasset`, `.umap`, `.tscn` |
| texture | an image inside an engine project | `.png`, `.tga` under a Unity project |
| backup | application autosave or backup | `.blend1`, `.skb`, `.dwl` |

- **Distinct designs** group native files and exports of the same piece of work in a folder. `designs_with_native_share` is the share of designs that still have their editable source. `cad_bytes_share` and `render_and_image_bytes_share` keep renders from being quoted as the dataset.
- **Zip contents** are counted from each zip's member index (`zip_contents`), never extracted.
- **Authors and tools** come from XMP metadata: `authors.distinct_creators_in_metadata` (hashed), `peak_creators_in_a_month`, and `creator_tools` (for example Adobe Photoshop with its version). These are estimates: many files carry no XMP.
- Caches (After Effects disk cache, media cache, auto-save folders) are skipped.
- **Distinct works** group native files whose names differ only by version suffixes (`_v2`, `final`, `copy`, `(3)`, dates) in the same folder. `native_files_per_work` shows how much iteration history exists.
- **exports_with_native_source_nearby**: exports that sit next to a native file of the same work. This is a signal that the source of an export is present.
- **Format versions** come from headers: Blender version, FBX version and encoding, DWG release, SketchUp version. **Internal dates** come from STEP headers.
- **Canva exports** are detected from PDF/PNG metadata and from Canva's default file names.
- **Engine projects** are Unity (with editor version), Unreal and Godot project roots. Engine caches such as `Library` and `Intermediate` are skipped, and `.meta` files are ignored.

## Hard rules

- Read-only. Never move, rename or open files in their applications.
- Never list file or folder names in the chat or the report. If the user wants to know where the bulk is, answer with counts per top-level folder that the user names themselves.
