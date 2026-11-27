# measure-art

An agent skill for Claude Code, Codex, Grok, Hermes and other coding agents that counts creative and CAD files **on your own machine**: files by application, native working files versus exports, distinct works, engine projects, sizes, dates, format versions and duplicates. It never writes a file name or any content. It ends with a short, clearly labelled **"Why this is special"** pitch that the agent writes after the audit (dream mode).

Part of the October measurement skills: [measure-code](https://github.com/october-dev/measure-code) · [measure-data](https://github.com/october-dev/measure-data) · **measure-art** · [master-valuate](https://github.com/october-dev/master-valuate)

## Install

Requires Python 3.9+. No pip packages.

This is a plain agent skill: [`SKILL.md`](SKILL.md) holds the instructions and `scripts/` holds the tools, so any coding agent that can read files and run Python can use it.

- **Claude Code**: clone it into your skills folder and it is picked up as the `measure-art` skill:
  ```bash
  git clone https://github.com/october-dev/measure-art ~/.claude/skills/measure-art
  ```
- **Codex**: clone it into the Codex skills folder:
  ```bash
  git clone https://github.com/october-dev/measure-art ~/.codex/skills/measure-art
  ```
  Or clone it anywhere and point Codex at `SKILL.md`. When Codex works inside the repo, it reads `AGENTS.md`, which points to `SKILL.md`.
- **Grok, Hermes and other agents**: clone it anywhere and tell the agent: *"Read `<path>/SKILL.md` and follow it."*

The commands below use `$SKILL` for the folder you cloned into, for example `SKILL=~/.claude/skills/measure-art`.

## Use

**Start with simple mode** (`--mode simple`): a listing-only pass that takes minutes and says whether a full run is worth it.

In your coding agent (Claude Code, Codex, Grok, Hermes ...):

> Use measure-art on /Volumes/StudioNAS/Art and ~/Projects/MyGame, label it studio-art

Or run it directly:

```bash
python3 $SKILL/scripts/measure_art.py /Volumes/StudioNAS/Art ~/Projects/MyGame \
    --out ./measure-out/art --label studio-art --tag project:my-game
```

Output:

```
measure-out/art/
├── measure.json   # schema october.measure/v1, kind "art"
├── report.md      # ends with "Why this is special" once the pitch is added
├── dream.json     # the pitch, kept for re-runs
└── .state/        # per-folder checkpoints for resuming; delete before sharing
```

See [`examples/`](examples/) for output built from **synthetic** data.

## What a full run adds

Format versions from headers, internal dates (STEP and XMP), XMP creators (hashed) and authoring tools, Canva detection, creative files inside zips (from the member index, never extracted), duplicates, and fingerprints for dedupe in master-valuate. It also reports distinct designs with the share that keeps a native file, and the CAD and render byte shares.

## Dream mode: "Why this is special"

Counts miss taste, ambition, complexity and polish. So after the audit, the agent re-reads the report and what it saw and writes a 4-6 sentence founder-style pitch for the collection. It is on by default; `--no-dream` (or telling the agent you don't want a pitch) skips it.

The pitch must be grounded only in what the run saw and in the counts. `scripts/add_dream.py` validates it before inserting it: 4-6 sentences and no more than 160 words, no emails, URLs, handles, paths, file names, tokens or names you pass with `--deny`, and every number must already appear in the report. It is written to `measure.json` as `dream` and rendered as the last section of `report.md`, labelled as a pitch, so the counts stay neutral and credible. See [`examples/studio-nas-art/`](examples/studio-nas-art/) for a synthetic one.

```bash
python3 $SKILL/scripts/add_dream.py draft.txt --out ./measure-out/art
```

## Applications recognised

Figma, Sketch, Adobe XD, Photoshop, Illustrator, InDesign, After Effects, Premiere Pro, Blender, Maya, 3ds Max, Cinema 4D, Houdini, ZBrush, Substance, Krita/Procreate/Affinity/Clip Studio, SketchUp, AutoCAD, SolidWorks, Fusion/Inventor, CATIA/Creo/NX, Rhino, FreeCAD, CAD interchange (STEP, IGES, ...), FBX, other 3D interchange (OBJ, glTF, USD, STL, ...), Unity, Unreal, Godot, Canva exports, and image, video, PDF, audio and font exports.

To add a format, add one line to the `APPS` table at the top of `scripts/measure_art.py`.

## Privacy

- No network calls. Read-only.
- Only header bytes are read (format magic, version fields, PDF producer). Content is never stored.
- Never emitted: file or folder names, paths, layer names, text.
- Cloud placeholders are not read, so no download is triggered.
- Fingerprints are hashes of file size plus head and tail bytes, kept as a bottom-k sketch. They let master-valuate find overlapping backups.

## Test

```bash
bash tests/selftest.sh
```

It builds a synthetic creative-files tree, checks the counts and that no name leaks, and covers dream mode: insert, validation, re-runs and `--no-dream`.

## License

MIT
