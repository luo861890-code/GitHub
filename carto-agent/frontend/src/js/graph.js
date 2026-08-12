/**
 * 知识图谱面板逻辑
 * GraphPanel类：管理D3.js力导向图，渲染节点和边，支持拖拽、搜索、筛选、缩放
 */

class GraphPanel {
    /**
     * 构造函数
     * @param {object} app - 主应用实例
     */
    constructor(app) {
        this.app = app;
        this.svg = null;                    // D3 SVG选择器
        this.container = null;              // 容器选择器
        this.g = null;                      // 主图层组（用于缩放平移）
        this.simulation = null;             // D3力导向仿真
        this.zoom = null;                   // D3缩放行为
        this.graphData = { nodes: [], links: [] };  // 原始图谱数据
        this.filteredData = { nodes: [], links: [] }; // 筛选后数据
        this.nodeScale = null;              // 节点大小比例
        this.activeFilters = new Set();     // 当前激活的类型筛选
        this.searchKeyword = "";            // 当前搜索关键词
        this.selectedNode = null;           // 当前选中节点
        this.width = 0;                     // SVG宽度
        this.height = 0;                    // SVG高度
        this.tooltip = null;                // 节点tooltip元素
        this.eventsBound = false;           // 事件是否已绑定（防止重复绑定）
        this.resizeListenerBound = false;   // resize监听器是否已绑定

        this.elements = {};
    }

    /**
     * 初始化图谱
     * @param {string} containerId - 容器DOM ID
     */
    initGraph(containerId = "graph-container") {
        this.container = d3.select(`#${containerId}`);

        // 获取容器尺寸
        const containerEl = document.getElementById(containerId);
        this.width = containerEl.clientWidth;
        this.height = containerEl.clientHeight;

        // 清空容器
        this.container.selectAll("*").remove();

        // 创建SVG
        this.svg = this.container.append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", `0 0 ${this.width} ${this.height}`)
            .attr("preserveAspectRatio", "xMidYMid meet");

        // 创建defs定义箭头标记
        const defs = this.svg.append("defs");
        Object.entries(CONFIG.kgNodeColors).forEach(([label, color]) => {
            defs.append("marker")
                .attr("id", `arrow-${label}`)
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 20)
                .attr("refY", 0)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,-5L10,0L0,5")
                .attr("fill", color);
        });
        // 默认箭头
        defs.append("marker")
            .attr("id", "arrow-default")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 20)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#999");

        // 创建主图层组（所有内容放在这里，用于缩放平移）
        this.g = this.svg.append("g");

        // 创建链接线和节点组
        this.linkGroup = this.g.append("g").attr("class", "links");
        this.nodeGroup = this.g.append("g").attr("class", "nodes");

        // 创建tooltip（如果已存在则复用，避免重复创建）
        d3.selectAll(".graph-tooltip").remove();
        this.tooltip = d3.select("body").append("div")
            .attr("class", "graph-tooltip")
            .style("opacity", 0);

        // 初始化缩放行为
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {
                this.g.attr("transform", event.transform);
            });

        this.svg.call(this.zoom);

        // 初始化力导向仿真
        this.initSimulation();

        // 绑定UI事件（仅绑定一次，防止重复监听）
        if (!this.eventsBound) {
            this.bindEvents();
            this.initTypeFilters();
            this.eventsBound = true;
        }

        // 监听窗口大小变化（仅绑定一次）
        if (!this.resizeListenerBound) {
            window.addEventListener("resize", Utils.debounce(() => {
                this.handleResize();
            }, 300));
            this.resizeListenerBound = true;
        }
    }

    /**
     * 初始化力导向仿真
     */
    initSimulation() {
        this.simulation = d3.forceSimulation()
            .force("link", d3.forceLink()
                .id(d => d.id)
                .distance(d => 80)
                .strength(d => 0.3)
            )
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(this.width / 2, this.height / 2))
            .force("collision", d3.forceCollide().radius(d => this.getNodeRadius(d) + 5))
            .on("tick", () => this.tick());
    }

    /**
     * 绑定UI事件
     */
    bindEvents() {
        // 搜索框
        const searchInput = document.getElementById("graph-search");
        if (searchInput) {
            searchInput.addEventListener("input", Utils.debounce((e) => {
                this.searchKeyword = e.target.value.trim().toLowerCase();
                this.applyFilters();
            }, 200));
        }

        // 重新布局按钮
        const reheatBtn = document.getElementById("graph-reheat");
        if (reheatBtn) {
            reheatBtn.addEventListener("click", () => {
                this.simulation.alpha(1).restart();
                Utils.showToast("已重新布局", "info", 1000);
            });
        }

        // 重置缩放按钮
        const resetZoomBtn = document.getElementById("graph-reset-zoom");
        if (resetZoomBtn) {
            resetZoomBtn.addEventListener("click", () => {
                this.svg.transition().duration(500).call(
                    this.zoom.transform,
                    d3.zoomIdentity
                );
            });
        }

        // 刷新数据按钮
        const refreshBtn = document.getElementById("graph-refresh");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", () => {
                this.loadData();
            });
        }

        // 关闭按钮（滑出式覆盖层）
        const closeBtn = document.getElementById("graph-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => {
                document.getElementById("graph-overlay").classList.add("hidden");
            });
        }
    }

    /**
     * 初始化类型筛选按钮
     */
    initTypeFilters() {
        const container = document.getElementById("graph-type-filters");
        if (!container) return;

        container.innerHTML = "";

        // "全部"按钮
        const allBtn = document.createElement("button");
        allBtn.className = "type-filter-btn active";
        allBtn.dataset.label = "all";
        allBtn.textContent = "全部";
        allBtn.addEventListener("click", () => this.toggleTypeFilter("all", allBtn));
        container.appendChild(allBtn);

        // 各类型按钮
        Object.entries(CONFIG.kgNodeColors).forEach(([label, color]) => {
            const btn = document.createElement("button");
            btn.className = "type-filter-btn";
            btn.dataset.label = label;
            btn.innerHTML = `<span class="filter-color-dot" style="background:${color}"></span> ${label}`;
            btn.addEventListener("click", () => this.toggleTypeFilter(label, btn));
            container.appendChild(btn);
        });
    }

    /**
     * 切换类型筛选
     * @param {string} label - 节点类型标签
     * @param {HTMLElement} btn - 按钮元素
     */
    toggleTypeFilter(label, btn) {
        const allBtn = document.querySelector('.type-filter-btn[data-label="all"]');

        if (label === "all") {
            // 点击"全部"时清空筛选
            this.activeFilters.clear();
            document.querySelectorAll(".type-filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
        } else {
            // 切换该类型的筛选状态
            if (this.activeFilters.has(label)) {
                this.activeFilters.delete(label);
                btn.classList.remove("active");
            } else {
                this.activeFilters.add(label);
                btn.classList.add("active");
            }
            // 取消"全部"按钮的激活
            if (allBtn) allBtn.classList.remove("active");

            // 如果没有任何筛选，恢复"全部"
            if (this.activeFilters.size === 0 && allBtn) {
                allBtn.classList.add("active");
            }
        }

        this.applyFilters();
    }

    /**
     * 应用筛选条件（类型 + 搜索）
     */
    applyFilters() {
        let nodes = [...this.graphData.nodes];
        let links = [...this.graphData.links];

        // 类型筛选
        if (this.activeFilters.size > 0) {
            const allowedIds = new Set(
                nodes.filter(n => this.activeFilters.has(n.label)).map(n => n.id)
            );
            nodes = nodes.filter(n => allowedIds.has(n.id));
            links = links.filter(l => {
                const sourceId = typeof l.source === "object" ? l.source.id : l.source;
                const targetId = typeof l.target === "object" ? l.target.id : l.target;
                return allowedIds.has(sourceId) && allowedIds.has(targetId);
            });
        }

        this.filteredData = { nodes, links };

        // 重新渲染
        this.renderGraph(this.filteredData);

        // 应用搜索高亮
        if (this.searchKeyword) {
            this.highlightSearch();
        }
    }

    /**
     * 加载知识图谱数据
     * @param {number} limit - 节点数量限制
     */
    async loadData(limit = CONFIG.kgDefaultLimit) {
        const container = document.getElementById("graph-container");
        if (container) {
            container.innerHTML = `
                <div class="graph-loading">
                    <div class="spinner"></div>
                    <span>加载知识图谱...</span>
                </div>
            `;
        }

        try {
            const data = await API.getKGGraph(limit);
            const graphData = data.data || data;

            this.graphData = {
                nodes: graphData.nodes || [],
                links: graphData.links || []
            };

            // 重新初始化SVG（因为loading状态清空了容器）
            this.initGraph("graph-container");
            this.renderGraph(this.graphData);

            // 更新节点计数
            this.updateNodeCount();
        } catch (error) {
            console.error("加载知识图谱失败:", error);
            if (container) {
                container.innerHTML = `
                    <div class="graph-error">
                        <i class="fa-solid fa-circle-exclamation"></i>
                        <span>加载失败</span>
                        <span class="graph-error-detail">${Utils.escapeHtml(error.message)}</span>
                        <button class="graph-retry-btn" onclick="window.app.graphPanel.loadData()">
                            <i class="fa-solid fa-rotate-right"></i> 重试
                        </button>
                    </div>
                `;
            }
        }
    }

    /**
     * 渲染图谱
     * @param {object} data - {nodes, links}
     */
    renderGraph(data) {
        if (!data || !data.nodes) return;

        const nodes = data.nodes;
        const links = data.links;

        // 更新仿真数据
        this.simulation.nodes(nodes);
        this.simulation.force("link").links(links);

        // ===== 渲染连接线 =====
        this.linkGroup.selectAll("line")
            .data(links, d => {
                const s = typeof d.source === "object" ? d.source.id : d.source;
                const t = typeof d.target === "object" ? d.target.id : d.target;
                return s + "-" + t;
            })
            .join(
                enter => enter.append("line")
                    .attr("class", "graph-link")
                    .attr("stroke", "#94a3b8")
                    .attr("stroke-opacity", 0.5)
                    .attr("stroke-width", d => Math.sqrt(d.value || 1)),
                update => update,
                exit => exit.remove()
            );

        // ===== 渲染节点 =====
        const nodeSel = this.nodeGroup.selectAll("g.graph-node")
            .data(nodes, d => d.id)
            .join(
                enter => {
                    const nodeEnter = enter.append("g")
                        .attr("class", "graph-node")
                        .call(d3.drag()
                            .on("start", (event, d) => this.dragStarted(event, d))
                            .on("drag", (event, d) => this.dragged(event, d))
                            .on("end", (event, d) => this.dragEnded(event, d))
                        );

                    // 节点圆形
                    nodeEnter.append("circle")
                        .attr("class", "node-circle")
                        .attr("r", d => this.getNodeRadius(d))
                        .attr("fill", d => this.getNodeColor(d))
                        .attr("stroke", "#fff")
                        .attr("stroke-width", 2);

                    // 节点文字
                    nodeEnter.append("text")
                        .attr("class", "node-label")
                        .attr("dy", d => this.getNodeRadius(d) + 14)
                        .attr("text-anchor", "middle")
                        .text(d => this.truncateText(d.name || d.id, 10))
                        .attr("font-size", "10px")
                        .attr("fill", "#475569");

                    // 事件绑定
                    nodeEnter
                        .on("mouseover", (event, d) => this.handleMouseOver(event, d))
                        .on("mouseout", (event, d) => this.handleMouseOut(event, d))
                        .on("click", (event, d) => this.handleNodeClick(event, d));

                    return nodeEnter;
                },
                update => update,
                exit => exit.remove()
            );

        // 重启仿真
        this.simulation.alpha(0.5).restart();
    }

    /**
     * 仿真tick回调，更新节点和连线位置
     */
    tick() {
        // 更新连线位置
        this.linkGroup.selectAll("line")
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        // 更新节点位置
        this.nodeGroup.selectAll("g.graph-node")
            .attr("transform", d => {
                // 边界约束，防止节点飞出视图
                d.x = Math.max(this.getNodeRadius(d), Math.min(this.width - this.getNodeRadius(d), d.x));
                d.y = Math.max(this.getNodeRadius(d), Math.min(this.height - this.getNodeRadius(d), d.y));
                return `translate(${d.x}, ${d.y})`;
            });
    }

    /**
     * 获取节点半径（根据连接数动态调整）
     * @param {object} d - 节点数据
     * @returns {number} 半径
     */
    getNodeRadius(d) {
        if (d.radius) return d.radius;
        // 根据属性或连接数计算大小
        const baseSize = 12;
        const connections = d.connections || d.degree || 0;
        return Math.max(8, Math.min(25, baseSize + connections * 1.5));
    }

    /**
     * 获取节点颜色
     * @param {object} d - 节点数据
     * @returns {string} 颜色值
     */
    getNodeColor(d) {
        return CONFIG.kgNodeColors[d.label] || "#64748b";
    }

    /**
     * 截断文本
     * @param {string} text - 原始文本
     * @param {number} maxLen - 最大长度
     * @returns {string} 截断后的文本
     */
    truncateText(text, maxLen = 10) {
        if (!text) return "";
        return text.length > maxLen ? text.substring(0, maxLen) + "..." : text;
    }

    /**
     * 鼠标悬停事件
     */
    handleMouseOver(event, d) {
        // 高亮节点
        d3.select(event.currentTarget).select("circle")
            .transition().duration(200)
            .attr("r", this.getNodeRadius(d) * 1.3)
            .attr("stroke-width", 3);

        // 显示tooltip
        const propsText = d.properties ? Object.entries(d.properties)
            .map(([k, v]) => `<div class="tooltip-prop"><span class="tooltip-key">${Utils.escapeHtml(k)}:</span> <span class="tooltip-val">${Utils.escapeHtml(String(v))}</span></div>`)
            .join("") : "";

        this.tooltip
            .style("opacity", 1)
            .style("left", (event.pageX + 15) + "px")
            .style("top", (event.pageY - 10) + "px")
            .html(`
                <div class="tooltip-title">${Utils.escapeHtml(d.name || d.id)}</div>
                <div class="tooltip-label"><span class="tooltip-key">类型:</span> ${Utils.escapeHtml(d.label || "未知")}</div>
                ${propsText}
            `);
    }

    /**
     * 鼠标移出事件
     */
    handleMouseOut(event, d) {
        d3.select(event.currentTarget).select("circle")
            .transition().duration(200)
            .attr("r", this.getNodeRadius(d))
            .attr("stroke-width", 2);

        this.tooltip.style("opacity", 0);
    }

    /**
     * 节点点击事件 - 显示详情面板
     */
    handleNodeClick(event, d) {
        event.stopPropagation();
        this.selectedNode = d;
        this.showNodeDetail(d);
    }

    /**
     * 显示节点详情面板
     * @param {object} node - 节点数据
     */
    showNodeDetail(node) {
        const panel = document.getElementById("graph-node-detail");
        if (!panel) return;

        const color = this.getNodeColor(node);
        let propsHtml = "";

        if (node.properties && Object.keys(node.properties).length > 0) {
            propsHtml = Object.entries(node.properties).map(([key, value]) => `
                <div class="detail-prop">
                    <span class="detail-prop-key">${Utils.escapeHtml(key)}</span>
                    <span class="detail-prop-val">${Utils.escapeHtml(String(value))}</span>
                </div>
            `).join("");
        } else {
            propsHtml = '<div class="detail-empty">无额外属性</div>';
        }

        // 查找关联节点
        const relatedLinks = this.graphData.links.filter(l => {
            const sId = typeof l.source === "object" ? l.source.id : l.source;
            const tId = typeof l.target === "object" ? l.target.id : l.target;
            return sId === node.id || tId === node.id;
        });

        let relationsHtml = "";
        if (relatedLinks.length > 0) {
            relationsHtml = relatedLinks.slice(0, 10).map(link => {
                const sId = typeof link.source === "object" ? link.source.id : link.source;
                const tId = typeof link.target === "object" ? link.target.id : link.target;
                const isSource = sId === node.id;
                const otherId = isSource ? tId : sId;
                const otherNode = this.graphData.nodes.find(n => n.id === otherId);
                const direction = isSource ? "→" : "←";
                const relationType = link.type || link.relation_type || "关联";
                return `
                    <div class="detail-relation">
                        <span class="relation-arrow">${direction}</span>
                        <span class="relation-type">${Utils.escapeHtml(relationType)}</span>
                        <span class="relation-node">${Utils.escapeHtml(otherNode ? (otherNode.name || otherNode.id) : otherId)}</span>
                    </div>
                `;
            }).join("");
        } else {
            relationsHtml = '<div class="detail-empty">无关联节点</div>';
        }

        panel.innerHTML = `
            <div class="detail-header">
                <span class="detail-color-dot" style="background:${color}"></span>
                <span class="detail-name">${Utils.escapeHtml(node.name || node.id)}</span>
                <button class="detail-close" onclick="document.getElementById('graph-node-detail').classList.add('hidden')">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="detail-section">
                <div class="detail-section-title">基本信息</div>
                <div class="detail-prop">
                    <span class="detail-prop-key">ID</span>
                    <span class="detail-prop-val">${Utils.escapeHtml(node.id)}</span>
                </div>
                <div class="detail-prop">
                    <span class="detail-prop-key">类型</span>
                    <span class="detail-prop-val">${Utils.escapeHtml(node.label || "未知")}</span>
                </div>
                <div class="detail-prop">
                    <span class="detail-prop-key">名称</span>
                    <span class="detail-prop-val">${Utils.escapeHtml(node.name || "未命名")}</span>
                </div>
            </div>
            <div class="detail-section">
                <div class="detail-section-title">属性 (${node.properties ? Object.keys(node.properties).length : 0})</div>
                ${propsHtml}
            </div>
            <div class="detail-section">
                <div class="detail-section-title">关联 (${relatedLinks.length})</div>
                ${relationsHtml}
            </div>
        `;

        panel.classList.remove("hidden");
    }

    /**
     * 搜索高亮
     */
    highlightSearch() {
        if (!this.searchKeyword) {
            // 清除高亮
            this.nodeGroup.selectAll("g.graph-node")
                .classed("node-dimmed", false)
                .classed("node-highlighted", false);
            this.linkGroup.selectAll("line")
                .attr("stroke-opacity", 0.5);
            return;
        }

        // 高亮匹配的节点，淡化其他节点
        this.nodeGroup.selectAll("g.graph-node")
            .classed("node-highlighted", d => {
                const name = (d.name || d.id || "").toLowerCase();
                return name.includes(this.searchKeyword);
            })
            .classed("node-dimmed", d => {
                const name = (d.name || d.id || "").toLowerCase();
                return !name.includes(this.searchKeyword);
            });
    }

    /**
     * 拖拽开始
     */
    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    /**
     * 拖拽中
     */
    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    /**
     * 拖拽结束
     */
    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        // 释放固定位置（可选：保留固定位置）
        d.fx = null;
        d.fy = null;
    }

    /**
     * 处理容器尺寸变化
     */
    handleResize() {
        const containerEl = document.getElementById("graph-container");
        if (!containerEl) return;

        this.width = containerEl.clientWidth;
        this.height = containerEl.clientHeight;

        if (this.svg) {
            this.svg.attr("viewBox", `0 0 ${this.width} ${this.height}`);
        }

        if (this.simulation) {
            this.simulation.force("center", d3.forceCenter(this.width / 2, this.height / 2));
            this.simulation.alpha(0.3).restart();
        }
    }

    /**
     * 更新节点计数显示
     */
    updateNodeCount() {
        const countEl = document.getElementById("graph-node-count");
        if (countEl) {
            countEl.textContent = `${this.graphData.nodes.length} 节点 / ${this.graphData.links.length} 关系`;
        }
    }

    /**
     * 知识图谱问答
     * @param {string} question - 问题
     */
    async query(question) {
        try {
            const result = await API.kgQuery(question);
            return result;
        } catch (error) {
            Utils.showToast("图谱问答失败: " + error.message, "error");
            throw error;
        }
    }
}
