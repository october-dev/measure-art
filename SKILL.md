---
name: measure-art
description: Count creative and CAD files locally - Figma, Blender, Unity/Unreal/Godot projects, FBX and other 3D, Photoshop, Illustrator, After Effects, Canva exports, SketchUp, AutoCAD, SolidWorks and other CAD - and write counts only (files by application, native vs export, distinct works, engine projects, sizes, dates, format versions, duplicates, plus Wwise and FMOD projects, localisation and narrative files, engine content counts, template and Asset Store content, pre-2025 and pre-ChatGPT shares, labels on every number and restriction flags) into measure.json + report.md, ending with a short, clearly labelled "Why this is special" pitch written after the audit (dream mode, on by default, --no-dream skips it). Full mode is the default; simple mode (optional) is a fast listing pass, used only when the user asks for a quick look. Use when the user asks to "count our art/design/3D/CAD files", "inventory creative assets", "how many Blender/PSD/Unity files do we have", or to prepare inputs for master-valuate. Never emits file names or content.
---

# measure-art

Inventories creative working files **on this machine**. The script walks folders and reads a few **header bytes** per file to identify formats and versions. It never opens layers, scenes or images and never makes network calls. The output holds counts, sizes, dates and version strings, plus one-way fingerprints for dedupe. `<skill-dir>` below is the folder holding this SKILL.md.

## Two modes

| mode | what runs | time |
|---|---|---|
| `--mode simple` (optional) | directory listing and file metadata only (size, modification time, extension, folder grouping). No header reads, no hashing, no zip listing. Ends with a **full-run recommendation**. | minutes, even on large disks |
| `--mode full` (default) | adds header probes (format versions, STEP and XMP dates, XMP creators and tools, Canva detection), zip member listing, duplicate detection and fingerprints for master-valuate | longer; about one file header per file |

## Steps

1. **Find the roots.** Ask where the creative files live: disks, NAS shares, synced Dropbox or Drive folders, engine project folders. One run can take several roots. Use one run per **collection** you want to show separately, for example `--label studio-nas` and `--label laptop-backup`.
2. **Make files local.** Cloud-only files (iCloud, Dropbox Smart Sync, Drive streaming) are counted as `placeholders_not_downloaded` and never read, because reading them would trigger a download. If that number is large, ask the user to make the folders available offline and re-run.
3. **Full run** (the default):
   ```bash
   python3 <skill-dir>/scripts/measure_art.py <root> [<root> ...] --out <out-dir> --label <label> [--tag project:<name>] \
       [--cutoff 2025-01-01] [--cutoff-early 2022-11-30] [--flag <name>[=no]] [--ownership own|client_owned|unclear]
   ```
   **Simple mode (optional): a fast sampled pass, used only when asked to do a quick look.** Do not choose it on your own; add `--mode simple` only if the user explicitly asks for a quick look.
   Ask whether any of the collection is client work (work-for-hire art) or holds platform-holder material, and record it with `--ownership client_owned` or `--flag client_owned`, `--flag platform_nda` (`NAME=no` records a no). Flags are recorded, not ruled on; ownership defaults to `own`.
   The output folder must be outside the roots. For large disks, run in the background (`nohup ... > run.log 2>&1 &`). Each top-level folder is checkpointed in `<out-dir>/.state/`, so a re-run resumes, and `--force` starts over.
4. **Dream: "Why this is special"** (on by default). Skip this step only if the user passed or asked for `--no-dream` (no pitch); then record the skip with `python3 <skill-dir>/scripts/add_dream.py --no-dream --out <out-dir>`, or pass `--no-dream` to `measure_art.py`. Otherwise, once the measurement and `report.md` are complete, dream: re-read the report and recall what you actually saw during the run (the folders the user pointed you at, the application mix, the asset types and volumes in the counts, engine projects), then write a short founder-style pitch for the collection.
   - **4 to 6 sentences, casual and simple**, not verbose. Say what the counts miss: taste, ambition, complexity and polish. For example "the full art pipeline of an AAA-style Unity game, with richly detailed characters and complete end-to-end levels", years of one team's craft, or a rare CAD library.
   - **Grounded only in what you saw in this run** and in the counts. No invented facts. No number that is not in the report (quote figures as the report shows them). No superlatives about things you did not inspect. The script never opens images, so do not describe what the art looks like unless the user showed you.
   - **Same privacy rules as everything else**: no file or folder names, paths, people's names (XMP creators included), emails, URLs or secrets. Describe the product or genre in general terms.
   - Save it in a draft text file outside the roots, then run `python3 <skill-dir>/scripts/add_dream.py draft.txt --out <out-dir> [--deny "<a name you saw>" ...]`. It checks that the paragraph is not empty, has 4 to 6 sentences and no more than 160 words, holds no email, URL, handle, path, file name, token or denied name, and that every number in it appears in the report or `measure.json`. It warns about superlatives. Then it writes the `dream` block into `measure.json` and adds the **Why this is special** section at the very end of `report.md`, labelled as a pitch and kept apart from the counts. If it refuses, fix what it names and run it again: never loosen a fact to get past a check. `--check` validates without writing. Re-runs keep the paragraph and check it again. Delete the draft afterwards.
5. **Review with the user.** Read `report.md` together, including the pitch. Check that the application mix matches what the user expects, and that `native_files` is not near zero (exports alone are worth much less to buyers). Check whether `duplicate_files` points at backups of backups.
6. **Hand off.** `measure.json` goes to **master-valuate**. Delete `.state/` before sharing.

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
- **Labels.** Every material number has a label in `labels` (`verified`, `estimated`, `self_reported`, `unknown`, `not_applicable`); `estimated` comes with a `method`. Unknown is `null`, never `0`.
- **Two cutoffs.** `cutoffs.pre_2025` and `cutoffs.pre_chatgpt` give the count and share of dated creative files modified before `--cutoff` (default 2025-01-01) and `--cutoff-early` (default 2022-11-30). Modification times can be reset by copies, so they are labelled `estimated`.
- **Studio content** (`studio_content`): Wwise (`.wproj`) and FMOD (`.fspro`) projects and sound banks (`.bnk`, `.bank`), localisation and narrative files (`.po`, `.xliff`, `.ink`, `.yarn`, `.strings`, `.resx`, articy exports and more), engine content counts (`.uasset`, `.umap`, `.unity`, `.prefab`, `.tscn`), files in template content folders (`StarterContent`, `ThirdPerson`, `Megascans` ...) and in Asset Store or Marketplace folders, and `.unitypackage` files. Blueprints and Blueprint nodes are counted by measure-code, not here.
- **Restrictions** (`restrictions`): ownership (default `own`) and six flags: client-owned, platform NDA, third-party middleware (Asset Store, Marketplace and template content), player and staff personal data, secrets. Each is `{value, label, method}`; what the scan cannot see stays `unknown`.
- **Engine projects** are Unity (with editor version), Unreal and Godot project roots. Engine caches such as `Library` and `Intermediate` are skipped, and `.meta` files are ignored.

## Hard rules

- Read-only. Never move, rename or open files in their applications.
- Never list file or folder names in the chat or the report. If the user wants to know where the bulk is, answer with counts per top-level folder that the user names themselves.
