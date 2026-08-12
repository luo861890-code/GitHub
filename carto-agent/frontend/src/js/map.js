/**
 * 地图面板核心逻辑（MapPanel 类）
 *
 * 模块职责：
 *  - Leaflet 地图实例初始化 / 视图与主题管理
 *  - 地图数据渲染（renderMap / renderLayer）
 *  - 图层面板 / 图例 / 样式编辑器 / 元数据 / 质量检测
 *  - 比例尺 / 经纬网 / 路线规划 / 导出 / 状态栏
 *
 * 依赖加载顺序：map.js -> map-lod.js -> map-edit.js -> app.js
 * （lod/edit 通过 MapPanel.prototype 扩展本类方法）
 */


class MapPanel {
    /**
     * 构造函数
     * @param {object} app - 主应用实例
     */
    constructor(app) {
        this.app = app;
        this.map = null;                    // Leaflet地图实例
        this.currentTheme = "plain";        // 当前底图主题（默认无瓦片制图底图）
        this.tileLayer = null;              // 当前瓦片图层
        this.currentMapData = null;         // 当前地图数据
        this.currentMapId = null;           // 当前地图ID
        this.layerGroups = {};              // 图层组 {layer_id: {layer: LeafletLayer, data: layerData, visible: bool}}
        this.layerControl = null;           // Leaflet图层控制器
        this.routeLayer = null;             // 路径规划线图层
        this.routeMarkers = [];             // 路径规划标记（起点、终点）
        this.routePointMode = null;         // 路径选点模式: null / "start" / "end"
        this.selectedProfile = "driving";   // 当前选择的出行方式
        this.isModifying = false;           // 修改请求防重复标志
        this.legendControl = null;          // 图例控件(兼容)
        this.legendData = null;             // 图例数据
        this.legendActiveGroup = "全部";   // 图例当前分组
        this.legendSearch = "";           // 图例搜索关键词
        this._labelPlaced = [];           // 全局注记避让（跨图层共享，防重复堆叠）
        this.markerMode = false;          // 标注模式（点击地图添加自定义标注）
        this.elements = {};
    }

    /**
     * 初始化地图
     * @param {string} containerId - 地图容器DOM ID
     */
    /** 构建地图投影 CRS（Web墨卡托默认；高斯-克吕格/等距圆柱用proj4leaflet） */
    _buildCRS(crsKey) {
        if (crsKey === "GaussKruger" && window.L && window.L.Proj) {
            // CGCS2000 高斯-克吕格 3°分带（中央经线114°E），武汉范围
            const projDef = "+proj=tmerc +lat_0=0 +lon_0=114 +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs";
            const resolutions = [];
            let _r = 60000;
            for (let i = 0; i < 20; i++) { resolutions.push(_r); _r /= 2; }
            return new L.Proj.CRS("EPSG:4523", projDef, {
                resolutions: resolutions,
                origin: [200000, 3600000],
                bounds: L.bounds([200000, 3000000], [800000, 3600000])
            });
        }
        if (crsKey === "Equirect") return L.CRS.EPSG4326;
        return null;   // Web墨卡托：Leaflet默认
    }

    initMap(containerId = "map-container", crsKey = "WebMercator") {
        // 创建Leaflet地图实例（支持自定义投影CRS）
        const _crs = this._buildCRS(crsKey);
        const opts = {
            center: CONFIG.defaultMapCenter,
            zoom: CONFIG.defaultZoom,
            zoomControl: false,             // 禁用默认缩放控件，使用自定义工具栏
            zoomSnap: 0.05,                 // 0.05级缩放：自定义比例尺跳转误差<1%
            preferCanvas: true,             // Canvas渲染：大路网/水系统量渲染不卡顿
            attributionControl: true
        };
        if (_crs) opts.crs = _crs;
        this.map = L.map(containerId, opts);
        this.mapCrsKey = crsKey;
        this.tileLayer = null;
        const _projSel = document.getElementById("map-proj-select");
        if (_projSel) _projSel.value = crsKey;
        // 非墨卡托投影：关闭在线瓦片底图（在线瓦片为Web墨卡托，其他投影下无法对齐）
        if (crsKey === "WebMercator") {
            this.setTheme(this.currentTheme || "standard");
        } else {
            this.setTheme("plain");
        }
        if (this._uiBound) {
            // 重建地图：仅重建核心控件与底图，UI事件不重复绑定
            L.control.zoom({ position: "bottomright" }).addTo(this.map);
            this.initScaleControl();
            this.bindEvents();
            this.initGraticule();
            this._initEditable();
            this.updateStatusBar();
            return;
        }
        this._uiBound = true;
        // 添加缩放控件到右下角
        L.control.zoom({ position: "bottomright" }).addTo(this.map);
        // 添加标准分段比例尺（黑白分段、km/m标注）
        this.currentMapType = null;
        this.initScaleControl();
        // 自定义比例尺输入（工具栏）
        this._initScaleSetter();
        // 投影切换
        this._initProjSetter();
        // 绑定事件
        this.bindEvents();
        // 初始化工具栏
        this.initToolbar();
        // 初始化图层管理面板
        this.initLayerPanel();
        // 初始化图例按钮与面板
        this.initLegendPanel();
        // 初始化自然语言修改输入框
        this.initModifyInput();
        // 初始化路径规划面板
        this.initRoutePanel();
        // 标准制图整饰：经纬网与经纬度注记
        this.initGraticule();
        // 自定义标注工具（答辩演示：标注赏樱点/卫生间）
        this.initMarkerTool();
        // 编辑模式（QGIS/ArcGIS 式几何编辑）
        this._initEditable();
        this.initEditPanel();
        // 更新状态栏
        this.updateStatusBar();
    }

    /** 初始化投影切换下拉 */
    _initProjSetter() {
        const sel = document.getElementById("map-proj-select");
        if (!sel) return;
        sel.addEventListener("change", () => {
            const key = sel.value;
            const names = { WebMercator: "Web墨卡托", GaussKruger: "高斯-克吕格CGCS2000", Equirect: "等距圆柱" };
            if (key === this.mapCrsKey) return;
            this._switchProjection(key);
            Utils.showToast("已切换投影：" + (names[key] || key), "info", 2000);
        });
    }

    /** 切换投影：重建Leaflet地图并重新渲染当前数据（非墨卡托关闭瓦片底图） */
    _switchProjection(crsKey) {
        const data = this.currentMapData;
        const center = this.map.getCenter();
        const zoom = this.map.getZoom();
        // 清理旧地图与图层状态
        try { this.map.remove(); } catch (e) {}
        this.map = null;
        this.tileLayer = null;
        this.layerGroups = {};
        this._labelPlaced = [];
        this._labelNames = new Set();
        this._poiMarkers = [];
        this.graticuleGroup = null;
        this.graticuleLabelGroup = null;
        // 重建地图（新投影）
        this.initMap("map-container", crsKey);
        // 重新渲染当前地图数据并恢复视图
        if (data) {
            this.renderMap(data);
            if (center) this.map.setView([center.lat, center.lng], zoom);
        }
    }

    /** 当前投影名称 */
    _crsName() {
        if (this.mapCrsKey === "GaussKruger") return "高斯-克吕格 CGCS2000 3°分带 (EPSG:4523)";
        if (this.mapCrsKey === "Equirect") return "等距圆柱 (EPSG:4326)";
        return "Web墨卡托 (EPSG:3857)";
    }

    /**
     * 绑定地图事件
     */
    bindEvents() {
        // 地图移动/缩放时更新状态栏
        this.map.on("moveend zoomend", () => {
            this.updateStatusBar();
        });
        // 地图点击时显示坐标或设置路径起终点
        this.map.on("click", (e) => {
            const lat = e.latlng.lat.toFixed(4);
            const lng = e.latlng.lng.toFixed(4);
            // 如果在路径选点模式，设置起终点
            if (this.routePointMode) {
                this.setRoutePoint(this.routePointMode, [e.latlng.lat, e.latlng.lng]);
                this.routePointMode = null;
                this.map.getContainer().style.cursor = "";
            } else if (this.markerMode) {
                // 标注模式：点击地图添加自定义标注点
                this.addCustomMarker(e.latlng.lat, e.latlng.lng);
            } else {
                this.updateStatusBar(lat, lng);
            }
        });
    }

    /**
     * 初始化顶部工具栏
     */
    initToolbar() {
        // 主题切换下拉
        const themeSelect = document.getElementById("map-theme-select");
        if (themeSelect) {
            // 填充主题选项
            themeSelect.innerHTML = "";
            Object.entries(CONFIG.mapThemes).forEach(([key, theme]) => {
                const option = document.createElement("option");
                option.value = key;
                option.textContent = theme.name;
                if (key === this.currentTheme) option.selected = true;
                themeSelect.appendChild(option);
            });
            themeSelect.addEventListener("change", (e) => {
                this.setTheme(e.target.value);
            });
        }
        // 其他工具栏按钮由右侧工具栏触发，在app.js中绑定
    }

    /**
     * 设置底图主题
     * @param {string} theme - 主题名 standard/positron/dark/satellite
     */
    setTheme(theme) {
        const themeConfig = CONFIG.mapThemes[theme];
        if (!themeConfig) {
            Utils.showToast("未知主题: " + theme, "warning");
            return;
        }
        // 移除旧底图
        if (this.tileLayer) {
            this.map.removeLayer(this.tileLayer);
        }
        // 添加新底图（制图底图"plain"无瓦片，关闭第三方底图）
        if (themeConfig.url) {
            this.tileLayer = L.tileLayer(themeConfig.url, {
                attribution: themeConfig.attribution,
                maxZoom: themeConfig.maxZoom,
                subdomains: themeConfig.subdomains || "abc"
            }).addTo(this.map);
            // 瓦片加载失败（网络/被墙）时自动回退到高德矢量底图（国内可直连）
            if (theme !== "amap_normal" && theme !== "tianditu_vec" && theme !== "tianditu_img") {
                let _errCount = 0;
                this.tileLayer.on("tileerror", () => {
                    _errCount += 1;
                    if (_errCount >= 8 && this.currentTheme === theme) {
                        _errCount = 9999;
                        Utils.showToast("当前底图加载失败，已自动切换高德矢量底图", "info");
                        this.setTheme("amap_normal");
                    }
                });
            }
        } else {
            this.tileLayer = null;
        }
        this.currentTheme = theme;
        // 更新下拉选择
        const themeSelect = document.getElementById("map-theme-select");
        if (themeSelect) themeSelect.value = theme;
        // 如果有当前地图，通知后端更新主题
        if (this.currentMapId) {
            API.updateTheme(this.currentMapId, theme).catch(err => {
                console.warn("更新主题到后端失败:", err);
            });
        }
        this.updateStatusBar();
    }

    /**
     * 循环切换底图主题
     */
    cycleTheme() {
        const themes = Object.keys(CONFIG.mapThemes);
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % themes.length;
        this.setTheme(themes[nextIndex]);
        Utils.showToast(`底图: ${CONFIG.mapThemes[themes[nextIndex]].name}`, "info", 1500);
    }

    /**
     * 渲染后端返回的地图数据
     * @param {object} mapData - 地图数据 {map_id, name, center, zoom, theme, layers}
     */
    renderMap(mapData) {
        if (!mapData || !this.map) return;
        // 切换/刷新地图时退出编辑模式
        if (this.editMode) this.exitEditMode();
        this.currentMapData = mapData;
        this.currentMapId = mapData.map_id;
        // 清除旧图层
        this.clearAllLayers();
        // 重置全局注记避让、名称去重与符号碰撞位置
        this._labelPlaced = [];
        this._labelNames = new Set();
        this._poiMarkers = [];
        this._poiMarkers = [];
        // 更新地图视图（校验center坐标完整性，防止null/undefined导致Leaflet崩溃）
        const center = mapData.center;
        if (center && Array.isArray(center) && center.length === 2
            && center[0] != null && center[1] != null
            && !isNaN(parseFloat(center[0])) && !isNaN(parseFloat(center[1]))) {
            const zoom = mapData.zoom || CONFIG.defaultZoom;
            this.map.setView([parseFloat(center[0]), parseFloat(center[1])], zoom);
        } else {
            // center缺失或无效时使用默认中心
            console.warn("[MapPanel] 地图center坐标缺失或无效，使用默认中心:", center);
            this.map.setView(CONFIG.defaultMapCenter, CONFIG.defaultZoom);
        }
        // 记录当前地图类型：必须在渲染图层之前设置，供 LOD 层级控制与样式兜底判断
        this.currentMapType = mapData.map_type;
        // 更新主题（行政区划图忽略旧数据的"plain"无瓦片主题；非墨卡托投影保持无瓦片）
        if (this.mapCrsKey === "WebMercator"
            && mapData.theme && mapData.theme !== this.currentTheme
            && !(mapData.map_type === "administrative" && mapData.theme === "plain")) {
            this.setTheme(mapData.theme);
        }
        // 渲染所有图层（先按制图叠置顺序排序：面状底图→建筑→水系→铁路→道路→点状符号）
        if (mapData.layers && Array.isArray(mapData.layers)) {
            const roadRank = {
                "高速公路": 90, "国道": 80, "主干道": 80, "省道": 70, "主要道路": 70,
                "次干道": 60, "支路": 50, "社区道路": 40, "服务道路": 30, "其他道路": 20
            };
            const layerZ = (ld) => {
                const t = ld.type || "";
                const n = ld.name || "";
                if (t === "polygon" || t === "area") {
                    if (/陆地/.test(n)) return 0;
                    // 水体面（湖泊/水库）渲染在政区/用地色块之上，覆盖陆地填充
                    if (/水体|湖泊|水库/.test(n)) return 150;
                    if (/用地|绿地|公园|花园|森林|草地|草甸|土地|政区|区划/.test(n)) return 100;
                    if (/建筑|住宅|公寓|宿舍|商业|零售|酒店|工业|公共|政府|学校|大学|医院|宗教|文化|体育|停车|车库|仓储|交通枢纽|农业|温室|居民地|街区/.test(n)) return 200;
                    return 100;
                }
                if (t === "polyline" || t === "line") {
                    // GIS叠加顺序：底图(瓦片) → 水系 → 路网 → 行政边界 → 铁路
                    if (/水系|河流|溪流|运河|湖泊|水库/.test(n)) return 330;   // 水系（底图之上）
                    if (/等高线/.test(n)) return 310;   // 等高线（底图之上、水系/道路之下）
                    const rankKey = Object.keys(roadRank).find(k => n.indexOf(k) >= 0);
                    if (rankKey || n.indexOf("道路-") === 0) return 400;   // 路网（水系之上，含本地道路数据）
                    if (/边界|市域|省界|县界/.test(n)) return 460;            // 行政边界
                    if (/铁路|地铁|轻轨|高铁/.test(n)) return 500;
                    return 300;
                }
                if (t === "textLabel" || t === "label") return 650;
                return 600;
            };
            mapData.layers.sort((a, b) => layerZ(a) - layerZ(b));
            mapData.layers.forEach(layerData => {
                this.renderLayer(layerData);
            });
        }
        // 行政区划图（标准政区图）：矢量制图底图，湖北省域浅米/武汉市域白底，外部绝对留白
        if (mapData.map_type === "administrative") {
            this.setTheme("plain");
        }
        // 行政区划图：图幅自动适应"武汉全域+周边相邻地市"（规范九-5），
        // 避免窄屏时周边地市显示不全
        if (mapData.map_type === "administrative") {
            const bounds = L.latLngBounds([]);
            const collect = (c) => {
                if (!Array.isArray(c)) return;
                if (c.length >= 2 && typeof c[0] === "number" && !isNaN(c[0]) && !isNaN(c[1])) {
                    bounds.extend([c[0], c[1]]);
                } else {
                    c.forEach(collect);
                }
            };
            (mapData.layers || []).forEach(ld => {
                const t = ld.type || "";
                if (t === "polygon" || t === "polyline" || t === "circleMarker" || t === "textLabel" || t === "line") {
                    if (ld.coordinates) collect(ld.coordinates);
                    if (ld.features && Array.isArray(ld.features)) {
                        ld.features.forEach(f => { if (f.coordinates) collect(f.coordinates); });
                    }
                }
            });
            if (bounds.isValid()) {
                // maxZoom 限制：避免过度放大导致周边地市丢失；padding 保证图廓内完整
                this.map.fitBounds(bounds, { padding: [12, 12], maxZoom: 10.5 });
            }
        }
        // 更新图层管理面板
        this.updateLayerPanel();
        // 编制说明（坐标系/投影/数据来源，规范3.7）
        this.renderMetadata(mapData.metadata);
        // 数据质量检测（拓扑/属性/统计/专题/标注）
        this.checkQuality();
        // 渲染图例
        if (mapData.legend) {
            this.renderLegend(mapData.legend);
        }
        // 数据质量告警提示
        if (mapData.quality && mapData.quality.warnings && mapData.quality.warnings.length) {
            mapData.quality.warnings.forEach(w => Utils.showToast(w, "warning"));
        }
        // 右下角图例（可折叠抽屉）：行政区划图显示；折叠状态由localStorage记忆（默认展开）
        const miniLegendEl = document.getElementById("map-mini-legend");
        if (miniLegendEl) miniLegendEl.classList.toggle("hidden", mapData.map_type !== "administrative");
        this._applyMiniLegendState();
        // 图名版本小字"政区版"（图名右上角，规范四）
        const verTag = document.getElementById("map-version-tag");
        if (verTag) verTag.classList.toggle("hidden", mapData.map_type !== "administrative");
        // 行政区划图：图名固定"武汉市地图"（黑体大号，图廓上方居中，无框；规范四）
        if (mapData.map_type === "administrative") {
            const nameEl = document.getElementById("map-status-name");
            if (nameEl) nameEl.textContent = "武汉市地图";
        }
        // 比例尺：独立控件统一放左下角（随缩放实时更新）
        if (this.currentMapType !== mapData.map_type && this.scaleControl) {
            this.map.removeControl(this.scaleControl);
            this.scaleControl = null;
        }
        this.currentMapType = mapData.map_type;
        if (!this.scaleControl) this.initScaleControl();
        // 审图落款（图廓底边之下，规范八：编制单位/审图号/出版日期）
        const attribution = document.getElementById("map-attribution");
        if (attribution) {
            if (mapData.map_type === "administrative") {
                attribution.innerHTML = "投影：" + this._crsName() +
                    "　编制单位：地图制图智能体 CartoAgent　审图号：鄂S(2022)100号　" +
                    "出版日期：2022-04　资料来源：DataV GeoAtlas 官方行政区划数据（民政部）";
            } else {
                attribution.innerHTML = "编制单位：地图制图智能体 CartoAgent<br>" +
                    "资料来源：官方行政区划数据（DataV/OSM）<br>" +
                    "制图时间：" + new Date().toLocaleDateString("zh-CN");
            }
            attribution.classList.remove("hidden");
        }
        // 更新状态栏
        this.updateStatusBar();
        this.updateMapInfo(mapData.name);
        Utils.showToast(`地图已加载: ${mapData.name || "未命名地图"}`, "success");
    }

    /**
     * 渲染单个图层
     * @param {object} layerData - 图层数据 {id, type, name, coordinates, style, popup}
     */
    renderHeatmap(layer) {
        if (typeof L.heatLayer === 'undefined') {
            console.warn('leaflet.heat 插件未加载，使用圆形标记替代热力图');
            const group = L.layerGroup();
            const coords = layer.coordinates || [];
            const style = layer.style || {};
            const colorScheme = style.color_scheme || ['#000004', '#320a5e', '#781c6d', '#bb3754', '#ed6925', '#fcbf49', '#fcffa4'];
            coords.forEach(pt => {
                if (pt && pt.length >= 3 && pt[0] != null && pt[1] != null) {
                    const intensity = pt[2] || 0.5;
                    const colorIdx = Math.min(Math.floor(intensity * colorScheme.length), colorScheme.length - 1);
                    L.circleMarker([pt[0], pt[1]], {
                        radius: 8 + intensity * 12,
                        fillColor: colorScheme[colorIdx],
                        color: colorScheme[colorIdx],
                        fillOpacity: intensity * 0.6,
                        weight: 0
                    }).addTo(group);
                }
            });
            return group;
        }
        const coords = (layer.coordinates || []).filter(pt => pt && pt[0] != null && pt[1] != null);
        const style = layer.style || {};
        return L.heatLayer(coords, {
            radius: style.radius || 35,
            blur: style.blur || 25,
            maxZoom: style.maxZoom || 17,
            minOpacity: style.minOpacity || 0.3,
            gradient: this._buildHeatGradient(style.color_scheme)
        });
    }

    _buildHeatGradient(colors) {
        if (!colors || !Array.isArray(colors)) return { 0.0: '#000004', 0.3: '#320a5e', 0.6: '#bb3754', 1.0: '#fcffa4' };
        const gradient = {};
        colors.forEach((color, i) => {
            gradient[i / (colors.length - 1)] = color;
        });
        return gradient;
    }

    /**
     * 水系要素成套矢量符号（统一蓝色）
     * @param {string} kind - spring/confluence/to_lake/to_sea
     * @param {string} color - 符号主色
     */
    _waterSymbolSvg(kind, color) {
        const c = color || "#0369a1";
        const light = "#e0f2fe";
        if (kind === "spring") {
            // 河源：水滴形
            return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
                '<path d="M16 4 C21 11, 26 14.5, 26 20 A10 10 0 0 1 6 20 C 6 14.5, 11 11, 16 4 Z" ' +
                'fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
                '<path d="M16 8 C19 12.5, 22 14.8, 22 18 A6 6 0 0 1 10 18 C 10 14.8, 13 12.5, 16 8 Z" ' +
                'fill="' + c + '" opacity="0.85"/></svg>';
        }
        if (kind === "to_lake" || kind === "to_sea") {
            // 入湖口/入海口：双波浪环
            return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
                '<circle cx="16" cy="16" r="14" fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
                '<path d="M7 13 Q9.8 10.5, 12.6 13 T 18.2 13 T 23.8 13" fill="none" stroke="' + c + '" ' +
                'stroke-width="2" stroke-linecap="round"/>' +
                '<path d="M7 19 Q9.8 16.5, 12.6 19 T 18.2 19 T 23.8 19" fill="none" stroke="' + c + '" ' +
                'stroke-width="1.5" stroke-linecap="round" opacity="0.7"/></svg>';
        }
        // 汇入口：Y形汇流符号（支流汇入主河，与水涯线在曲率最大处相交）
        return '<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">' +
            '<circle cx="16" cy="16" r="14" fill="' + light + '" stroke="' + c + '" stroke-width="2"/>' +
            '<path d="M16 6 L16 16 L8.5 21.5" fill="none" stroke="' + c + '" stroke-width="2.4" ' +
            'stroke-linecap="round" stroke-linejoin="round"/>' +
            '<path d="M16 16 L23.5 21.5" fill="none" stroke="' + c + '" stroke-width="2.4" ' +
            'stroke-linecap="round" stroke-linejoin="round"/>' +
            '<circle cx="16" cy="16" r="2.6" fill="' + c + '"/></svg>';
    }

    renderLayer(layerData) {
        if (!layerData || !layerData.type) return;
        // 载负量控制：按比例尺抽稀大图层要素（编辑模式不抽稀，避免保存丢要素）
        const _renderZoom = this.map ? this.map.getZoom() : 12;
        const _origData = layerData;
        layerData = this._applyLoadControl(layerData, _renderZoom);
        layerData._lodVisible = this._lodVisible(layerData, _renderZoom);
        layerData._lodCount = (layerData.coordinates || layerData.features || []).length;
        _origData._lodCount = layerData._lodCount;
        // 校验坐标数据是否存在且非空（支持coordinates/data/features三种数据源）
        if (!layerData.coordinates && !layerData.data && !layerData.features) {
            console.warn("[MapPanel] 图层缺少坐标数据，跳过:", layerData.name || layerData.id);
            return;
        }
        const style = layerData.style || {};
        let layer = null;
        // 辅助函数：验证单个坐标点 [lat, lng] 是否有效
        const isValidPoint = (pt) => Array.isArray(pt) && pt.length >= 2
            && pt[0] != null && pt[1] != null
            && !isNaN(parseFloat(pt[0])) && !isNaN(parseFloat(pt[1]));
        // 辅助函数：过滤坐标列表中的无效点
        const filterValidCoords = (coords) => {
            if (!Array.isArray(coords)) return [];
            return coords.filter(c => {
                if (Array.isArray(c) && c.length === 2 && !Array.isArray(c[0])) {
                    return isValidPoint(c);
                } else if (Array.isArray(c) && Array.isArray(c[0])) {
                    return isValidPoint(c[0]) || c.some(p => isValidPoint(p));
                }
                return false;
            });
        };
        // 预处理：带features数组的图层（专题地图的circle/polygon类型）
        if (layerData.features && Array.isArray(layerData.features) && layerData.features.length > 0) {
            const featGroup = L.layerGroup();
            layerData.features.forEach(feat => {
                if (!feat.coordinates) return;
                const featStyle = feat.style || style;
                if (feat.type === "polygon") {
                    const coords = filterValidCoords(
                        Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates]
                    );
                    if (coords.length > 0) {
                        // 行政区划图：面完全透明（兜底旧地图数据），露出瓦片底图
                        let fColor = featStyle.color || "#3388ff";
                        let fFill = featStyle.fillColor || featStyle.color || "#3388ff";
                        let fWeight = featStyle.weight || 1;
                        let fOpac = featStyle.opacity !== undefined ? featStyle.opacity : 0.5;
                        let fFillOpac = featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.4;
                        if (this.currentMapType === "administrative") {
                            fFillOpac = 0.2; fWeight = 0; fFill = "#f0f4f8";  // 极浅纹理：露出底图且不空心
                        }
                        const poly = L.polygon(coords, {
                            color: fColor, fillColor: fFill, weight: fWeight,
                            opacity: fOpac, fillOpacity: fFillOpac
                        });
                        // 悬浮交互：鼠标移入该区，边界高亮为红色加粗、区块微泛白，移出复原
                        if (this.currentMapType === "administrative") {
                            poly.on("mouseover", function() {
                                this.setStyle({ weight: 3, color: "#FF0000", fillOpacity: 0.12 });
                                this.bringToFront();
                            });
                            poly.on("mouseout", function() {
                                this.setStyle({ weight: fWeight, color: fColor, fillOpacity: fFillOpac });
                            });
                        }
                        poly.addTo(featGroup);
                    }
                } else if (feat.type === "point" || feat.type === "circle") {
                    if (isValidPoint(feat.coordinates)) {
                        L.circleMarker(
                            [parseFloat(feat.coordinates[0]), parseFloat(feat.coordinates[1])],
                            {
                                radius: featStyle.radius || 6,
                                color: featStyle.color || "#3388ff",
                                fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.7,
                                weight: featStyle.weight || 2
                            }
                        ).addTo(featGroup);
                    }
                }
            });
            layer = featGroup;
        } else {
        switch (layerData.type) {
            case "heatmap":
                layer = this.renderHeatmap(layerData);
                break;
            case "polyline":
            case "line":
                // 线图层 - 过滤无效坐标点
                {
                    const validCoords = filterValidCoords(layerData.coordinates);
                    if (validCoords.length === 0) {
                        console.warn("[MapPanel] 线图层无有效坐标，跳过:", layerData.name);
                        return;
                    }
                    const lineProps = layerData.properties || [];
                    let lineStyle = {
                        color: style.color || "#3388ff",
                        weight: style.weight || 3,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        dashArray: style.dashArray || null
                    };
                    // 行政区划图边界样式兜底（兼容旧地图数据）：市界红粗实线/区县界灰虚线/周边县界灰细虚线
                    if (this.currentMapType === "administrative") {
                        const _ln = layerData.name || "";
                        if (/市域边界|地级市界|市界/.test(_ln)) lineStyle = { color: "#E03131", weight: 3, opacity: 0.9, dashArray: null };
                        else if (/区县界/.test(_ln)) lineStyle = { color: "#8A8A8A", weight: 1.2, opacity: 0.9, dashArray: "6,4" };
                        else if (/周边县界/.test(_ln)) lineStyle = { color: "#999999", weight: 0.9, opacity: 0.85, dashArray: "1,4" };
                        else if (/省界/.test(_ln)) lineStyle = { color: "#000000", weight: 1.2, opacity: 0.9, dashArray: "1,4" };
                    }
                    // 武汉市域边界：叠加发光晕影（底层宽半透明红线 + 主线）
                    const _isMainBound = this.currentMapType === "administrative"
                        && /市域边界|地级市界|市界/.test(layerData.name || "");
                    // 多条线段时绑定弹窗显示道路名称
                    if (validCoords.length === 1) {
                        if (_isMainBound) {
                            const _gg = L.layerGroup();
                            L.polyline(validCoords[0], { color: "#E03131", weight: 8, opacity: 0.12, dashArray: null }).addTo(_gg);
                            L.polyline(validCoords[0], lineStyle).addTo(_gg);
                            layer = _gg;
                        } else {
                            layer = L.polyline(validCoords[0], lineStyle);
                        }
                    } else {
                        const group = L.layerGroup();
                        validCoords.forEach((lineCoords, idx) => {
                            if (_isMainBound) {
                                L.polyline(lineCoords, { color: "#E03131", weight: 8, opacity: 0.12, dashArray: null }).addTo(group);
                            }
                            const line = L.polyline(lineCoords, lineStyle);
                            const prop = lineProps[idx] || {};
                            if (prop.name || prop.subtype) {
                                let popupHtml = '<div style="font-size:13px;"><strong>' +
                                    Utils.escapeHtml(prop.name || layerData.name || '') + '</strong>';
                                if (prop.subtype) {
                                    const roadTypeLabels = {
                                        'motorway': '高速公路', 'trunk': '主干道', 'primary': '主要道路',
                                        'secondary': '次干道', 'tertiary': '支路',
                                        'residential': '社区道路', 'service': '服务道路',
                                        'rail': '铁路', 'subway': '地铁', 'light_rail': '轻轨',
                                        'high_speed': '高速铁路',
                                        'river': '河流', 'stream': '溪流', 'canal': '运河',
                                    };
                                    const label = roadTypeLabels[prop.subtype] || prop.subtype;
                                    popupHtml += '<br><span style="color:#666;">等级: ' + Utils.escapeHtml(label) + '</span>';
                                }
                                popupHtml += '</div>';
                                line.bindPopup(popupHtml);
                            }
                            line.addTo(group);
                        });
                        layer = group;
                    }
                }
                break;
            case "textLabel":
            case "label":
                // 文字标注图层（行政区划/水系注记：支持沿要素方向旋转与避让）
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 文字标注图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const group = L.layerGroup();
                    const props = layerData.properties || [];
                    const fontSize = style.fontSize || 13;
                    // 注记数量上限（载负量控制）：单图层最多渲染300个标签，避免渲染撑爆
                    const MAX_LABELS = 300;
                    let _placedCount = 0;
                    const placed = this._labelPlaced;  // 全局避让：跨图层共享，同一名称只显示一次
                    const getFontSize = (idx) => {
                        const p = props[idx] || {};
                        return (p && p.fontSize) ? p.fontSize : fontSize;
                    };
                    coords.forEach((pt, idx) => {
                        if (_placedCount >= MAX_LABELS) return;
                        if (!isValidPoint(pt)) return;
                        const prop = props[idx] || {};
                        const label = prop.name || layerData.name || "";
                        if (!label) return;
                        // 过滤非地名注记：纯英文/数字的长文本（歌词等污染）不渲染
                        if (/^[A-Za-z0-9\s.,'\"-]{15,}$/.test(label)) return;
                        // 名称去重：同一地理名称整图只渲染一处标签
                        if (this._labelNames && this._labelNames.has(label)) return;
                        if (!this._labelNames) this._labelNames = new Set();
                        this._labelNames.add(label);
                        const labelColor = style.color || "#1a1a1a";
                        // 字号随缩放级别自适应：基准zoom=12，每+1级字号×1.1，限制0.85~1.6倍且最小11px
                        const zoomFactor = Math.pow(1.1, this.map.getZoom() - 12);
                        const itemFontSize = Math.max(11, Math.round(getFontSize(idx) * Math.min(1.6, Math.max(0.85, zoomFactor))));
                        let rot = (prop.rotation !== undefined) ? prop.rotation : (style.rotation || 0);
                        // 字头朝上：旋转角归一化到[-90,90]，避免文字倒置
                        rot = ((rot + 90) % 180 + 180) % 180 - 90;
                        const labelFont = style.font || "normal";
                        let fontCss = "";
                        if (labelFont === "black") fontCss = "font-family:'SimHei','Microsoft YaHei',sans-serif;font-weight:700;";
                        else if (labelFont === "song") fontCss = "font-family:'SimSun','宋体','NSimSun',serif;";
                        else if (labelFont === "bold") fontCss = "font-weight:700;";
                        else if (labelFont === "italic") fontCss = "font-style:italic;";
                        const isCentered = style.center === true;
                        const cp = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                        // 文本碰撞检测（防重叠）：中心区县名注记与红点/已放置注记冲突时，
                        // 先缩小字号（最小9px），仍冲突再轻微错开(右下4px)，保证可读
                        let labelFs = itemFontSize;
                        let labelW = label.length * labelFs * 0.95 + 16;
                        let labelH = labelFs + 10;
                        let ox = 0, oy = 0;
                        if (isCentered) {
                            const hit = (w, h) => {
                                const h1 = placed.some(p2 =>
                                    !(cp.x + ox + w < p2.x || cp.x + ox > p2.x + p2.w ||
                                      cp.y + oy + h < p2.y || cp.y + oy > p2.y + p2.h));
                                const h2 = (this._poiMarkers || []).some(pm =>
                                    !(cp.x + ox + w < pm.x || cp.x + ox > pm.x + pm.w ||
                                      cp.y + oy + h < pm.y || cp.y + oy > pm.y + pm.h));
                                return h1 || h2;
                            };
                            while (labelFs > 9 && hit(labelW, labelH)) {
                                labelFs -= 1;
                                labelW = label.length * labelFs * 0.95 + 16;
                                labelH = labelFs + 10;
                            }
                            if (hit(labelW, labelH)) { ox = 4; oy = 4; }
                            placed.push({ x: cp.x + ox, y: cp.y + oy, w: labelW, h: labelH });
                            _placedCount += 1;
                        } else {
                            for (let attempt = 0; attempt < 4; attempt++) {
                                const cand = { x: cp.x + ox, y: cp.y + oy, w: labelW, h: labelH };
                                const h1 = placed.some(p2 =>
                                    !(cand.x + cand.w < p2.x || cand.x > p2.x + p2.w ||
                                      cand.y + cand.h < p2.y || cand.y > p2.y + p2.h));
                                if (!h1) { placed.push(cand); _placedCount += 1; break; }
                                if (attempt === 0) { ox += labelW * 0.7; }
                                else if (attempt === 1) { ox = 0; oy += labelH * 1.3; }
                                else if (attempt === 2) { ox = -labelW * 0.7; oy = 0; }
                                else { ox = 0; oy = 0; placed.push(cand); }
                            }
                        }
                        const icon = L.divIcon({
                            className: "map-text-label",
                            html: '<span class="map-text-label-box" style="' + fontCss + 'font-size:' + labelFs +
                                "px;border-color:" + labelColor + ";color:" + labelColor +
                                ";transform:translate(" + ox + "px," + oy + "px) rotate(" + rot + "deg);\">" +
                                Utils.escapeHtml(label) + "</span>",
                            iconSize: isCentered ? [labelW, labelH] : null,
                            iconAnchor: isCentered ? [labelW / 2, labelH / 2] : [0, 0]
                        });
                        const m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                        m.bindPopup('<div style="font-size:13px;"><strong>' + Utils.escapeHtml(label) + "</strong></div>");
                        m.addTo(group);
                    });
                    layer = group;
                }
                break;
            case "circleMarker":
                // 圆形/象形标记图层（POI按分类使用整套象形符号）
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 圆形标记图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const group = L.layerGroup();
                    const props = layerData.properties || [];
                    const usePictoIcon = !!(style.icon);
                    const zf = this._symbolZoomFactor();
                    const badgeSize = Math.max(26, Math.round((style.radius || 6) * 4.2 * zf));
                    coords.forEach((pt, idx) => {
                        if (isValidPoint(pt)) {
                            // 符号防重叠：与已渲染符号屏幕距离过近时缩小尺寸（POI防堆积）
                            let _dupFactor = 1;
                            try {
                                const _sp = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                                if (this._poiMarkers && this._poiMarkers.length) {
                                    for (const pm of this._poiMarkers) {
                                        if (Math.abs(pm.x - _sp.x) < pm.w * 0.85 && Math.abs(pm.y - _sp.y) < pm.h * 0.85) {
                                            _dupFactor = 0.55;
                                            break;
                                        }
                                    }
                                }
                            } catch (e) {}
                            const _effSize = Math.max(14, Math.round(badgeSize * _dupFactor));
                            let m;
                            if (usePictoIcon) {
                                const waterKind = (style.kind === "spring" || style.kind === "confluence" || style.kind === "to_lake" || style.kind === "to_sea") ? style.kind : null;
                                // 市级行政中心：红色五角星★（规范三-1，正红#D82828）
                                if (style.kind === "admin_city") {
                                    const asize = Math.max(26, Math.round((style.radius || 8) * 3.4 * zf));
                                    const icon = L.divIcon({
                                        className: "admin-city-symbol",
                                        html: '<span class="admin-city-star" style="color:' + (style.color || "#D82828") + ';font-size:' + asize + 'px;">★</span>',
                                        iconSize: [asize, asize],
                                        iconAnchor: [asize / 2, asize / 2],
                                        popupAnchor: [0, -asize / 2]
                                    });
                                    m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                } else if (waterKind) {
                                    const wsvg = this._waterSymbolSvg(waterKind, style.color || "#0369a1");
                                    const wsize = Math.max(30, Math.round((style.radius || 6) * 5));
                                    const icon = L.divIcon({
                                        className: "poi-marker water-symbol",
                                        html: wsvg,
                                        iconSize: [wsize, wsize],
                                        iconAnchor: [wsize / 2, wsize / 2],
                                        popupAnchor: [0, -wsize / 2]
                                    });
                                    m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                } else {
                                // 象形符号徽章：白色圆底 + 分类色环 + 成套矢量图标(iconClass)/emoji（百度/高德风格）
                                const iconInner = style.iconClass
                                    ? '<i class="fa-solid ' + style.iconClass + '"></i>'
                                    : (style.icon || "\ud83d\udccd");
                                const icon = L.divIcon({
                                    className: "poi-marker",
                                    html: '<span class="poi-marker-badge" style="border-color:' +
                                        (style.color || "#f59e0b") + ";width:" + _effSize + "px;height:" + _effSize +
                                        "px;font-size:" + Math.round(_effSize * 0.5) + 'px;">' +
                                        iconInner + "</span>",
                                    iconSize: [_effSize, _effSize],
                                    iconAnchor: [_effSize / 2, _effSize / 2],
                                    popupAnchor: [0, -_effSize / 2]
                                });
                                m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])], { icon: icon });
                                }
                            } else {
                                m = L.circleMarker([parseFloat(pt[0]), parseFloat(pt[1])], {
                                    radius: (style.radius || 6) * zf,
                                    color: style.color || "#f59e0b",
                                    fillColor: style.fillColor || style.color || "#f59e0b",
                                    fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.7,
                                    weight: style.weight || 2
                                });
                            }
                            const prop = props[idx] || {};
                            const poiName = prop.name || layerData.name || "";
                            // 记录符号屏幕位置（供区名注记碰撞检测防重叠）
                            try {
                                if (!this._poiMarkers) this._poiMarkers = [];
                                const _spt = this.map.latLngToContainerPoint([parseFloat(pt[0]), parseFloat(pt[1])]);
                                this._poiMarkers.push({ x: _spt.x, y: _spt.y, w: _effSize, h: _effSize, name: poiName });
                            } catch (e) {}
                            const popupHtml = '<div style="font-size:13px;min-width:170px;">' +
                                (style.icon ? '<span style="font-size:18px;">' + style.icon + '</span> ' : '') +
                                '<strong>' + Utils.escapeHtml(poiName) + '</strong>' +
                                (prop.category ? '<br><span style="color:#666;">类型: ' + Utils.escapeHtml(prop.category) + '</span>' : '') +
                                (prop.target ? '<br><span style="color:#0369a1;">汇入: ' + Utils.escapeHtml(prop.target) + '</span>' : '') +
                                (prop.kind === "to_lake" ? '<br><span style="color:#0369a1;">河流入湖口</span>' : '') +
                                (prop.kind === "spring" ? '<br><span style="color:#0369a1;">河源</span>' : '') +
                                (poiName ? '<br><button class="wiki-btn" type="button">📖 百科介绍</button>' : '') +
                                '</div>';
                            m.bindPopup(popupHtml);
                            // 悬停显示名称（重点地标/行政中心/水系符号等）
                            if (poiName) {
                                m.bindTooltip(poiName, { sticky: true, direction: "top", opacity: 0.92 });
                            }
                            if (poiName) {
                                // 点击"百科介绍"：从后端加载建筑简介与图片（点击后显示）
                                m.on("popupopen", (e) => {
                                    const box = e.popup.getElement();
                                    const btn = box ? box.querySelector(".wiki-btn") : null;
                                    if (!btn || btn.dataset.bound) return;
                                    btn.dataset.bound = "1";
                                    btn.addEventListener("click", async () => {
                                        btn.innerHTML = "⏳ 加载百科...";
                                        btn.disabled = true;
                                        try {
                                            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/wiki?name=" + encodeURIComponent(poiName));
                                            const json = await resp.json();
                                            const d = json.data || {};
                                            const holder = document.createElement("div");
                                            holder.className = "wiki-box";
                                            let wikiHtml = "";
                                            if (d.image) {
                                                wikiHtml += "<img class=\"wiki-img\" src=\"" + d.image +
                                                    "\" onerror=\"this.style.display='none'\" alt=\"百科图片\">";
                                            }
                                            wikiHtml += "<div class=\"wiki-text\">" + Utils.escapeHtml(d.extract || "暂无百科简介") + "</div>";
                                            if (d.source) wikiHtml += "<div class=\"wiki-src\">来源：" + Utils.escapeHtml(d.source) + "</div>";
                                            holder.innerHTML = wikiHtml;
                                            btn.replaceWith(holder);
                                        } catch (err) {
                                            btn.innerHTML = "百科加载失败";
                                        }
                                    });
                                });
                            }
                            m.addTo(group);
                        }
                    });
                    layer = group;
                }
                break;
            case "marker":
            case "point":
                // 点标记图层 - 支持多个标记点
                {
                    const coords = layerData.coordinates;
                    if (!Array.isArray(coords) || coords.length === 0) {
                        console.warn("[MapPanel] 点图层无坐标，跳过:", layerData.name);
                        return;
                    }
                    const props = layerData.properties || [];
                    // 单个点用L.marker，多个点用LayerGroup
                    if (coords.length === 1) {
                        const latlng = Array.isArray(coords[0]) ? coords[0] : coords;
                        if (!isValidPoint(latlng)) return;
                        layer = L.marker([parseFloat(latlng[0]), parseFloat(latlng[1])]);
                        const prop = props[0] || {};
                        if (prop.name || layerData.popup) {
                            layer.bindPopup(layerData.popup || '<strong>' + Utils.escapeHtml(prop.name || '') + '</strong>');
                        }
                    } else {
                        const group = L.layerGroup();
                        coords.forEach((pt, idx) => {
                            if (isValidPoint(pt)) {
                                const m = L.marker([parseFloat(pt[0]), parseFloat(pt[1])]);
                                const prop = props[idx] || {};
                                if (prop.name) {
                                    m.bindPopup('<div style="font-size:13px;"><strong>' + Utils.escapeHtml(prop.name) + '</strong></div>');
                                }
                                m.addTo(group);
                            }
                        });
                        layer = group;
                    }
                }
                break;
            case "polygon":
            case "area":
                // 多边形图层 - 支持多个独立多边形和fillColor填充
                {
                    const validCoords = filterValidCoords(layerData.coordinates);
                    if (validCoords.length === 0) {
                        console.warn("[MapPanel] 多边形图层无有效坐标，跳过:", layerData.name);
                        return;
                    }
                    const polyStyle = {
                        color: style.color || "#3388ff",
                        fillColor: style.fillColor || style.color || "#3388ff",
                        weight: style.weight || 2,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.3,
                        dashArray: style.dashArray || null
                    };
                    const props = layerData.properties || [];
                    const buildPolyPopup = (prop, layerName) => {
                        let html = '<div style="font-size:13px;min-width:120px;">';
                        html += '<strong>' + Utils.escapeHtml(prop.name || layerName || '') + '</strong>';
                        if (prop.subtype) {
                            const subtypeLabels = {
                                'residential': '住宅', 'apartments': '公寓', 'commercial': '商业',
                                'industrial': '工业', 'public': '公共', 'school': '学校',
                                'university': '大学', 'hospital': '医院', 'religious': '宗教',
                                'parking': '停车', 'warehouse': '仓储', 'default': '其他',
                                'park': '公园', 'garden': '花园', 'forest': '森林',
                                'grass': '草地', 'meadow': '草甸',
                            };
                            const label = subtypeLabels[prop.subtype] || prop.subtype;
                            html += '<br><span style="color:#666;">类型: ' + Utils.escapeHtml(label) + '</span>';
                        }
                        if (prop.category) {
                            html += '<br><span style="color:#666;">分类: ' + Utils.escapeHtml(prop.category) + '</span>';
                        }
                        html += '</div>';
                        return html;
                    };
                    if (validCoords.length === 1) {
                        layer = L.polygon(validCoords[0], polyStyle);
                        const prop = props[0] || {};
                        if (prop.name || prop.subtype) {
                            layer.bindPopup(buildPolyPopup(prop, layerData.name));
                        }
                    } else {
                        // 多个独立多边形
                        const group = L.layerGroup();
                        validCoords.forEach((polyCoords, idx) => {
                            const poly = L.polygon(polyCoords, polyStyle);
                            const prop = props[idx] || {};
                            if (prop.name || prop.subtype) {
                                poly.bindPopup(buildPolyPopup(prop, layerData.name));
                            }
                            poly.addTo(group);
                        });
                        layer = group;
                    }
                }
                break;
            case "circle":
                // 圆形图层
                {
                    const coords = layerData.coordinates;
                    if (!isValidPoint(coords)) {
                        console.warn("[MapPanel] 圆形图层坐标无效，跳过:", layerData.name);
                        return;
                    }
                    layer = L.circle([parseFloat(coords[0]), parseFloat(coords[1])], {
                        radius: layerData.radius || 500,
                        color: style.color || "#3388ff",
                        weight: style.weight || 2,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.2
                    });
                }
                break;
            case "geojson":
                // GeoJSON图层
                layer = L.geoJSON(layerData.coordinates || layerData.data, {
                    style: () => ({
                        color: style.color || "#3388ff",
                        weight: style.weight || 2,
                        opacity: style.opacity !== undefined ? style.opacity : 1,
                        fillOpacity: style.fillOpacity !== undefined ? style.fillOpacity : 0.2
                    }),
                    pointToLayer: (feature, latlng) => {
                        return L.marker(latlng);
                    }
                });
                break;
            default:
                // 处理带features数组的图层（专题地图）
                if (layerData.features && Array.isArray(layerData.features) && layerData.features.length > 0) {
                    const group = L.layerGroup();
                    layerData.features.forEach(feat => {
                        if (!feat.coordinates) return;
                        const featStyle = feat.style || style;
                        if (feat.type === "polygon") {
                            const coords = filterValidCoords(
                                Array.isArray(feat.coordinates[0]) ? feat.coordinates : [feat.coordinates]
                            );
                            if (coords.length > 0) {
                                L.polygon(coords, {
                                    color: featStyle.color || "#3388ff",
                                    fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                    weight: featStyle.weight || 1,
                                    opacity: featStyle.opacity !== undefined ? featStyle.opacity : 0.5,
                                    fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.4
                                }).addTo(group);
                            }
                        } else if (feat.type === "point" || feat.type === "circle") {
                            if (isValidPoint(feat.coordinates)) {
                                L.circleMarker(
                                    [parseFloat(feat.coordinates[0]), parseFloat(feat.coordinates[1])],
                                    {
                                        radius: featStyle.radius || 6,
                                        color: featStyle.color || "#3388ff",
                                        fillColor: featStyle.fillColor || featStyle.color || "#3388ff",
                                        fillOpacity: featStyle.fillOpacity !== undefined ? featStyle.fillOpacity : 0.7,
                                        weight: featStyle.weight || 2
                                    }
                                ).addTo(group);
                            }
                        }
                    });
                    layer = group;
                } else {
                    console.warn("未知图层类型:", layerData.type);
                    return;
                }
         }
        } // end of else (features preprocessing)
        if (!layer) return;
        // 添加弹窗（如果有）
        if (layerData.popup && layerData.type !== "marker") {
            layer.bindPopup(layerData.popup);
        }
        // 添加tooltip
        if (layerData.name) {
            layer.bindTooltip(layerData.name, { sticky: true });
        }
        // 图层 LOD（层级细节控制）：路网/水系/注记/POI 按缩放分级
        const _lodShown = layerData._lodVisible;
        // 添加到地图
        if (_lodShown) layer.addTo(this.map);
        // 存储图层引用
        this.layerGroups[layerData.id] = {
            layer: layer,
            data: _origData,       // 始终保存全量数据（编辑/保存用），渲染层为抽稀副本
            visible: _lodShown
        };
        // 编辑模式下为新渲染要素挂载编辑元数据
        if (this.editMode) this._attachEditMetadata(layerData.id, layer);
    }

    /**
     * 清除所有图层
     */
    clearAllLayers() {
        Object.values(this.layerGroups).forEach(item => {
            if (item.layer) {
                this.map.removeLayer(item.layer);
            }
        });
        this.layerGroups = {};
        // 清除自动检测的桥梁/渡口符号
        if (this._bridgeGroup) {
            this.map.removeLayer(this._bridgeGroup);
            this._bridgeGroup = null;
        }
        // 清除图面整饰（常驻图例框/编制说明）
        const miniLegendEl = document.getElementById("map-mini-legend");
        if (miniLegendEl) miniLegendEl.classList.add("hidden");
        const attributionEl = document.getElementById("map-attribution");
        if (attributionEl) attributionEl.classList.add("hidden");
        // 清除质量检测面板
        const qualityPanel = document.getElementById("map-quality-panel");
        if (qualityPanel) qualityPanel.classList.add("hidden");
        if (this._qualityMarker) { this.map.removeLayer(this._qualityMarker); this._qualityMarker = null; }
        // 清除图例
        this.legendData = null;
        const legendPanel = document.getElementById("map-legend-panel");
        const legendBtn = document.getElementById("map-legend-btn");
        if (legendPanel) legendPanel.classList.add("hidden");
        if (legendBtn) { legendBtn.classList.remove("active"); legendBtn.style.display = "none"; }
        this.updateLayerPanel();
    }

    /**
     * 初始化图例按钮与面板
     */
    initLegendPanel() {
        const btn = document.getElementById("map-legend-btn");
        const panel = document.getElementById("map-legend-panel");
        const closeBtn = panel ? panel.querySelector(".legend-panel-close") : null;
        const pinBtn = document.getElementById("legend-pin-btn");
        const searchInput = document.getElementById("legend-search-input");
        this.legendPinned = false;
        if (btn && panel) {
            btn.addEventListener("click", () => {
                const willHide = !this.legendPinned && !panel.classList.contains("hidden");
                if (willHide) {
                    panel.classList.add("hidden");
                    btn.classList.remove("active");
                } else {
                    panel.classList.remove("hidden");
                    btn.classList.add("active");
                    this.renderLegendPanel();
                }
            });
        }
        if (pinBtn && panel) {
            pinBtn.addEventListener("click", () => {
                this.legendPinned = !this.legendPinned;
                pinBtn.classList.toggle("active", this.legendPinned);
                pinBtn.title = this.legendPinned ? "取消固定" : "固定图例";
            });
        }
        if (closeBtn && panel) {
            closeBtn.addEventListener("click", () => {
                panel.classList.add("hidden");
                if (btn) btn.classList.remove("active");
                this.legendPinned = false;
                if (pinBtn) pinBtn.classList.remove("active");
            });
        }
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                this.legendSearch = searchInput.value.trim();
                this.renderLegendPanel();
            });
        }
        // 右下角图例折叠抽屉：点击标题栏/折叠按钮切换展开/折叠，localStorage记忆状态
        this._initMiniLegendFold();
    }

    /** 初始化右下角图例折叠抽屉（标题栏 + ▼/▶ 按钮） */
    _initMiniLegendFold() {
        const legend = document.getElementById("map-mini-legend");
        const header = document.getElementById("mini-legend-header");
        const foldBtn = document.getElementById("mini-legend-fold");
        if (!legend || !header) return;
        const toggle = () => {
            const collapsed = legend.classList.toggle("collapsed");
            if (foldBtn) foldBtn.textContent = collapsed ? "▶" : "▼";
            try { localStorage.setItem("carto_mini_legend_collapsed", collapsed ? "1" : "0"); } catch (e) {}
        };
        header.addEventListener("click", toggle);
        if (foldBtn) foldBtn.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
    }

    /** 应用图例折叠状态（localStorage记忆；无记录时默认展开） */
    _applyMiniLegendState() {
        const legend = document.getElementById("map-mini-legend");
        const foldBtn = document.getElementById("mini-legend-fold");
        if (!legend) return;
        let collapsed = false;
        try { collapsed = localStorage.getItem("carto_mini_legend_collapsed") === "1"; } catch (e) {}
        legend.classList.toggle("collapsed", collapsed);
        if (foldBtn) foldBtn.textContent = collapsed ? "▶" : "▼";
    }

    /**
     * 渲染整套图例（按钮 + 分组面板 + 搜索 + 图层联动）
     * @param {object} legendData - 图例数据 {title, items: [...]}
     */
    renderLegend(legendData) {
        this.legendData = legendData || null;
        this.legendActiveGroup = "全部";
        this.legendSearch = "";
        const btn = document.getElementById("map-legend-btn");
        const searchInput = document.getElementById("legend-search-input");
        if (searchInput) searchInput.value = "";
        if (btn) {
            btn.style.display = (legendData && legendData.items && legendData.items.length) ? "" : "none";
        }
        if (legendData) this.renderLegendPanel();
    }

    /**
     * 渲染图例面板内容（分组标签 + 条目列表）
     */
    renderLegendPanel() {
        const panel = document.getElementById("map-legend-panel");
        const tabsEl = document.getElementById("legend-group-tabs");
        const itemsEl = document.getElementById("legend-items");
        if (!panel || !tabsEl || !itemsEl || !this.legendData) return;
        const items = this.legendData.items || [];
        const groups = ["全部"];
        items.forEach(it => {
            const g = it.group || "其他";
            if (groups.indexOf(g) < 0) groups.push(g);
        });
        tabsEl.innerHTML = "";
        groups.forEach(g => {
            const count = g === "全部" ? items.length : items.filter(it => (it.group || "其他") === g).length;
            const tab = document.createElement("button");
            tab.className = "legend-tab" + (g === this.legendActiveGroup ? " active" : "");
            tab.innerHTML = Utils.escapeHtml(g) + '<span class="legend-tab-count">' + count + "</span>";
            tab.addEventListener("click", () => { this.legendActiveGroup = g; this.renderLegendPanel(); });
            tabsEl.appendChild(tab);
        });
        const keyword = (this.legendSearch || "").trim().toLowerCase();
        const filtered = items.filter(it => {
            const inGroup = this.legendActiveGroup === "全部" || (it.group || "其他") === this.legendActiveGroup;
            const label = (it.label || "").toLowerCase();
            const group = (it.group || "").toLowerCase();
            return inGroup && (!keyword || label.indexOf(keyword) >= 0 || group.indexOf(keyword) >= 0);
        });
        itemsEl.innerHTML = "";
        if (filtered.length === 0) {
            itemsEl.innerHTML = '<div style="color:#94a3b8;font-size:12px;padding:14px;">没有匹配的图例项</div>';
            return;
        }
        filtered.forEach(item => {
            const row = document.createElement("div");
            const matched = this._findLayersByLabel(item.label);
            const anyVisible = matched.some(id => this.layerGroups[id] && this.layerGroups[id].visible);
            row.className = "legend-item" + (matched.length > 0 && !anyVisible ? " legend-item-off" : "");
            row.innerHTML =
                '<span class="legend-symbol">' + this._legendSymbolHtml(item) + "</span>" +
                '<span class="legend-item-label">' + Utils.escapeHtml(item.label || "") + "</span>" +
                '<span class="legend-eye">' + (matched.length > 0 ? (anyVisible ? "\ud83d\udc41" : "\ud83d\udeab") : "") + "</span>";
            if (matched.length > 0) {
                row.title = "点击" + (anyVisible ? "隐藏" : "显示") + "对应图层";
                row.addEventListener("click", () => {
                    matched.forEach(id => { if (this.layerGroups[id]) this.toggleLayer(id, !anyVisible); });
                    this.renderLegendPanel();
                });
            } else {
                row.style.cursor = "default";
            }
            itemsEl.appendChild(row);
        });
    }

    /**
     * 图例条目符号HTML
     */
    _legendSymbolHtml(item) {
        if (item.type === "line") {
            const dash = item.dashArray
                ? "border-top:2px dashed " + (item.color || "#333") + ";"
                : "background:" + (item.color || "#333") + ";";
            const h = Math.max(2, Math.min(item.weight || 3, 6));
            return '<span style="display:inline-block;width:24px;height:' + h + "px;" + dash + ';border-radius:1px;"></span>';
        }
        if (item.type === "polygon") {
            return '<span style="display:inline-block;width:16px;height:16px;background:' +
                (item.fillColor || item.color || "#ccc") + ";border:1px solid " +
                (item.color || "#999") + ";border-radius:2px;opacity:" + (item.fillOpacity || 0.5) + ';"></span>';
        }
        if (item.iconClass) {
            return '<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;color:' +
                (item.color || "#0369a1") + ';font-size:17px;"><i class="fa-solid ' + item.iconClass + '"></i></span>';
        }
        if (item.icon) {
            return '<span style="font-size:17px;line-height:1;">' + item.icon + "</span>";
        }
        return '<span style="display:inline-block;width:13px;height:13px;background:' +
            (item.color || "#f59e0b") + ';border-radius:50%;border:1px solid rgba(0,0,0,0.2);"></span>';
    }

    /**
     * 根据图例标签匹配对应图层（忽略外层/内层后缀）
     */
    _findLayersByLabel(label) {
        if (!label) return [];
        const base = String(label).replace(/\(外层\)|\(内层\)/g, "").trim();
        return Object.keys(this.layerGroups).filter(id => {
            const name = (this.layerGroups[id].data.name || "").replace(/\(外层\)|\(内层\)/g, "").trim();
            return name === base || name === label;
        });
    }

    /**
     * 自定义标注工具（点击地图放置标注点，答辩演示：标注赏樱点/卫生间等）
     */
    initMarkerTool() {
        const btn = document.getElementById("toolbar-marker");
        if (!btn) return;
        btn.addEventListener("click", () => {
            this.markerMode = !this.markerMode;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = this.markerMode ? "crosshair" : "";
            if (this.markerMode) {
                Utils.showToast("标注模式：请在地图上点击放置标注点", "info");
            }
        });
    }

    updateMarkerBtn() {
        const btn = document.getElementById("toolbar-marker");
        if (btn) btn.classList.toggle("active", this.markerMode);
    }

    /**
     * 标准分段比例尺（黑白交替分段条 + km/m 标注）
     */
    /**
     * 计算当前画面比例尺（整个画面宽度对应的比例尺，随缩放实时更新）
     * @returns {{denom:number, meters:number, label:string}}
     */
    /** 圆整到 1/2/5×10^n 的"整"数值 */
    _niceScale(m) {
        if (m <= 0) return 200000;
        const pow = Math.pow(10, Math.floor(Math.log10(m)));
        const n = m / pow;
        if (n <= 1) return pow;
        if (n <= 2) return 2 * pow;
        if (n <= 5) return 5 * pow;
        return 10 * pow;
    }

    /**
     * 计算比例尺数据：数字比例尺与线段比例尺严格一致。
     * 以"画面每像素对应实地距离"为基准选择主分划总长(meters)，
     * 再按比例尺条宽度反推数字比例尺分母(denom)，保证 1:xxx 与条上 0~xxxkm 完全匹配。
     * @param {number} barW - 比例尺条宽度(px)，与CSS一致
     */
    _computeScaleData(barW) {
        const size = this.map.getSize();
        const y = size.y / 2;
        const maxMeters = size.x > 0 ? this.map.distance(
            this.map.containerPointToLatLng([0, y]),
            this.map.containerPointToLatLng([size.x, y])
        ) : 0;
        const mPerPx = size.x > 0 ? maxMeters / size.x : 0;
        // 数字比例尺：画面1px对应mPerPx米 → 分母 = mPerPx / 0.0002646(96dpi时1px=0.2646mm)。
        // 直接由画面真实比例换算，不再被线段取整反推，保证数字与实际图面严格一致。
        const _rawDenom = mPerPx > 0 ? Math.max(1000, mPerPx / 0.0002646) : 0;
        // 取整粒度自适应：小分母(大比例尺)取整到100，大分母取整到1000，保证精度
        const _step = _rawDenom < 50000 ? 100 : 1000;
        const denom = _rawDenom ? Math.round(_rawDenom / _step) * _step : 0;
        // 线段比例尺：整条barW px表示 barW*mPerPx 米（与画面比例严格一致）；
        // 主分划(4段)总长精确为 barW*4/5*mPerPx，仅末端标签按制图惯例取整。
        const meters = barW * (4 / 5) * mPerPx;
        const labelMeters = this._niceScale(meters);
        return { denom, meters, label: labelMeters >= 1000 ? (labelMeters / 1000) + " km" : labelMeters + " m" };
    }

    /** 更新右下角比例尺控件（非行政区划图使用） */
    _updateScaleControl() {
        if (!this.scaleControl) return;
        const d = this._computeScaleData(180);
        const c = this.scaleControl._container;
        if (!c) return;
        // 数字比例尺：直接以 1:xxx 形式显示（取代线段比例尺条）
        const num = c.querySelector(".map-scale-num");
        if (num) num.textContent = d.denom ? "1:" + d.denom.toLocaleString("en-US").replace(/,/g, " ") : "1:1 440 000";
    }

    /** 更新图例框内比例尺（行政区划图：数字+线段比例尺随缩放实时变化） */
    _updateMiniScale() {
        const num = document.getElementById("mini-scale-num");
        const bar = document.getElementById("mini-scale-bar");
        const labels = document.getElementById("mini-scale-labels");
        if (!num || !bar || !labels) return;
        const d = this._computeScaleData(140);
        num.textContent = d.denom ? "1:" + d.denom.toLocaleString("en-US").replace(/,/g, " ") : "1:1 440 000";
        bar.innerHTML = "";
        for (let i = 0; i < 5; i++) {
            const seg = document.createElement("span");
            seg.className = "map-scale-seg" + (i === 0 ? " sub" : (i % 2 === 1 ? " dark" : ""));
            bar.appendChild(seg);
        }
        labels.innerHTML = "<span></span><span>0</span><span></span><span></span><span>" + d.label + "</span>";
    }

    /** 同步工具栏比例尺输入框（输入框未被聚焦时回显当前比例尺） */
    _syncScaleInput(denom) {
        const input = document.getElementById("map-scale-input");
        if (!input || document.activeElement === input) return;
        if (denom) input.value = "1:" + denom.toLocaleString("en-US").replace(/,/g, " ");
    }

    /** 自定义比例尺：输入 1:xxx 回车后跳转到对应缩放级别 */
    _initScaleSetter() {
        const input = document.getElementById("map-scale-input");
        if (!input) return;
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const digits = String(input.value || "").replace(/[^0-9]/g, "");
                const target = parseInt(digits, 10);
                if (!target || target < 1000) {
                    Utils.showToast("请输入有效比例尺，如 1:100000", "warning");
                    return;
                }
                const z = this._zoomForScale(target);
                // 失焦让回显显示跳转后的实际比例尺（zoom为整数，实际值可能与输入略有出入）
                input.blur();
                const _d = this._computeScaleData(180);
                const _actual = (_d && _d.denom) ? _d.denom : target;
                Utils.showToast("已跳转，当前实际比例尺 1:" + _actual.toLocaleString("en-US").replace(/,/g, " "),
                                "info", 2200);
            }
        });
    }

    /**
     * 根据目标比例尺分母计算目标缩放级别（公式法，一次到位）
     * 原理：mPerPx ∝ 2^(-zoom)，由当前mPerPx与目标mPerPx比值直接算出zoom差
     */
    _zoomForScale(targetDenom) {
        const size = this.map.getSize();
        const y = size.y / 2;
        const mPerPxNow = size.x > 0 ? this.map.distance(
            this.map.containerPointToLatLng([0, y]),
            this.map.containerPointToLatLng([size.x, y])
        ) / size.x : 0;
        const mPerPxTarget = targetDenom * 0.0002646;
        if (!mPerPxNow || !mPerPxTarget) return null;
        const z = this.map.getZoom() + Math.log2(mPerPxNow / mPerPxTarget);
        // 0.05 步长吸附（与 zoomSnap=0.05 一致），保证比例尺与输入几乎一致（误差<1%）
        const clamped = Math.min(19, Math.max(1, Math.round(z * 20) / 20));
        this.map.setZoom(clamped);
        return clamped;
    }

    initScaleControl() {
        const panel = this;
        const ScaleControl = L.Control.extend({
            options: { position: "bottomleft" },
            onAdd: function() {
                const container = L.DomUtil.create("div", "map-scale");
                container.innerHTML = '<div class="map-scale-num"></div>';
                this._container = container;
                this._update = function() { panel._updateScaleControl(); };
                this._map.on("zoomend moveend", this._update);
                this._update();
                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }
        });
        this.scaleControl = new ScaleControl();
        this.scaleControl.addTo(this.map);
    }

    /**
     * 编制说明（坐标系/投影/数据来源，规范3.7）
     */
    renderMetadata(meta) {
        const el = document.getElementById("map-metadata");
        if (!el) return;
        if (!meta) { el.innerHTML = ""; return; }
        // 投影标注动态化：显示当前实际使用的投影（切换投影后自动更新）
        const meta2 = Object.assign({}, meta);
        if (meta2["投影"]) meta2["投影"] = this._crsName();
        el.innerHTML = '<div class="map-metadata-title">编制说明</div>' +
            Object.entries(meta2).map(([k, v]) =>
                '<div class="map-metadata-line"><b>' + Utils.escapeHtml(k) + "：</b>" +
                Utils.escapeHtml(v) + "</div>").join("");
    }

    /**
     * 从地图数据中查找武汉市域边界多边形坐标
     * @param {object} mapData - 完整地图数据
     * @returns {Array|null} Leaflet格式坐标数组 [[lat, lng], ...] 或 null
     */
    _findWuhanBoundaryPolygon(mapData) {
        // 从生成的图层数据中查找武汉市域边界多边形的坐标
        for (const layer of (mapData.layers || [])) {
            const name = (layer.name || '').toLowerCase();
            if (name.includes('市域边界') || name.includes('市界') || name.includes('wuhan_boundary')) {
                const feats = layer.features || layer.data?.features || [];
                for (const feat of feats) {
                    const geom = feat.geometry || {};
                    if (geom.type === 'Polygon' && geom.coordinates?.length > 0) {
                        // Leaflet用[lat,lng]格式
                        const ring = geom.coordinates[0];
                        return ring.map(c => [c[1], c[0]]);
                    }
                    if (geom.type === 'MultiPolygon' && geom.coordinates?.length > 0) {
                        return geom.coordinates[0][0].map(c => [c[1], c[0]]);
                    }
                }
            }
        }
        return null;
    }

    renderQuality(report) {
        const container = document.getElementById("map-quality-panel");
        if (!container) return;
        const summary = report.summary || {};
        const items = report.items || [];
        const fail = summary.failed || 0;
        let html = '<div class="quality-header">' +
            '<i class="fa-solid fa-shield-halved"></i> 数据质量检测' +
            (summary.passed_all
                ? ' <span class="quality-badge ok">全部通过</span>'
                : ' <span class="quality-badge warn">' + fail + ' 项异常</span>') +
            '<button class="quality-recheck" title="重新检测"><i class="fa-solid fa-rotate"></i></button>' +
            '</div>';
        html += '<div class="quality-items">';
        items.forEach((it) => {
            html += '<div class="quality-item ' + (it.passed ? "ok" : "err") + '" data-idx="' + it.check + '">' +
                '<span class="quality-ico">' + (it.passed ? "✓" : "✗") + "</span>" +
                '<span class="quality-text">' + Utils.escapeHtml(it.check) +
                (it.count ? ' <b>' + it.count + "</b>" : "") + "</span>" +
                (it.positions && it.positions.length
                    ? '<button class="quality-locate" data-idx="' + it.check + '" title="定位问题">📍</button>'
                    : "") +
                "</div>";
            if (!it.passed && it.message) {
                html += '<div class="quality-msg" data-msg-idx="' + it.check + '">' +
                    Utils.escapeHtml(it.message) + "</div>";
            }
        });
        html += "</div>";
        container.innerHTML = html;
        container.classList.remove("hidden");
        container.querySelectorAll(".quality-locate").forEach(btn => {
            btn.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const it = items.find(x => x.check === btn.dataset.idx);
                if (it && it.positions && it.positions.length) {
                    this.map.setView(it.positions[0], Math.max(this.map.getZoom(), 13));
                    if (this._qualityMarker) this.map.removeLayer(this._qualityMarker);
                    this._qualityMarker = L.circleMarker(it.positions[0], {
                        radius: 14, color: "#dc2626", fillColor: "#dc2626", fillOpacity: 0.55
                    }).addTo(this.map);
                    this._qualityMarker.bindPopup("<strong>" + Utils.escapeHtml(it.check) + "</strong>").openPopup();
                }
            });
        });
        container.querySelectorAll(".quality-item").forEach(div => {
            div.addEventListener("click", () => {
                const msg = container.querySelector('[data-msg-idx="' + div.dataset.idx + '"]');
                if (msg) msg.classList.toggle("show");
            });
        });
        const recheck = container.querySelector(".quality-recheck");
        if (recheck) recheck.addEventListener("click", () => this.checkQuality());
    }

    /**
     * 经纬网与经纬度注记（标准地图整饰）
     */
    initGraticule() {
        this.graticuleGroup = L.layerGroup().addTo(this.map);
        this.graticuleLabelGroup = L.layerGroup().addTo(this.map);
        this._updateGraticule = this._updateGraticule.bind(this);
        this.map.on("moveend zoomend", this._updateGraticule);
        // 比例尺回显：缩放/平移后更新工具栏比例尺输入框
        this.map.on("moveend zoomend", () => {
            const _d = this._computeScaleData(140);
            this._syncScaleInput(_d ? _d.denom : 0);
        });
        // 缩放级别变化时刷新注记（字号随比例尺自适应）
        this.map.on("zoomend", () => this.refreshLabels());
        this._updateGraticule();
    }

    _updateGraticule() {
        if (!this.graticuleGroup) return;
        this.graticuleGroup.clearLayers();
        this.graticuleLabelGroup.clearLayers();
        const bounds = this.map.getBounds();
        const zoom = this.map.getZoom();
        const step = zoom <= 7 ? 2 : zoom <= 9 ? 1 : zoom <= 11 ? 0.5 :
                     zoom <= 13 ? 0.2 : zoom <= 15 ? 0.1 : 0.05;
        const south = Math.floor(bounds.getSouth() / step) * step;
        const north = Math.ceil(bounds.getNorth() / step) * step;
        const west = Math.floor(bounds.getWest() / step) * step;
        const east = Math.ceil(bounds.getEast() / step) * step;
        const lineStyle = { color: "#94a3b8", weight: 0.6, opacity: 0.35, interactive: false };
        // 经纬度度分格式（规范：114°30′）
        const fmtDMS = (deg) => {
            const d = Math.abs(deg);
            const dd = Math.floor(d);
            const m = Math.round((d - dd) * 60);
            return dd + "\u00b0" + (m < 10 ? "0" + m : m) + "\u2032";
        };
        // 纬线 + 左边缘纬度注记（度分）
        for (let lat = south; lat <= north + 1e-9; lat += step) {
            const v = Math.round(lat * 100) / 100;
            L.polyline([[v, west], [v, east]], lineStyle).addTo(this.graticuleGroup);
            const label = (Math.abs(v) < 0.01 ? "0\u00b0" : fmtDMS(v) + (v >= 0 ? "N" : "S"));
            this._addGraticuleLabel([v, west], label);
        }
        // 经线 + 底部经度注记（度分）
        for (let lng = west; lng <= east + 1e-9; lng += step) {
            const v = Math.round(lng * 100) / 100;
            L.polyline([[south, v], [north, v]], lineStyle).addTo(this.graticuleGroup);
            const label = (Math.abs(v) < 0.01 ? "0\u00b0" : fmtDMS(v) + (v >= 0 ? "E" : "W"));
            this._addGraticuleLabel([south, v], label);
        }
    }

    _addGraticuleLabel(latlng, text) {
        const icon = L.divIcon({
            className: "graticule-label",
            html: '<span class="graticule-label-text">' + text + "</span>",
            iconSize: [0, 0],
            iconAnchor: [0, 0]
        });
        L.marker(latlng, { icon: icon, interactive: false }).addTo(this.graticuleLabelGroup);
    }

    /**
     * 初始化图层管理面板
     */
    initLayerPanel() {
        const panel = document.getElementById("map-layer-panel");
        if (!panel) return;
        // 关闭按钮
        const closeBtn = panel.querySelector(".layer-panel-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.toggleLayerPanel(false));
        }
    }

    /**
     * 切换图层管理面板显示
     * @param {boolean|null} show - 是否显示，null为切换
     */
    toggleLayerPanel(show = null) {
        const panel = document.getElementById("map-layer-panel");
        if (!panel) return;
        if (show === null) {
            panel.classList.toggle("hidden");
        } else {
            panel.classList.toggle("hidden", !show);
        }
    }

    /**
     * 更新图层管理面板内容
     */
    updateLayerPanel() {
        const container = document.getElementById("map-layer-list");
        if (!container) return;
        container.innerHTML = "";
        const layerEntries = Object.entries(this.layerGroups);
        if (layerEntries.length === 0) {
            container.innerHTML = '<div class="empty-hint">暂无图层</div>';
            return;
        }
        layerEntries.forEach(([layerId, item]) => {
            const div = document.createElement("div");
            div.className = "layer-item";
            const style = item.data.style || {};
            const color = style.color || "#3388ff";
            div.innerHTML = `
                <div class="layer-item-header">
                    <label class="layer-toggle">
                        <input type="checkbox" ${item.visible ? "checked" : ""} data-layer-id="${layerId}">
                        <span class="layer-color-dot" style="background:${color}"></span>
                        <span class="layer-name">${Utils.escapeHtml(item.data.name || "未命名图层")}</span>
                    </label>
                    <button class="layer-edit-btn" data-layer-id="${layerId}" title="编辑样式">
                        <i class="fa-solid fa-sliders"></i>
                    </button>
                </div>
                <div class="layer-item-type">${Utils.escapeHtml(item.data.type || "")}</div>
            `;
            // 切换可见性
            const checkbox = div.querySelector("input[type=checkbox]");
            checkbox.addEventListener("change", (e) => {
                this.toggleLayer(layerId, e.target.checked);
            });
            // 编辑样式
            div.querySelector(".layer-edit-btn").addEventListener("click", () => {
                this.showLayerStyleEditor(layerId);
            });
            container.appendChild(div);
        });
    }

    /**
     * 切换图层可见性
     * @param {string} layerId - 图层ID
     * @param {boolean} visible - 是否可见
     */
    toggleLayer(layerId, visible) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        if (visible) {
            item.layer.addTo(this.map);
        } else {
            this.map.removeLayer(item.layer);
        }
        item.visible = visible;
    }

    /**
     * 显示图层样式编辑器
     * @param {string} layerId - 图层ID
     */
    showLayerStyleEditor(layerId) {
        const item = this.layerGroups[layerId];
        if (!item) return;
        const style = item.data.style || {};
        const editor = document.getElementById("map-style-editor");
        if (!editor) return;
        editor.innerHTML = `
            <div class="style-editor-header">
                <span>编辑图层样式: ${Utils.escapeHtml(item.data.name || "")}</span>
                <button class="style-editor-close"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="style-editor-body">
                <div class="style-field">
                    <label>颜色</label>
                    <input type="color" id="style-color" value="${style.color || "#3388ff"}">
                </div>
                <div class="style-field">
                    <label>线宽: <span id="weight-value">${style.weight || 3}</span></label>
                    <input type="range" id="style-weight" min="1" max="10" value="${style.weight || 3}">
                </div>
                <div class="style-field">
                    <label>透明度: <span id="opacity-value">${(style.opacity !== undefined ? style.opacity : 1).toFixed(2)}</span></label>
                    <input type="range" id="style-opacity" min="0" max="1" step="0.1" value="${style.opacity !== undefined ? style.opacity : 1}">
                </div>
                <div class="style-field">
                    <label>填充透明度: <span id="fill-value">${(style.fillOpacity !== undefined ? style.fillOpacity : 0.2).toFixed(2)}</span></label>
                    <input type="range" id="style-fillOpacity" min="0" max="1" step="0.1" value="${style.fillOpacity !== undefined ? style.fillOpacity : 0.2}">
                </div>
                <div class="style-field">
                    <label>虚线样式</label>
                    <select id="style-dashArray">
                        <option value="" ${!style.dashArray ? "selected" : ""}>实线</option>
                        <option value="5,5" ${style.dashArray === "5,5" ? "selected" : ""}>短虚线</option>
                        <option value="10,5" ${style.dashArray === "10,5" ? "selected" : ""}>长虚线</option>
                        <option value="5,10" ${style.dashArray === "5,10" ? "selected" : ""}>点线</option>
                    </select>
                </div>
                <button class="style-apply-btn" id="style-apply-btn">应用样式</button>
            </div>
        `;
        editor.classList.remove("hidden");
        // 实时显示数值
        const weightInput = document.getElementById("style-weight");
        const weightValue = document.getElementById("weight-value");
        weightInput.addEventListener("input", (e) => {
            weightValue.textContent = e.target.value;
        });
        const opacityInput = document.getElementById("style-opacity");
        const opacityValue = document.getElementById("opacity-value");
        opacityInput.addEventListener("input", (e) => {
            opacityValue.textContent = parseFloat(e.target.value).toFixed(2);
        });
        const fillInput = document.getElementById("style-fillOpacity");
        const fillValue = document.getElementById("fill-value");
        fillInput.addEventListener("input", (e) => {
            fillValue.textContent = parseFloat(e.target.value).toFixed(2);
        });
        // 关闭按钮
        editor.querySelector(".style-editor-close").addEventListener("click", () => {
            editor.classList.add("hidden");
        });
        // ===== 实时预览：输入变化时即时预览样式效果 =====
        const previewStyle = () => {
            const item = this.layerGroups[layerId];
            if (!item || !item.layer) return;
            const previewStyleData = {
                color: document.getElementById("style-color").value,
                weight: parseInt(document.getElementById("style-weight").value) || 1,
                opacity: parseFloat(document.getElementById("style-opacity").value) || 1,
                fillOpacity: parseFloat(document.getElementById("style-fillOpacity").value) || 0.2,
                dashArray: document.getElementById("style-dashArray").value || null
            };
            try {
                if (item.layer.setStyle) {
                    item.layer.setStyle(previewStyleData);
                } else if (item.layer.eachLayer) {
                    item.layer.eachLayer(sub => { if (sub.setStyle) sub.setStyle(previewStyleData); });
                }
            } catch (e) { /* 预览失败忽略 */ }
        };
        // 绑定实时预览事件
        ["style-color", "style-weight", "style-opacity", "style-fillOpacity", "style-dashArray"].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener("input", previewStyle);
            }
        });
        // 应用样式按钮
        document.getElementById("style-apply-btn").addEventListener("click", () => {
            const newStyle = {
                color: document.getElementById("style-color").value,
                weight: parseInt(document.getElementById("style-weight").value),
                opacity: parseFloat(document.getElementById("style-opacity").value),
                fillOpacity: parseFloat(document.getElementById("style-fillOpacity").value),
                dashArray: document.getElementById("style-dashArray").value || null
            };
            this.updateLayerStyle(layerId, newStyle);
        });
    }

    /**
     * 初始化自然语言修改输入框
     */
    initModifyInput() {
        const input = document.getElementById("map-modify-input");
        const btn = document.getElementById("map-modify-btn");
        if (!input || !btn) return;
        // 发送修改指令
        const sendModify = async () => {
            const instruction = input.value.trim();
            if (!instruction) return;
            if (!this.currentMapId) {
                Utils.showToast("请先生成地图", "warning");
                return;
            }
            // 防重复提交
            if (this.isModifying) {
                Utils.showToast("正在执行修改，请稍候", "warning");
                return;
            }
            this.isModifying = true;
            btn.disabled = true;
            btn.innerHTML = '<div class="btn-spinner"></div>';
            try {
                const result = await API.modifyMap(this.currentMapId, instruction);
                // 如果返回了新的地图数据，重新渲染
                if (result.map_data) {
                    this.renderMap(result.map_data);
                } else if (result.data && result.data.map_data) {
                    this.renderMap(result.data.map_data);
                }
                Utils.showToast("修改指令已执行", "success");
                input.value = "";
            } catch (error) {
                Utils.showToast("修改失败: " + error.message, "error");
            } finally {
                this.isModifying = false;
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i>';
            }
        };
        btn.addEventListener("click", sendModify);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendModify();
        });
    }

    /**
     * 重置视图到默认或地图数据指定的视图
     */
    resetView() {
        if (this.currentMapData && this.currentMapData.center) {
            this.map.setView(this.currentMapData.center, this.currentMapData.zoom || CONFIG.defaultZoom);
        } else {
            this.map.setView(CONFIG.defaultMapCenter, CONFIG.defaultZoom);
        }
        Utils.showToast("视图已重置", "info", 1500);
    }

    /**
     * 切换全屏
     */
    toggleFullscreen() {
        const mapContainer = document.getElementById("map-panel");
        if (!mapContainer) return;
        if (!document.fullscreenElement) {
            mapContainer.requestFullscreen().catch(err => {
                Utils.showToast("全屏失败: " + err.message, "error");
            });
        } else {
            document.exitFullscreen();
        }
    }

    /**
     * 显示导出菜单
     */
    showExportMenu() {
        if (!this.currentMapId) {
            Utils.showToast("请先生成地图", "warning");
            return;
        }
        // 创建导出菜单
        const menu = document.createElement("div");
        menu.className = "export-menu";
        menu.innerHTML = `
            <div class="export-menu-overlay"></div>
            <div class="export-menu-dialog">
                <div class="export-menu-header">
                    <span>导出地图</span>
                    <button class="export-menu-close"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="export-menu-body">
                    <button class="export-option" data-format="geojson">
                        <i class="fa-solid fa-file-code"></i>
                        <div>
                            <span class="export-option-name">GeoJSON</span>
                            <span class="export-option-desc">矢量数据格式</span>
                        </div>
                    </button>
                    <button class="export-option" data-format="png">
                        <i class="fa-solid fa-image"></i>
                        <div>
                            <span class="export-option-name">PNG图片</span>
                            <span class="export-option-desc">栅格图片格式</span>
                        </div>
                    </button>
                    <button class="export-option" data-format="svg">
                        <i class="fa-solid fa-bezier-curve"></i>
                        <div>
                            <span class="export-option-name">SVG矢量图</span>
                            <span class="export-option-desc">可缩放矢量图形</span>
                        </div>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(menu);
        // 关闭菜单
        const closeMenu = () => menu.remove();
        menu.querySelector(".export-menu-overlay").addEventListener("click", closeMenu);
        menu.querySelector(".export-menu-close").addEventListener("click", closeMenu);
        // 导出选项点击
        menu.querySelectorAll(".export-option").forEach(btn => {
            btn.addEventListener("click", async () => {
                const format = btn.dataset.format;
                closeMenu();
                await this.exportMap(format);
            });
        });
    }

    /**
     * 更新状态栏
     * @param {string|null} lat - 纬度
     * @param {string|null} lng - 经度
     */
    updateStatusBar(lat = null, lng = null) {
        if (!this.map) return;
        const center = this.map.getCenter();
        const zoom = this.map.getZoom();
        const latEl = document.getElementById("map-status-lat");
        const lngEl = document.getElementById("map-status-lng");
        const zoomEl = document.getElementById("map-status-zoom");
        // 坐标合理性保护：非Web墨卡托投影逆算或异常值时，回退到后端已知中心（武汉30°N/114°E）
        let _lat = lat !== null && lat !== undefined ? lat : center.lat;
        let _lng = lng !== null && lng !== undefined ? lng : center.lng;
        if (!(Math.abs(_lat) <= 90 && Math.abs(_lng) <= 180)) {
            const _c = this.currentMapData && this.currentMapData.center;
            if (_c && _c.length >= 2) { _lat = _c[0]; _lng = _c[1]; }
        }
        if (latEl) latEl.textContent = Number(_lat).toFixed(4) + "°";
        if (lngEl) lngEl.textContent = Number(_lng).toFixed(4) + "°";
        if (zoomEl) zoomEl.textContent = "缩放 " + Number(zoom).toFixed(2);
    }

    /**
     * 更新地图信息显示
     * @param {string} name - 地图名称
     */
    updateMapInfo(name) {
        const nameEl = document.getElementById("map-status-name");
        if (nameEl) nameEl.textContent = name || "未命名地图";
        const layerCountEl = document.getElementById("map-status-layers");
        if (layerCountEl) layerCountEl.textContent = Object.keys(this.layerGroups).length + " 个图层";
    }

    /**
     * 设置地图视图
     * @param {array} center - 中心点 [lat, lng]
     * @param {number} zoom - 缩放级别
     */
    setView(center, zoom) {
        if (this.map && center) {
            this.map.setView(center, zoom || this.map.getZoom());
        }
    }

    // ==================== 路径规划 ====================
    /**
     * 初始化路径规划面板
     */
    initRoutePanel() {
        const panel = document.getElementById("map-route-panel");
        if (!panel) return;
        // 关闭按钮
        const closeBtn = panel.querySelector(".route-panel-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.toggleRoutePanel(false));
        }
        // 出行方式选择
        panel.querySelectorAll(".route-profile-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                panel.querySelectorAll(".route-profile-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                this.selectedProfile = btn.dataset.profile;
            });
        });
        // 起点输入框 - 点击时进入选点模式
        const startLat = document.getElementById("route-start-lat");
        const startLng = document.getElementById("route-start-lng");
        if (startLat && startLng) {
            const enterStartMode = () => {
                this.routePointMode = "start";
                this.map.getContainer().style.cursor = "crosshair";
                Utils.showToast("请在地图上点击起点", "info", 2000);
            };
            startLat.addEventListener("focus", enterStartMode);
            startLng.addEventListener("focus", enterStartMode);
        }
        // 终点输入框 - 点击时进入选点模式
        const endLat = document.getElementById("route-end-lat");
        const endLng = document.getElementById("route-end-lng");
        if (endLat && endLng) {
            const enterEndMode = () => {
                this.routePointMode = "end";
                this.map.getContainer().style.cursor = "crosshair";
                Utils.showToast("请在地图上点击终点", "info", 2000);
            };
            endLat.addEventListener("focus", enterEndMode);
            endLng.addEventListener("focus", enterEndMode);
        }
        // 规划按钮
        const planBtn = document.getElementById("route-plan-btn");
        if (planBtn) {
            planBtn.addEventListener("click", () => this.planRoute());
        }
    }

    /**
     * 切换路径规划面板显示
     * @param {boolean|null} show - 是否显示
     */
    toggleRoutePanel(show = null) {
        const panel = document.getElementById("map-route-panel");
        if (!panel) return;
        if (show === null) {
            panel.classList.toggle("hidden");
        } else {
            panel.classList.toggle("hidden", !show);
        }
    }

    /**
     * 设置路径起终点坐标
     * @param {string} type - "start" 或 "end"
     * @param {array} coords - [lat, lng]
     */
    setRoutePoint(type, coords) {
        const latEl = document.getElementById(`route-${type}-lat`);
        const lngEl = document.getElementById(`route-${type}-lng`);
        if (latEl) latEl.value = coords[0].toFixed(6);
        if (lngEl) lngEl.value = coords[1].toFixed(6);
        // 更新地图上的标记
        this.updateRouteMarkers();
        Utils.showToast(`${type === "start" ? "起点" : "终点"}已设置`, "success", 1500);
    }

    /**
     * 更新路径起终点标记
     */
    updateRouteMarkers() {
        // 清除旧标记
        this.routeMarkers.forEach(m => this.map.removeLayer(m));
        this.routeMarkers = [];
        const startLat = parseFloat(document.getElementById("route-start-lat")?.value);
        const startLng = parseFloat(document.getElementById("route-start-lng")?.value);
        const endLat = parseFloat(document.getElementById("route-end-lat")?.value);
        const endLng = parseFloat(document.getElementById("route-end-lng")?.value);
        // 起点标记
        if (!isNaN(startLat) && !isNaN(startLng)) {
            const startMarker = L.marker([startLat, startLng], {
                icon: L.divIcon({
                    html: '<div style="width:16px;height:16px;background:#22c55e;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                })
            }).bindPopup("起点");
            startMarker.addTo(this.map);
            this.routeMarkers.push(startMarker);
        }
        // 终点标记
        if (!isNaN(endLat) && !isNaN(endLng)) {
            const endMarker = L.marker([endLat, endLng], {
                icon: L.divIcon({
                    html: '<div style="width:16px;height:16px;background:#ef4444;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                })
            }).bindPopup("终点");
            endMarker.addTo(this.map);
            this.routeMarkers.push(endMarker);
        }
    }

    /**
     * 在地图上渲染路径
     * @param {object} routeData - 路径数据
     */
    renderRoute(routeData) {
        // 清除旧路径
        this.clearRoute();
        if (!routeData.coordinates || routeData.coordinates.length === 0) return;
        // 绘制路径线
        this.routeLayer = L.polyline(routeData.coordinates, {
            color: "#3b82f6",
            weight: 5,
            opacity: 0.8,
            lineJoin: "round",
            lineCap: "round"
        }).addTo(this.map);
        // 添加路径弹窗
        const distance = (routeData.distance / 1000).toFixed(2);
        const duration = Math.round(routeData.duration / 60);
        this.routeLayer.bindPopup(`
            <div style="font-size:13px;">
                <strong>${routeData.profile_name || routeData.profile}</strong><br>
                距离: ${distance} km<br>
                预计时间: ${duration} 分钟
            </div>
        `);
        // 调整地图视图以显示完整路径
        this.map.fitBounds(this.routeLayer.getBounds(), { padding: [50, 50] });
    }

    /**
     * 显示路径规划结果信息
     * @param {object} routeData - 路径数据
     */
    showRouteResult(routeData) {
        const resultEl = document.getElementById("route-result");
        if (!resultEl) return;
        const distance = (routeData.distance / 1000).toFixed(2);
        const duration = Math.round(routeData.duration / 60);
        const sourceLabel = routeData.source === "osrm" ? "OSRM实时路径" : "直线估算";
        const steps = routeData.steps || [];
        let stepsHtml = "";
        if (steps.length > 0) {
            stepsHtml = `
                <div class="route-steps">
                    <div class="route-steps-title">导航步骤</div>
                    ${steps.map((step, i) => `
                        <div class="route-step">
                            <span class="route-step-num">${i + 1}</span>
                            <span class="route-step-text">${Utils.escapeHtml(step.instruction || "继续")}</span>
                            <span class="route-step-dist">${(step.distance / 1000).toFixed(2)}km</span>
                        </div>
                    `).join("")}
                </div>
            `;
        }
        resultEl.innerHTML = `
            <div class="route-result-header">
                <i class="fa-solid fa-${routeData.profile === 'driving' ? 'car' : routeData.profile === 'walking' ? 'person-walking' : 'bicycle'}"></i>
                <span>${routeData.profile_name || routeData.profile}</span>
                <span class="route-source">${sourceLabel}</span>
            </div>
            <div class="route-result-stats">
                <div class="route-stat">
                    <span class="route-stat-label">距离</span>
                    <span class="route-stat-value">${distance} km</span>
                </div>
                <div class="route-stat">
                    <span class="route-stat-label">预计时间</span>
                    <span class="route-stat-value">${duration} 分钟</span>
                </div>
                <div class="route-stat">
                    <span class="route-stat-label">坐标点数</span>
                    <span class="route-stat-value">${routeData.coordinates.length}</span>
                </div>
            </div>
            ${stepsHtml}
            <button class="route-clear-btn" onclick="window.app.mapPanel.clearRoute()">
                <i class="fa-solid fa-trash"></i> 清除路径
            </button>
        `;
        resultEl.classList.remove("hidden");
    }

    /**
     * 清除路径规划和标记
     */
    clearRoute() {
        // 清除路径线
        if (this.routeLayer) {
            this.map.removeLayer(this.routeLayer);
            this.routeLayer = null;
        }
        // 清除标记
        this.routeMarkers.forEach(m => this.map.removeLayer(m));
        this.routeMarkers = [];
        // 隐藏结果面板
        const resultEl = document.getElementById("route-result");
        if (resultEl) resultEl.classList.add("hidden");
    }

    /**
     * 自定义标注：点击地图放置标注点（答辩演示：标注赏樱点/卫生间等）
     */
    async addCustomMarker(lat, lng) {
        if (!this.currentMapId) {
            Utils.showToast("请先生成地图", "warning");
            this.markerMode = false;
            this.updateMarkerBtn();
            return;
        }
        const name = window.prompt("标注名称（如：赏樱点、卫生间）：", "标注点");
        if (!name || !name.trim()) {
            this.markerMode = false;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = "";
            return;
        }
        try {
            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/" + this.currentMapId + "/marker", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name.trim(), lat: lat, lng: lng })
            });
            const json = await resp.json();
            if (json.success && json.data) {
                Utils.showToast("已添加标注: " + name, "success");
                this.renderMap(json.data);
            } else {
                Utils.showToast(json.message || "标注添加失败", "error");
            }
        } catch (e) {
            Utils.showToast("标注添加失败: " + e.message, "error");
        } finally {
            this.markerMode = false;
            this.updateMarkerBtn();
            this.map.getContainer().style.cursor = "";
        }
    }

    /**
     * 数据质量检测（五类：拓扑/属性/统计/专题/标注）
     */
    async checkQuality() {
        if (!this.currentMapId) return;
        const container = document.getElementById("map-quality-panel");
        if (!container) return;
        try {
            const resp = await fetch(CONFIG.apiBaseUrl + "/api/maps/" + this.currentMapId + "/quality");
            const json = await resp.json();
            this.renderQuality(json.data || {});
            // 跨要素检查：将检测到的"道路跨水"桥位渲染为桥梁/渡口符号
            this._renderBridgeMarkers(json.data || {});
        } catch (e) {
            container.innerHTML = '<div class="quality-empty">质量检测服务不可用</div>';
            container.classList.remove("hidden");
        }
    }

    /**
     * 渲染桥梁/渡口符号：依据质量检测"道路跨水"项的位置自动上图
     * （制图综合·跨要素关系：道路跨河必须表达桥梁/渡口）
     */
    _renderBridgeMarkers(report) {
        if (!this._bridgeGroup) this._bridgeGroup = L.layerGroup();
        else this._bridgeGroup.clearLayers();
        if (!this._bridgeGroup._map) this._bridgeGroup.addTo(this.map);
        const items = (report && report.items) || [];
        const cross = items.find((it) => (it.check || "").indexOf("道路跨水") === 0);
        if (!cross || !cross.positions || !cross.positions.length) return;
        cross.positions.forEach((pos) => {
            if (!Array.isArray(pos) || pos.length < 2) return;
            L.marker([pos[0], pos[1]], {
                icon: L.divIcon({
                    html: '<div style="width:18px;height:18px;font-size:14px;text-align:center;line-height:17px;background:#ffffff;border:1.5px solid #475569;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.35);">🌉</div>',
                    iconSize: [18, 18],
                    iconAnchor: [9, 9],
                    className: ""
                }),
                zIndexOffset: 900,
                interactive: true
            }).bindTooltip("桥梁/渡口（自动检测）", { sticky: true, opacity: 0.92 })
              .addTo(this._bridgeGroup);
        });
    }

    /**
     * 更新图层样式（颜色/线宽/透明度/虚线），保存到后端并重渲染
     */
    async updateLayerStyle(layerId, style) {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        try {
            const resp = await API.updateLayerStyle(this.currentMapId, layerId, style);
            if (resp.success && resp.data) {
                Utils.showToast("样式已更新", "success", 1600);
                this.renderMap(resp.data);
            } else {
                Utils.showToast(resp.message || "样式更新失败", "error");
            }
        } catch (e) {
            Utils.showToast("样式更新失败: " + e.message, "error");
        }
    }

    /**
     * 导出地图（GeoJSON/SVG/PNG）并触发浏览器下载
     * @param {string} format - geojson / svg / png
     */
    async exportMap(format) {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        Utils.showToast("正在导出 " + format.toUpperCase() + " ...", "info", 1800);
        try {
            const resp = await API.exportMap(this.currentMapId, format);
            if (!resp.success) {
                Utils.showToast(resp.message || "导出失败", "error");
                return;
            }
            const data = resp.data;
            const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
            const fname = ((this.currentMapData && this.currentMapData.name) || "map") + "-" + stamp + "." + format;
            let blob;
            if (format === "png") {
                const b64 = String(data).replace(/^data:[^;]*;base64,/, "");
                const bin = atob(b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                blob = new Blob([arr], { type: "image/png" });
            } else {
                blob = new Blob([data], { type: format === "geojson" ? "application/geo+json" : "image/svg+xml" });
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = fname;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            Utils.showToast("已导出 " + fname, "success");
        } catch (e) {
            Utils.showToast("导出失败: " + e.message, "error");
        }
    }

    /**
     * 规划路径：读取起终点输入，调用后端路由服务并渲染结果
     */
    async planRoute() {
        if (!this.currentMapId) { Utils.showToast("请先生成地图", "warning"); return; }
        const startLat = parseFloat(document.getElementById("route-start-lat")?.value);
        const startLng = parseFloat(document.getElementById("route-start-lng")?.value);
        const endLat = parseFloat(document.getElementById("route-end-lat")?.value);
        const endLng = parseFloat(document.getElementById("route-end-lng")?.value);
        if (isNaN(startLat) || isNaN(startLng) || isNaN(endLat) || isNaN(endLng)) {
            Utils.showToast("请先设置起点和终点坐标", "warning");
            return;
        }
        Utils.showToast("正在规划路径...", "info", 1800);
        try {
            const resp = await API.planRoute(this.currentMapId, {
                start: [startLat, startLng],
                end: [endLat, endLng],
                profile: this.selectedProfile || "driving"
            });
            if (resp.success && resp.data) {
                this.renderRoute(resp.data);
                this.showRouteResult(resp.data);
            } else {
                Utils.showToast(resp.message || "路径规划失败", "error");
            }
        } catch (e) {
            Utils.showToast("路径规划失败: " + e.message, "error");
        }
    }
}
