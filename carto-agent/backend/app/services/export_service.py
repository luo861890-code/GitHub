"""地图导出服务 - 支持GeoJSON、SVG、PNG格式导出

将内部地图数据结构转换为标准地理数据格式：
- GeoJSON: 标准地理JSON格式，可被GIS工具直接导入
- SVG: 矢量图形格式，适合打印和文档嵌入
- PNG: 位图格式（服务端用 Pillow 按制图整饰规范渲染真实地图图片）
"""
from app.utils.logger import get_logger
logger = get_logger(__name__)
import base64
import datetime
import io
import json
import math
import os
from typing import Optional, Any

from app.core.exceptions import CartoAgentError

try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False


def _load_font(size: int):
    """加载支持中文的系统字体（Windows 中文字体优先）"""
    if not _HAS_PIL:
        return None
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",    # 黑体
        r"C:\Windows\Fonts\simsun.ttc",    # 宋体
        r"C:\Windows\Fonts\simfang.ttf",   # 仿宋
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def _pil_color(color, default: str = "#3388ff") -> str:
    """将样式色值规范化为 PIL 支持的格式（#RGB/#RRGGBB/#RRGGBBAA）"""
    if not color:
        return default
    s = str(color).strip()
    if s.startswith("#") and len(s) == 9:
        return s[:7]
    if s.startswith("#") and len(s) == 4:
        return "#" + "".join(c * 2 for c in s[1:])
    if s.lower() in ("transparent", "none"):
        return default
    return s


class ExportService:
    """地图导出服务

    提供多种格式的地图数据导出功能。
    所有方法接收地图数据字典，返回对应格式的字符串。
    """

    def __init__(self):
        """初始化导出服务"""
        logger.info("[ExportService] 初始化完成")

    def export_geojson(self, map_data: dict) -> str:
        """将地图数据转为GeoJSON格式

        将内部地图图层结构转换为标准的GeoJSON FeatureCollection。
        每个图层要素转换为一个Feature，包含geometry和properties。

        Args:
            map_data: 地图数据字典（含layers列表）

        Returns:
            GeoJSON格式的JSON字符串
        """
        features = []
        for layer in map_data.get("layers", []):
            layer_type = layer.get("type", "polyline")
            base_props = {"layer": layer.get("name", ""), "type": layer_type}
            # 面要素（features结构，如区县政区）
            for feat in layer.get("features", []):
                ring = feat.get("coordinates") or []
                if len(ring) >= 3:
                    poly = [[pt[1], pt[0]] for pt in ring if isinstance(pt, list) and len(pt) >= 2]
                    fprops = dict(base_props)
                    fprops.update(feat.get("properties") or {})
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [poly]},
                        "properties": fprops,
                    })
            # 线/点要素
            for coords in layer.get("coordinates", []):
                if isinstance(coords[0], (int, float)) and len(coords) >= 2:
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
                        "properties": dict(base_props),
                    })
                elif isinstance(coords[0], list) and len(coords) > 1:
                    line = [[pt[1], pt[0]] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
                    if len(line) > 1:
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": line},
                            "properties": dict(base_props),
                        })
        return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)

    def export_svg(self, map_data: dict) -> str:
        """生成带标准制图整饰的SVG（标题/图廓/图例/比例尺/编制说明）

        将地图要素投影到SVG画布上，生成符合行政区划图规范的矢量图形。

        Args:
            map_data: 地图数据字典

        Returns:
            SVG格式的XML字符串
        """
        import datetime
        layers = map_data.get("layers", [])
        width, height = 900, 700

        # 收集坐标（含 features 面要素）
        all_coords = []
        for layer in layers:
            for feat in layer.get("features", []):
                c = feat.get("coordinates") or []
                for pt in c:
                    if isinstance(pt, list) and len(pt) >= 2:
                        all_coords.append((pt[0], pt[1]))
            for coords in layer.get("coordinates", []):
                if isinstance(coords[0], (int, float)):
                    all_coords.append((coords[0], coords[1]))
                elif isinstance(coords[0], list):
                    for pt in coords:
                        if isinstance(pt, list) and len(pt) >= 2:
                            all_coords.append((pt[0], pt[1]))

        if not all_coords:
            return self._empty_svg(width, height, map_data.get("name", ""))

        lats = [c[0] for c in all_coords]
        lngs = [c[1] for c in all_coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        lat_range = max_lat - min_lat or 0.01
        lng_range = max_lng - min_lng or 0.01

        margin = 52
        top = 56
        bottom = height - 58

        def project(lat, lng):
            x = margin + (lng - min_lng) / lng_range * (width - 2 * margin)
            y = bottom - (lat - min_lat) / lat_range * (bottom - top)
            return x, y

        svg_elements = []

        # 1. 面要素（features，如区县政区）
        for layer in layers:
            for feat in layer.get("features", []):
                fcoords = feat.get("coordinates") or []
                fstyle = feat.get("style") or {}
                if len(fcoords) < 3:
                    continue
                pts = " ".join("%.1f,%.1f" % project(p[0], p[1]) for p in fcoords)
                fill = fstyle.get("fillColor", "#eee")
                fo = fstyle.get("fillOpacity", 0.5)
                fc = fstyle.get("color", "#999")
                svg_elements.append(
                    '<polygon points="' + pts + '" fill="' + fill + '" fill-opacity="' + str(fo) +
                    '" stroke="' + fc + '" stroke-width="0.8"/>'
                )

        # 2. 线/点要素
        for layer in layers:
            layer_type = layer.get("type", "polyline")
            style = layer.get("style", {})
            color = style.get("color", "#3388ff")
            weight = style.get("weight", 2)
            opacity = style.get("opacity", 0.8)
            for coords in layer.get("coordinates", []):
                if layer_type in ("circleMarker", "marker") and isinstance(coords[0], (int, float)):
                    x, y = project(coords[0], coords[1])
                    radius = style.get("radius", 5)
                    fill = style.get("fillColor", color)
                    svg_elements.append(
                        '<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.5"/>'
                        % (x, y, radius, fill, color)
                    )
                elif isinstance(coords[0], list) and len(coords) > 1:
                    points = ["%.1f,%.1f" % project(pt[0], pt[1]) for pt in coords if isinstance(pt, list) and len(pt) >= 2]
                    if len(points) > 1:
                        svg_elements.append(
                            '<polyline points="' + " ".join(points) + '" fill="none" stroke="' +
                            color + '" stroke-width="' + str(weight) + '" stroke-opacity="' + str(opacity) + '"/>'
                        )

        # 3. 图廓（外粗内细）
        svg_elements.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#4b5563" stroke-width="2.5"/>'
                            % (margin - 9, top - 9, width - 2 * margin + 18, bottom - top + 18))
        svg_elements.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#9ca3af" stroke-width="1"/>'
                            % (margin - 5, top - 5, width - 2 * margin + 10, bottom - top + 10))

        # 4. 图名（图廓上方居中）
        name = map_data.get("name", "") or ""
        svg_elements.append('<text x="%d" y="%d" text-anchor="middle" font-size="22" font-weight="bold" font-family="SimHei, sans-serif">%s</text>'
                            % (width // 2, top - 20, name))

        # 5. 图例（右下角，行政区划规范顺序）
        if map_data.get("map_type") == "administrative":
            lx, ly = width - 205, bottom - 168
            svg_elements.append('<rect x="%d" y="%d" width="185" height="150" fill="#ffffff" fill-opacity="0.94" stroke="#cbd5e1"/>' % (lx, ly))
            svg_elements.append('<text x="%d" y="%d" text-anchor="middle" font-size="13" font-weight="bold">图例</text>' % (lx + 92, ly + 22))
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#DC143C" stroke-width="3.5"/>' % (lx + 14, ly + 42, lx + 66, ly + 42))
            svg_elements.append('<text x="%d" y="%d" font-size="11">市域行政界线</text>' % (lx + 74, ly + 46))
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#FF6666" stroke-width="2"/>' % (lx + 14, ly + 64, lx + 66, ly + 64))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县行政界线</text>' % (lx + 74, ly + 68))
            svg_elements.append('<circle cx="%d" cy="%d" r="5" fill="#fff" stroke="#DC143C" stroke-width="2.5"/>' % (lx + 40, ly + 86))
            svg_elements.append('<text x="%d" y="%d" font-size="11">市级行政中心</text>' % (lx + 74, ly + 90))
            svg_elements.append('<circle cx="%d" cy="%d" r="3.5" fill="#fff" stroke="#DC143C" stroke-width="2"/>' % (lx + 40, ly + 108))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县级行政中心</text>' % (lx + 74, ly + 112))
            svg_elements.append('<circle cx="%d" cy="%d" r="6" fill="#E1E1CA" stroke="#FF6666" stroke-width="0.8"/>' % (lx + 40, ly + 130))
            svg_elements.append('<text x="%d" y="%d" font-size="11">区县政区（设色）</text>' % (lx + 74, ly + 134))

        # 6. 比例尺（数字比例尺 + 直线比例尺 0-40km）
        sx, sy = margin + 12, bottom - 14
        seg_w = 42
        svg_elements.append('<text x="%d" y="%d" font-size="10" fill="#333">1:400 000</text>' % (sx, sy - 12))
        svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" stroke-width="2"/>' % (sx, sy, sx + seg_w * 4, sy))
        for i in range(5):
            svg_elements.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" stroke-width="1.2"/>' % (sx + i * seg_w, sy - 5, sx + i * seg_w, sy + 5))
        labels = [(0, "0"), (1, "10"), (2, "20"), (3, "30"), (4, "40km")]
        for i, lab in labels:
            x = sx + i * seg_w - (18 if lab.endswith("km") else 3)
            svg_elements.append('<text x="%d" y="%d" font-size="9">%s</text>' % (x, sy + 16, lab))

        # 7. 编制说明（图廓外左下）
        now = datetime.datetime.now().strftime("%Y年%m月")
        svg_elements.append(
            '<text x="%d" y="%d" font-size="9" fill="#64748b">编制单位：地图制图智能体 CartoAgent | 资料来源：官方行政区划数据（DataV/OSM） | 制图时间：%s | 坐标系：CGCS2000（Web墨卡托显示）</text>'
            % (margin, height - 22, now)
        )

        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">\n'
            '<rect width="%d" height="%d" fill="#f7f5f0"/>\n' % (width, height, width, height, width, height)
            + "\n".join(svg_elements)
            + "\n</svg>"
        )

        return svg

    def _empty_svg(self, width: int, height: int, title: str) -> str:
        """生成空SVG（无坐标数据时使用）

        Args:
            width: 画布宽度
            height: 画布高度
            title: 地图标题

        Returns:
            SVG字符串
        """
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
            f'<rect width="{width}" height="{height}" fill="#f5f5f5"/>\n'
            f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
            f'font-size="14" fill="#999">{title}（无地理数据）</text>\n'
            f'</svg>'
        )

    def export_png(self, map_data: dict) -> str:
        """返回Base64编码的真实地图图片（带制图整饰）

        服务端使用 Pillow 直接渲染地图要素（面/线/点/注记）并按
        制图规范叠加：图名、图廓、图例、比例尺、指北针、经纬网、
        编制说明落款，输出 PNG 图片（Base64 data URI）。

        Returns:
            Base64编码的PNG图片字符串（带data URI前缀）
        """
        return self.export_layout_png(map_data, None)

    def export_layout_png(self, map_data: dict, layout: Optional[dict] = None) -> str:
        """按布局参数渲染带整饰的地图PNG（供“布局导出”使用）"""
        if not _HAS_PIL:
            return self._png_placeholder("服务器缺少 Pillow 依赖，无法渲染 PNG")
        layout = layout or {}

        # ========== 页面尺寸 ==========
        page_sizes_mm = {
            "A4": (210, 297),
            "A3": (297, 420),
            "A2": (420, 594),
        }
        size = page_sizes_mm.get(layout.get("pageSize", "A4"), (210, 297))
        orientation = layout.get("orientation", "landscape")
        dpi = int(layout.get("dpi", 150))
        if orientation == "landscape":
            page_w_mm, page_h_mm = max(size), min(size)
        else:
            page_w_mm, page_h_mm = min(size), max(size)
        width = int(page_w_mm / 25.4 * dpi)
        height = int(page_h_mm / 25.4 * dpi)

        show_title = layout.get("showTitle", True)
        show_legend = layout.get("showLegend", True)
        show_scale = layout.get("showScaleBar", True)
        show_north = layout.get("showNorthArrow", True)
        show_grid = layout.get("showGrid", False)
        title_text = layout.get("title") or map_data.get("name") or "地图"
        title_size = int(layout.get("titleSize", 24))
        legend_title = layout.get("legendTitle") or "图例"
        legend_pos = layout.get("legendPosition", "topright")
        scale_pos = layout.get("scaleBarPosition", "bottomleft")

        # ========== 背景与边距 ==========
        img = Image.new("RGB", (width, height), "#faf8f3")
        draw = ImageDraw.Draw(img)

        # 图廓区域（内图廓）
        margin_x = int(width * 0.07)
        top = int(height * 0.10) if show_title else int(height * 0.05)
        bottom = height - int(height * 0.10)

        # ========== 收集坐标并计算投影 ==========
        all_coords = []
        layers = map_data.get("layers", []) or []
        for layer in layers:
            for feat in layer.get("features", []) or []:
                c = feat.get("coordinates") or []
                for pt in c:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        all_coords.append((float(pt[0]), float(pt[1])))
            for coords in layer.get("coordinates", []) or []:
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    if isinstance(coords[0], (int, float)):
                        all_coords.append((float(coords[0]), float(coords[1])))
                    elif isinstance(coords[0], (list, tuple)):
                        for pt in coords:
                            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                                all_coords.append((float(pt[0]), float(pt[1])))

        if all_coords:
            min_lat = min(c[0] for c in all_coords)
            max_lat = max(c[0] for c in all_coords)
            min_lng = min(c[1] for c in all_coords)
            max_lng = max(c[1] for c in all_coords)
            lat_range = max_lat - min_lat or 0.01
            lng_range = max_lng - min_lng or 0.01
        else:
            min_lat, max_lat, min_lng, max_lng = 29.8, 31.4, 113.7, 115.1
            lat_range = max_lat - min_lat
            lng_range = max_lng - min_lng

        def project(lat, lng):
            x = margin_x + (float(lng) - min_lng) / lng_range * (width - 2 * margin_x)
            y = bottom - (float(lat) - min_lat) / lat_range * (bottom - top)
            return x, y

        # ========== 经纬网（可选） ==========
        if show_grid:
            step = 0.5
            south = math.floor(min_lat / step) * step
            north = math.ceil(max_lat / step) * step
            west = math.floor(min_lng / step) * step
            east = math.ceil(max_lng / step) * step
            lat = south
            while lat <= north + 1e-9:
                p1 = project(lat, min_lng)
                p2 = project(lat, max_lng)
                draw.line([p1, p2], fill="#cbd5e1", width=1)
                lat += step
            lng = west
            while lng <= east + 1e-9:
                p1 = project(min_lat, lng)
                p2 = project(max_lat, lng)
                draw.line([p1, p2], fill="#cbd5e1", width=1)
                lng += step

        # ========== 绘制地图要素（面 → 线 → 点） ==========
        # 面要素
        for layer in layers:
            for feat in layer.get("features", []) or []:
                fcoords = feat.get("coordinates") or []
                style = feat.get("style") or layer.get("style") or {}
                if len(fcoords) < 3:
                    continue
                pts = [project(p[0], p[1]) for p in fcoords]
                fill = _pil_color(style.get("fillColor"), "#eee")
                outline = _pil_color(style.get("color"), "#999")
                try:
                    draw.polygon(pts, fill=fill, outline=outline)
                except Exception:
                    pass
        # 线要素
        for layer in layers:
            ltype = layer.get("type", "")
            style = layer.get("style", {}) or {}
            color = _pil_color(style.get("color"), "#3388ff")
            weight = max(1, int(style.get("weight", 2)))
            for coords in layer.get("coordinates", []) or []:
                if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    continue
                if isinstance(coords[0], (int, float)):
                    continue  # 点要素单独绘制
                pts = [project(p[0], p[1]) for p in coords if isinstance(p, (list, tuple)) and len(p) >= 2]
                if len(pts) >= 2:
                    draw.line(pts, fill=color, width=weight, joint="curve")
        # 点要素
        for layer in layers:
            ltype = layer.get("type", "")
            if ltype not in ("circleMarker", "marker", "point"):
                continue
            style = layer.get("style", {}) or {}
            color = _pil_color(style.get("color"), "#ef4444")
            fill = _pil_color(style.get("fillColor"), color)
            radius = max(2, int(style.get("radius", 5)))
            for coords in layer.get("coordinates", []) or []:
                if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    continue
                if not isinstance(coords[0], (int, float)):
                    continue
                x, y = project(coords[0], coords[1])
                draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                             fill=fill, outline=color, width=2)

        # ========== 图廓（外粗内细） ==========
        draw.rectangle([margin_x - 9, top - 9, width - margin_x + 9, bottom + 9],
                       outline="#4b5563", width=3)
        draw.rectangle([margin_x - 5, top - 5, width - margin_x + 5, bottom + 5],
                       outline="#9ca3af", width=1)

        # ========== 图名 ==========
        if show_title:
            font_title = _load_font(int(title_size * dpi / 96)) or _load_font(24)
            if font_title:
                bbox = draw.textbbox((0, 0), title_text, font=font_title)
                tx = (width - (bbox[2] - bbox[0])) / 2 - bbox[0]
                draw.text((tx, top - (title_size * dpi / 96) - 12), title_text,
                          fill="#1f2937", font=font_title)

        # ========== 指北针 ==========
        if show_north:
            nx, ny = width - margin_x + 4, top + 18
            arrow_len = int(14 * dpi / 96)
            draw.line([(nx, ny - arrow_len), (nx, ny)], fill="#dc2626", width=3)
            draw.polygon([(nx - 5, ny - arrow_len + 5), (nx + 5, ny - arrow_len + 5), (nx, ny - arrow_len - 6)],
                         fill="#dc2626")
            font_n = _load_font(int(12 * dpi / 96))
            if font_n:
                draw.text((nx - 3, ny - arrow_len - 22), "N", fill="#dc2626", font=font_n)

        # ========== 图例 ==========
        if show_legend:
            legend_items = self._legend_items(map_data)
            item_h = int(16 * dpi / 96)
            pad = int(8 * dpi / 96)
            lw = int(170 * dpi / 96)
            lh = pad + item_h + item_h * max(1, len(legend_items)) + pad
            if legend_pos == "topright":
                lx = width - margin_x - lw - 8
                ly = top + 8
            elif legend_pos == "bottomleft":
                lx = margin_x - lw + 4
                ly = bottom - lh - 8
            elif legend_pos == "bottomright":
                lx = width - margin_x - lw - 8
                ly = bottom - lh - 8
            else:
                lx = margin_x - lw + 4
                ly = top + 8
            lx = max(4, min(lx, width - lw - 4))
            ly = max(top, min(ly, height - lh - 4))
            draw.rectangle([lx, ly, lx + lw, ly + lh], fill="#ffffff", outline="#cbd5e1", width=1)
            font_legend_title = _load_font(int(13 * dpi / 96))
            if font_legend_title:
                draw.text((lx + pad, ly + pad - 3), legend_title, fill="#111827", font=font_legend_title)
            font_legend = _load_font(int(11 * dpi / 96))
            y = ly + pad + item_h - 3
            for item in legend_items[:12]:
                label = item.get("label", "")
                color = _pil_color(item.get("color") or item.get("fillColor") or "#3388ff")
                ltype = item.get("type", "")
                if ltype == "line":
                    draw.line([(lx + pad, y + item_h // 2), (lx + pad + 22, y + item_h // 2)],
                              fill=color, width=3)
                else:
                    draw.rounded_rectangle([lx + pad, y + 2, lx + pad + 18, y + item_h - 2],
                                           radius=2, fill=color, outline=color)
                if font_legend:
                    draw.text((lx + pad + 28, y), label[:12], fill="#374151", font=font_legend)
                y += item_h

        # ========== 比例尺 ==========
        if show_scale:
            bar_w = int(130 * dpi / 96)
            bar_h = int(14 * dpi / 96)
            if scale_pos == "bottomright":
                sx = width - margin_x - bar_w
            else:
                sx = margin_x - 8
            sy = bottom + 22
            seg = bar_w / 4
            draw.line([(sx, sy), (sx + bar_w, sy)], fill="#333333", width=2)
            for i in range(5):
                x0 = sx + i * seg
                draw.line([(x0, sy - 5), (x0, sy + 5)], fill="#333333", width=2)
                if i % 2 == 0:
                    draw.rectangle([x0, sy - 5, x0 + seg, sy], fill="#333333")
            font_scale = _load_font(int(10 * dpi / 96))
            if font_scale:
                draw.text((sx - 2, sy + 8), "0", fill="#333333", font=font_scale)
                # 估算地面距离（赤道近似：1度约111km）
                span_deg = lng_range * (bar_w / (width - 2 * margin_x))
                span_km = span_deg * 111
                label = self._nice_km_label(span_km)
                draw.text((sx + bar_w - 42, sy + 8), label, fill="#333333", font=font_scale)

        # ========== 编制说明落款 ==========
        font_attr = _load_font(int(9 * dpi / 96))
        if font_attr:
            now = datetime.datetime.now().strftime("%Y年%m月")
            text = ("编制单位：地图制图智能体 CartoAgent | 资料来源：官方行政区划数据（DataV/OSM）"
                    f" | 制图时间：{now} | 坐标系：WGS84（Web墨卡托显示）")
            bbox = draw.textbbox((0, 0), text, font=font_attr)
            draw.text(((width - (bbox[2] - bbox[0])) / 2 - bbox[0], height - 22),
                      text, fill="#64748b", font=font_attr)

        # ========== 输出 ==========
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        logger.info(f"[ExportService] PNG导出成功: {width}x{height}px, "
              f"地图「{map_data.get('name', '')}」")
        return f"data:image/png;base64,{b64_str}"

    def _legend_items(self, map_data: dict) -> list:
        """从地图数据中提取图例项（优先使用后端生成的图例）"""
        legend = map_data.get("legend") or {}
        items = legend.get("items") or []
        if items:
            return items
        # 兜底：按图层类型生成
        out = []
        for layer in map_data.get("layers", []) or []:
            style = layer.get("style") or {}
            ltype = layer.get("type", "")
            item_type = "line" if ltype in ("polyline", "line") else (
                "polygon" if ltype in ("polygon", "area") else "point")
            out.append({
                "label": layer.get("name", ""),
                "type": item_type,
                "color": _pil_color(style.get("color"), "#3388ff"),
                "fillColor": _pil_color(style.get("fillColor"), style.get("color", "#3388ff")),
            })
        return out

    def _nice_km_label(self, km: float) -> str:
        """将估算的地面距离格式化为美观的比例尺标签"""
        if km <= 0:
            return "1 km"
        if km < 1:
            return f"{int(km * 1000)} m"
        if km < 10:
            return f"{int(round(km))} km"
        mag = 10 ** int(math.log10(km))
        norm = km / mag
        if norm <= 1:
            nice = mag
        elif norm <= 2:
            nice = 2 * mag
        elif norm <= 5:
            nice = 5 * mag
        else:
            nice = 10 * mag
        return f"{int(nice)} km"

    def _png_placeholder(self, message: str) -> str:
        """Pillow 缺失时的兜底占位图（带错误信息文本）"""
        if _HAS_PIL:
            img = Image.new("RGB", (800, 500), "#faf8f3")
            draw = ImageDraw.Draw(img)
            font = _load_font(20)
            draw.text((40, 220), message, fill="#991b1b",
                      font=font or None)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
        return "data:image/png;base64," + base64.b64encode(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            )
        ).decode("utf-8")

    def export(self, map_data: dict, fmt: str = "geojson") -> str:
        """统一导出接口

        Args:
            map_data: 地图数据字典
            fmt: 导出格式（geojson/svg/png）

        Returns:
            对应格式的字符串

        Raises:
            CartoAgentError: 不支持的格式
        """
        if fmt == "geojson":
            return self.export_geojson(map_data)
        elif fmt == "svg":
            return self.export_svg(map_data)
        elif fmt == "png":
            return self.export_png(map_data)
        else:
            raise CartoAgentError(f"不支持的导出格式: {fmt}，支持: geojson, svg, png")
