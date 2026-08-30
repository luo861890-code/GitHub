import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from app.services.map_service import MapService
md = MapService().get_map("map_0014776b004f")
# 看市域边界图层结构（polygon, layer_6 武汉市域底图）+ 一个 polygon 要素结构
l = md["layers"][6]  # 武汉市域底图
print("=== layer keys ===", list(l.keys()))
print("=== 武汉市域底图 layer ===")
print(json.dumps({k: (v if k not in ("coordinates",) else f"<{len(v)} features>") for k, v in l.items()}, ensure_ascii=False, indent=1)[:1200])
feat = l["coordinates"][0] if isinstance(l["coordinates"], list) and l["coordinates"] else None
print("=== 一个要素结构 ===")
print(json.dumps(feat, ensure_ascii=False)[:800])
