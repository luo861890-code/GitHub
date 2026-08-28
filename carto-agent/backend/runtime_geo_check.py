import sys
sys.stdout.reconfigure(encoding="utf-8")
import app.services.geo_service as gs
src = open(gs.__file__, encoding="utf-8").read()
# 找武汉市域边界相关
import re
for kw in ["wh_rings", "武汉市域边界", "市域边界", "build_surrounding", "def build_surrounding_layers", "WH_", "wuhan_boundary"]:
    idxs = [m.start() for m in re.finditer(kw, src)]
    if idxs:
        print(f"{kw}: {len(idxs)}处")
        for i in idxs[:3]:
            print("   ...", src[max(0,i-60):i+80].replace(chr(10)," ")[:140])
