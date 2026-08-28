import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from app.services.map_service import MapService
md = MapService().get_map("map_0014776b004f")
l = md["layers"][6]
print(json.dumps({k: v for k, v in l.items() if k != "coordinates"}, ensure_ascii=False, indent=1)[:800])
l3 = md["layers"][3]  # 湖泊（城区级）polygon 带属性
print("=== 湖泊（城区级）非几何字段 ===")
print(json.dumps({k: v for k, v in l3.items() if k != "coordinates"}, ensure_ascii=False, indent=1)[:800])
print("=== 湖泊 properties 前2条 ===")
print(json.dumps(l3.get("properties", [])[:2], ensure_ascii=False)[:400])
