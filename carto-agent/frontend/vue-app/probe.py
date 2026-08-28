import sys
sys.stdout.reconfigure(encoding="utf-8")
p = "src/components/MapCanvas.vue"
src = open(p, encoding="utf-8").read()
# 加唯一标记注释（模板部分最顶）
marker = "<!-- CARTO_BUILD_PROBE_20260828 -->"
if marker not in src:
    src = src.replace("<template>", "<template>\n" + marker, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("已插入探针标记")
else:
    print("探针已存在")
