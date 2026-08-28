import json, sys
sys.stdout.reconfigure(encoding="utf-8")
md = json.load(open("D:/AAA-Study/work/github/carto-agent/data/maps/map_0014776b004f.json", encoding="utf-8"))
for l in md["layers"]:
    nm = l.get("name", "")
    if "湖泊" in nm or "水系" in nm:
        feats = l.get("features") or []
        if feats:
            names = [f.get("properties", {}).get("name") for f in feats if f.get("properties", {}).get("name")]
            print(f"  {nm}: {len(feats)}要素, 有name {len(names)}个, 前12: {names[:12]}")
