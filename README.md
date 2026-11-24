# measure-art

A Claude Code skill that counts creative and CAD files **on your own machine**: files by application, native working files versus exports, distinct works, engine projects, sizes, dates, format versions and duplicates. It never writes a file name or any content.

Part of the October measurement skills: [measure-code](https://github.com/october-dev/measure-code) · [measure-data](https://github.com/october-dev/measure-data) · **measure-art** · [master-valuate](https://github.com/october-dev/master-valuate)

## Install

Requires Python 3.9+. No pip packages.

```bash
git clone https://github.com/october-dev/measure-art ~/.claude/skills/measure-art
```

## Use

**Start with simple mode** (`--mode simple`): a listing-only pass that takes minutes and says whether a full run is worth it.

In Claude Code:

> Use measure-art on /Volumes/StudioNAS/Art and ~/Projects/MyGame, label it studio-art

Or run it directly:

```bash
python3 ~/.claude/skills/measure-art/scripts/measure_art.py /Volumes/StudioNAS/Art ~/Projects/MyGame \
    --out ./measure-out/art --label studio-art --tag project:my-game
```

Output:

```
measure-out/art/
├── measure.json   # schema october.measure/v1, kind "art"
├── report.md
└── .state/        # per-folder checkpoints for resuming; delete before sharing
```

See [`examples/`](examples/) for output built from **synthetic** data.

## What a full run adds

Format versions from headers, internal dates (STEP and XMP), XMP creators (hashed) and authoring tools, Canva detection, creative files inside zips (from the member index, never extracted), duplicates, and fingerprints for dedupe in master-valuate. It also reports distinct designs with the share that keeps a native file, and the CAD and render byte shares.

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

## License

MIT
