#!/usr/bin/env bash
# Builds a synthetic creative-files tree, measures it and checks the output and dream mode.
set -euo pipefail
PY="${PY:-python3}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
R="$WORK/disk"
mkdir -p "$R/ZqCharacters" "$R/ZqGame/Assets/Art" "$R/ZqGame/ProjectSettings" "$R/ZqCad"
printf 'BLENDER-v293fake' > "$R/ZqCharacters/zqhero_v1.blend"
printf 'BLENDER-v300fake' > "$R/ZqCharacters/zqhero_v2_final.blend"
printf 'BLENDER-v300fake' > "$R/ZqCharacters/zqhero_v2_final.blend1"
printf 'Kaydara FBX Binary  \x00\x1a\x00\xbc\x1c\x00\x00rest' > "$R/ZqCharacters/zqhero.fbx"
printf '8BPS\x00\x01\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x04\x00\x00\x00\x08\x00\x00\x08\x00\x03' > "$R/ZqCharacters/zqposter.psd"
printf 'png bytes' > "$R/ZqCharacters/zqposter.png"
printf 'png bytes' > "$R/ZqCharacters/zqposter copy.png"
printf 'm_EditorVersion: 2022.3.10f1\n' > "$R/ZqGame/ProjectSettings/ProjectVersion.txt"
printf '%%YAML scene' > "$R/ZqGame/Assets/ZqMain.unity"
printf 'tex' > "$R/ZqGame/Assets/Art/zqgrass.png"
printf 'AC1032rest' > "$R/ZqCad/zqbracket.dwg"
printf "ISO-10303-21;\nHEADER;\nFILE_NAME('zqbracket.step','2019-04-02T10:00:00',('x'),(''),'','','');\n" > "$R/ZqCad/zqbracket.step"
printf '%%PDF-1.4 /Producer (Canva) ' > "$R/Untitled design (3).pdf"
printf '8BPS\x00\x01\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x04\x00\x00\x00\x08\x00\x00\x08\x00\x03 <x:xmpmeta><rdf:Description xmp:CreatorTool="Adobe Photoshop 24.1" xmp:CreateDate="2018-05-03T10:00:00"><dc:creator><rdf:Seq><rdf:li>Zq Artist</rdf:li></rdf:Seq></dc:creator></rdf:Description></x:xmpmeta>' > "$R/ZqCharacters/zqbanner.psd"
mkdir -p "$R/ZqCharacters/Adobe After Effects Disk Cache"
printf 'cache' > "$R/ZqCharacters/Adobe After Effects Disk Cache/zqcache.png"
"$PY" -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],'w'); z.writestr('zqold.blend','BLENDER-v279x'); z.writestr('zqnotes.txt','x'); z.close()" "$R/ZqCharacters/zqarchive.zip"
OUT="$WORK/out"
"$PY" "$HERE/scripts/measure_art.py" "$R" --out "$OUT" --label demo-art
"$PY" "$HERE/scripts/measure_art.py" "$R" --out "$OUT" --label demo-art   # resume path
"$PY" "$HERE/scripts/measure_art.py" "$R" --out "$WORK/simple" --label demo-art --mode simple
"$PY" - "$OUT/measure.json" "$OUT/report.md" "$WORK/simple/measure.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); t = d["totals"]; apps = d["by_application"]
assert d["kind"] == "art"
assert apps["Blender"]["native"] == 2 and apps["Blender"]["backup"] == 1 and apps["Blender"]["distinct_works"] == 1, apps["Blender"]
assert apps["FBX"]["export"] == 1
assert apps["Unity"]["engine"] == 1 and apps["Image export"]["texture"] == 1
assert d["engine_projects"] == {"Unity 2022.3": 1}, d["engine_projects"]
assert t["canva_exports"] == 1 and t["cad_files"] == 2
assert t["duplicate_files"] == 2, t  # png copy + identical .blend1 backup
assert t["exports_with_native_source_nearby"] >= 2, t
assert d["internal_dates_by_year"].get("2019") == 1
assert "DWG 2018" in d["format_versions"] and "Blender 3.00" in d["format_versions"], d["format_versions"]
assert d["internal_dates_by_year"].get("2018") == 1 and d["authors"]["distinct_creators_in_metadata"] == 1, (d["internal_dates_by_year"], d["authors"])
assert d["creator_tools"] == {"Adobe Photoshop 24.1": 1}, d["creator_tools"]
assert d["zip_contents"]["creative_members"] == 1 and d["zip_contents"]["by_application"] == {"Blender": 1}, d["zip_contents"]
assert 0 < t["designs_with_native_share"] <= 1 and t["distinct_designs"] >= 4, t
assert apps["Image export"]["files"] == 3, apps["Image export"]   # the cache folder is skipped
sm = json.load(open(sys.argv[3]))
assert sm["mode"] == "simple" and sm["recommendation"]["full_run"] in ("recommended", "optional", "not worth it")
assert sm["format_versions"] == {} and sm["fingerprints"]["file_sketch"] == [] and sm["totals"]["creative_files"] == t["creative_files"]
text = open(sys.argv[1]).read() + open(sys.argv[2]).read() + open(sys.argv[3]).read()
for leak in ("zq", "Zq", "Untitled", "Artist"):
    assert leak not in text, leak
print("selftest: counts OK")
EOF
# Dream mode: validate and insert "Why this is special", keep it on re-runs, refuse bad drafts, honour --no-dream.
D="$HERE/scripts/add_dream.py"
cat > "$WORK/dream.txt" <<'EOF'
This small disk already looks like a real game studio at work. Character models, painted posters and a Unity 2022.3 project
sit together, so the art was made to ship. The Blender work kept 2 native files for one character, which shows real iteration.
There is even CAD for a physical part, and every file stays counted, never shown.
EOF
"$PY" "$D" "$WORK/dream.txt" --out "$OUT" --check 2>/dev/null
"$PY" "$D" "$WORK/dream.txt" --out "$OUT" --deny "Zq Artist" >/dev/null 2>&1
"$PY" "$HERE/scripts/measure_art.py" "$R" --out "$OUT" --label demo-art 2>/dev/null   # a re-run keeps it
refuse() {
  printf '%s\n' "$2" > "$WORK/bad.txt"
  if "$PY" "$D" "$WORK/bad.txt" --out "$OUT" --deny "Zq Artist" --check 2>/dev/null; then echo "dream accepted: $1"; exit 1; fi
}
refuse empty ""
refuse too-short "Nice art. Real craft."
refuse file-name "It has 2 Blender files. The hero lives in zqhero_v2_final.blend now. It is polished. It ships."
refuse path "It has 2 Blender files. The hero sits in ZqCharacters/hero/ today. It is polished. It ships."
refuse name "It has 2 Blender files. Zq Artist painted every poster. It is polished. It ships."
refuse email "It has 2 Blender files. Write to art@example.com for more. It is polished. It ships."
refuse invented-number "It has 2 Blender files. It took 40,000 hours to make. It is polished. It ships."
"$PY" "$HERE/scripts/measure_art.py" "$R" --out "$WORK/nodream" --label demo-art --no-dream 2>/dev/null
cp -R "$OUT" "$WORK/declined" && "$PY" "$D" --no-dream --out "$WORK/declined" >/dev/null 2>&1
"$PY" "$D" "$HERE/examples/studio-nas-art/dream.txt" --out "$HERE/examples/studio-nas-art" --check 2>/dev/null
"$PY" - "$WORK" <<'EOF'
import json, sys, pathlib
w = pathlib.Path(sys.argv[1])
d = json.loads((w / "out/measure.json").read_text()); rep = (w / "out/report.md").read_text()
dr = d["dream"]
assert dr["status"] == "written" and dr["title"] == "Why this is special" and dr["sentences"] == 4, dr
assert rep.rstrip().endswith("never shown.") and rep.index("## Why this is special") > rep.index("## 6. Caveats"), rep[-400:]
for leak in ("zq", "Zq", "Artist"):
    assert leak not in rep and leak not in json.dumps(d), leak
assert json.loads((w / "simple/measure.json").read_text())["dream"]["status"] == "pending"
nd = json.loads((w / "nodream/measure.json").read_text())
assert nd["dream"]["status"] == "skipped" and "Why this is special" not in (w / "nodream/report.md").read_text()
dc = json.loads((w / "declined/measure.json").read_text())
assert dc["dream"]["status"] == "skipped" and "Why this is special" not in (w / "declined/report.md").read_text()
print("selftest: dream mode OK")
EOF
# v0.4: audio middleware, localisation, engine content, template and Asset Store content, both cutoffs, labels, flags.
S="$WORK/studio"
mkdir -p "$S/ZqAudio/WwiseProject" "$S/ZqAudio/Fmod" "$S/ZqLoc" "$S/ZqUnreal/Content/StarterContent" "$S/ZqUnreal/Content/Zq" \
         "$S/ZqUnity/Assets/Plugins/ZqVendor" "$S/ZqUnity/ProjectSettings" "$S/ZqGodot" "$S/ZqPlat/PS5"
printf 'x' > "$S/ZqAudio/WwiseProject/ZqGame.wproj"; printf 'x' > "$S/ZqAudio/WwiseProject/ZqSfx.wwu"
printf 'x' > "$S/ZqAudio/WwiseProject/Init.bnk"; printf 'x' > "$S/ZqAudio/Fmod/ZqGame.fspro"; printf 'x' > "$S/ZqAudio/Fmod/Master.bank"
printf 'msgid ""\n' > "$S/ZqLoc/fr.po"; printf '<xliff/>' > "$S/ZqLoc/de.xliff"; printf '== start\n' > "$S/ZqLoc/story.ink"
printf 'title: x\n' > "$S/ZqLoc/dialogue.yarn"; printf 'x' > "$S/ZqLoc/zq_articy_export.json"
printf '{}' > "$S/ZqUnreal/Zq.uproject"; printf 'x' > "$S/ZqUnreal/Content/Zq/BP_Zq.uasset"; printf 'x' > "$S/ZqUnreal/Content/Zq/Main.umap"
printf 'x' > "$S/ZqUnreal/Content/StarterContent/M_Rock.uasset"
printf 'm_EditorVersion: 2021.3.1f1\n' > "$S/ZqUnity/ProjectSettings/ProjectVersion.txt"
printf 'x' > "$S/ZqUnity/Assets/Plugins/ZqVendor/icon.png"; printf 'x' > "$S/ZqUnity/Assets/Zq.prefab"; printf 'x' > "$S/ZqUnity/zqpack.unitypackage"
printf 'x' > "$S/ZqGodot/zq.tscn"; printf 'x' > "$S/ZqPlat/PS5/zqbutton.png"
touch -t 202101010000 "$S/ZqAudio/WwiseProject/ZqGame.wproj" "$S/ZqLoc/fr.po"
touch -t 202306010000 "$S/ZqAudio/Fmod/ZqGame.fspro"
"$PY" "$HERE/scripts/measure_art.py" "$S" --out "$WORK/studio-out" --label studio --no-dream 2>/dev/null
"$PY" "$HERE/scripts/measure_art.py" "$S" --out "$WORK/studio-simple" --label studio --mode simple --no-dream \
  --cutoff-early 2023-12-31 --flag client_owned --flag secrets=no 2>/dev/null
if "$PY" "$HERE/scripts/measure_art.py" "$S" --out "$WORK/bad" --flag nonsense 2>/dev/null; then echo "unknown flag accepted"; exit 1; fi
"$PY" - "$WORK" <<'PYEOF'
import json, sys, pathlib
w = pathlib.Path(sys.argv[1])
d = json.loads((w / "studio-out/measure.json").read_text()); rep = (w / "studio-out/report.md").read_text()
sc = d["studio_content"]
assert sc["audio_middleware"] == {"wwise_projects": 1, "fmod_projects": 1, "sound_banks": 2}, sc["audio_middleware"]
assert sc["localisation"]["files"] == 5 and sc["localisation"]["by_format"] == {"articy": 1, "ink": 1, "po": 1, "xliff": 1, "yarn": 1}, sc["localisation"]
assert sc["engine_content"] == {"uasset": 2, "umap": 1, "unity": 0, "prefab": 1, "tscn": 1}, sc["engine_content"]
assert sc["template_content_files"] == 1 and sc["asset_store_or_marketplace_files"] == 1 and sc["asset_store_packages"] == 1, sc
assert sc["blueprints"] is None and sc["blueprints_label"] == "not_applicable"
assert d["by_application"]["Wwise"]["native"] == 2 and d["by_application"]["FMOD"]["export"] == 1
c = d["cutoffs"]
assert c["pre_chatgpt"]["date"] == "2022-11-30" and c["pre_chatgpt"]["count"] == 1 and c["pre_2025"]["count"] == 2, c
assert c["pre_chatgpt"]["label"] == "estimated" and d["cutoff_early"] == "2022-11-30"
f = d["restrictions"]["flags"]
assert d["restrictions"]["ownership"] == "own" and f["third_party_middleware"]["value"] is True and f["third_party_middleware"]["count"] == 3, f
assert f["platform_nda"]["value"] is True and f["client_owned"]["value"] is None and f["client_owned"]["label"] == "unknown", f
lb = d["labels"]
assert lb["totals.creative_files"]["label"] == "verified" and lb["totals.distinct_works"]["label"] == "estimated"
assert all(v.get("method") for v in lb.values() if v["label"] == "estimated")
assert "## 5b. Studio content" in rep and "pre-ChatGPT" in rep and "| third party middleware | yes (3)" in rep, rep
s = json.loads((w / "studio-simple/measure.json").read_text())
assert s["cutoffs"]["pre_chatgpt"]["count"] == 2 and s["labels"]["totals.creative_files"]["label"] == "estimated"
assert s["restrictions"]["ownership"] == "client_owned" and s["restrictions"]["flags"]["secrets"] == {"value": False, "label": "self_reported", "method": "stated by the seller"}
text = (w / "studio-out/measure.json").read_text() + rep + (w / "studio-simple/measure.json").read_text()
for leak in ("zq", "Zq", "StarterContent", "PS5", "Wwise" + "Project"):
    assert leak not in text, leak
print("selftest: studio content, cutoffs, labels and restrictions OK")
PYEOF
echo "selftest: passed"
