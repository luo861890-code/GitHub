import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
# 验证 map_7e01062a00d5
req = urllib.request.Request("http://127.0.0.1:8080/api/maps/map_7e01062a00d5")
with urllib.request.urlopen(req, timeout=60) as resp:
    d = json.loads(resp.read().decode("utf-8"))
md = d.get("data") or d
hidden = [l.get("name") for l in md.get("layers",[]) if l.get("visible") is False]
hub = next((len(l.get("coordinates") or []) for l in md.get("layers",[]) if l.get("name")=="交通枢纽"), None)
print("map_7e01062a00d5: 隐藏=", hidden)
print("  交通枢纽=", hub)
