/**
 * 主应用入口
 * App类：协调三个面板（聊天、地图、图谱），管理全局状态和设置
 */

class App {
    constructor() {
        this.chatPanel = null;      // 聊天面板实例
        this.mapPanel = null;       // 地图面板实例
        this.graphPanel = null;     // 图谱面板实例
        this.currentProvider = null; // 当前LLM提供者
        this.currentModel = null;    // 当前模型
        this.settingsModal = null;   // 设置弹窗
    }

    /**
     * 初始化应用
     */
    async init() {
        console.log("地图制图智能体 - 前端应用启动中...");

        // 设置全局引用（供其他模块访问）
        window.app = this;

        try {
            // 初始化三个面板
            this.chatPanel = new ChatPanel(this);
            this.mapPanel = new MapPanel(this);
            this.graphPanel = new GraphPanel(this);

            // 初始化地图（需要先于其他面板，因为聊天消息可能触发地图渲染）
            this.mapPanel.initMap("map-container");

            // 初始化聊天面板
            this.chatPanel.init();

            // 加载知识图谱数据（loadData内部会调用initGraph初始化SVG）
            this.graphPanel.loadData();

            // 加载LLM状态
            await this.loadLLMStatus();

            // 绑定全局事件
            this.bindGlobalEvents();

            // 绑定设置面板事件
            this.bindSettingsEvents();

            // 绑定文档导入事件
            this.bindImportEvents();

            // 绑定面板折叠（响应式）
            this.bindPanelToggle();

            console.log("应用初始化完成");
        } catch (error) {
            console.error("应用初始化失败:", error);
            Utils.showToast("应用初始化失败: " + error.message, "error");
        }
    }

    /**
     * 加载LLM提供者状态
     */
    async loadLLMStatus() {
        const indicator = document.getElementById("llm-status-indicator");
        const statusText = document.getElementById("llm-status-text");

        if (indicator) indicator.className = "status-dot loading";
        if (statusText) statusText.textContent = "连接中...";

        try {
            const data = await API.getProviders();
            const providers = data.data || data;
            this.currentProvider = providers.current || providers.current_provider || providers.provider || "未知";
            this.currentModel = providers.current_model || providers.model || "";

            // 更新UI
            if (indicator) indicator.className = "status-dot online";
            if (statusText) {
                const displayNames = {
                    deepseek: "DeepSeek",
                    qwen: "通义千问",
                    openai: "OpenAI",
                    zhipu: "智谱GLM",
                    ollama: "Ollama"
                };
                const displayName = displayNames[this.currentProvider] || this.currentProvider;
                statusText.textContent = displayName;
                if (this.currentModel) {
                    statusText.textContent += ` / ${this.currentModel}`;
                }
            }

            // 保存提供者列表（用于设置面板）
            this.providers = providers.providers || providers.available || [];
        } catch (error) {
            console.warn("加载LLM状态失败:", error);
            if (indicator) indicator.className = "status-dot offline";
            if (statusText) statusText.textContent = "离线";
        }
    }

    /**
     * 绑定全局事件
     */
    bindGlobalEvents() {
        // 设置按钮
        const settingsBtn = document.getElementById("settings-btn");
        if (settingsBtn) {
            settingsBtn.addEventListener("click", () => this.showSettings());
        }

        // 点击空白处关闭设置弹窗
        const settingsOverlay = document.getElementById("settings-overlay");
        if (settingsOverlay) {
            settingsOverlay.addEventListener("click", () => this.hideSettings());
        }

        // 全局错误捕获
        window.addEventListener("error", (event) => {
            console.error("全局错误:", event.error);
        });

        // 未处理的Promise拒绝
        window.addEventListener("unhandledrejection", (event) => {
            console.error("未处理的Promise拒绝:", event.reason);
            event.preventDefault();
        });

        // 键盘快捷键
        document.addEventListener("keydown", (e) => {
            // ESC关闭弹窗
            if (e.key === "Escape") {
                this.hideSettings();
                this.hideImportModal();
                const layerPanel = document.getElementById("map-layer-panel");
                if (layerPanel) layerPanel.classList.add("hidden");
                const styleEditor = document.getElementById("map-style-editor");
                if (styleEditor) styleEditor.classList.add("hidden");
                const routePanel = document.getElementById("map-route-panel");
                if (routePanel) routePanel.classList.add("hidden");
                const nodeDetail = document.getElementById("graph-node-detail");
                if (nodeDetail) nodeDetail.classList.add("hidden");
                const graphOverlay = document.getElementById("graph-overlay");
                if (graphOverlay) graphOverlay.classList.add("hidden");
                const sessionDrawer = document.getElementById("session-drawer");
                if (sessionDrawer) sessionDrawer.classList.add("hidden");
            }
        });
    }

    /**
     * 绑定设置面板事件
     */
    bindSettingsEvents() {
        // 关闭按钮
        const closeBtn = document.getElementById("settings-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.hideSettings());
        }

        // 取消按钮
        const cancelBtn = document.getElementById("settings-cancel");
        if (cancelBtn) {
            cancelBtn.addEventListener("click", () => this.hideSettings());
        }

        // LLM提供者切换
        const providerSelect = document.getElementById("settings-provider-select");
        if (providerSelect) {
            providerSelect.addEventListener("change", (e) => {
                this.onProviderChange(e.target.value);
            });
        }

        // 模型选择
        const modelSelect = document.getElementById("settings-model-select");
        if (modelSelect) {
            modelSelect.addEventListener("change", (e) => {
                this.currentModel = e.target.value;
            });
        }

        // 保存设置
        const saveBtn = document.getElementById("settings-save");
        if (saveBtn) {
            saveBtn.addEventListener("click", () => this.saveSettings());
        }

        // API Key 保存按钮（所有提供者共用事件委托）
        document.querySelectorAll(".api-key-save-btn").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                const provider = btn.dataset.provider;
                const input = document.getElementById(`apikey-input-${provider}`);
                if (!input || !input.value.trim()) {
                    Utils.showToast("请输入API Key", "warning");
                    return;
                }
                await this.saveApiKey(provider, input.value.trim());
            });
        });
    }

    /**
     * 显示设置弹窗
     */
    async showSettings() {
        console.log("[App] showSettings 被调用");
        const modal = document.getElementById("settings-modal");
        const overlay = document.getElementById("settings-overlay");
        if (!modal) {
            console.error("[App] 找不到 settings-modal 元素");
            Utils.showToast("设置面板加载失败，请刷新页面", "error");
            return;
        }

        // 强制移除 hidden 类（兼容 CSS 优先级问题）
        modal.classList.remove("hidden");
        modal.style.display = "flex";
        if (overlay) {
            overlay.classList.remove("hidden");
            overlay.style.display = "block";
        }

        console.log("[App] 设置弹窗已显示");
        
        // 加载提供者列表（失败不影响弹窗展示）
        try {
            await this.loadSettingsData();
        } catch (e) {
            console.warn("[App] 加载设置数据失败:", e);
        }
    }

    /**
     * 隐藏设置弹窗
     */
    hideSettings() {
        const modal = document.getElementById("settings-modal");
        const overlay = document.getElementById("settings-overlay");
        if (modal) {
            modal.classList.add("hidden");
            modal.style.display = "";
        }
        if (overlay) {
            overlay.classList.add("hidden");
            overlay.style.display = "";
        }
    }

    /**
     * 加载设置数据
     */
    async loadSettingsData() {
        const providerSelect = document.getElementById("settings-provider-select");
        const modelSelect = document.getElementById("settings-model-select");

        try {
            const data = await API.getProviders();
            const providers = data.data || data;

            // 填充提供者下拉
            if (providerSelect) {
                providerSelect.innerHTML = "";
                const providerList = providers.providers || providers.available || [
                    { id: "ollama", name: "Ollama（本地）", models: ["qwen3:8b"] },
                    { id: "qwen", name: "通义千问", models: ["qwen-plus", "qwen-turbo"] },
                    { id: "openai", name: "OpenAI", models: ["gpt-4o-mini", "gpt-4o"] },
                    { id: "deepseek", name: "DeepSeek", models: ["deepseek-chat"] },
                    { id: "zhipu", name: "智谱GLM", models: ["glm-4"] }
                ];

                providerList.forEach(p => {
                    const id = p.id || p.name || p;
                    const name = p.name || p.id || p;
                    const option = document.createElement("option");
                    option.value = id;
                    option.textContent = name;
                    if (id === this.currentProvider) option.selected = true;
                    providerSelect.appendChild(option);
                });

                // 存储提供者列表供模型选择使用
                this.providersData = providerList;
            }

            // 填充模型下拉
            if (modelSelect) {
                this.updateModelSelect(this.currentProvider);
            }

            // 更新API Key状态指示器
            const providerList = providers.providers || providers.available || [];
            const keyProviders = ["deepseek", "qwen", "openai", "zhipu"];
            keyProviders.forEach(pName => {
                const providerInfo = providerList.find(p => (p.id || p.name) === pName);
                const configured = providerInfo ? providerInfo.configured : false;
                this.updateApiKeyStatus(pName, configured);
            });

            // 地图主题列表
            const themesContainer = document.getElementById("settings-themes");
            if (themesContainer) {
                themesContainer.innerHTML = "";
                Object.entries(CONFIG.mapThemes).forEach(([key, theme]) => {
                    const btn = document.createElement("button");
                    btn.className = "theme-option-btn";
                    if (key === this.mapPanel.currentTheme) btn.classList.add("active");
                    btn.innerHTML = `<span>${theme.name}</span>`;
                    btn.addEventListener("click", () => {
                        this.mapPanel.setTheme(key);
                        document.querySelectorAll(".theme-option-btn").forEach(b => b.classList.remove("active"));
                        btn.classList.add("active");
                    });
                    themesContainer.appendChild(btn);
                });
            }

        } catch (error) {
            Utils.showToast("加载设置失败: " + error.message, "error");
        }
    }

    /**
     * 更新API Key状态指示器
     * @param {string} provider - 提供者名称
     * @param {boolean} configured - 是否已配置
     */
    updateApiKeyStatus(provider, configured) {
        const statusEl = document.getElementById(`apikey-status-${provider}`);
        if (!statusEl) return;

        if (configured) {
            statusEl.className = "api-key-status configured";
            statusEl.innerHTML = '<i class="fa-solid fa-circle-check"></i> 已配置';
        } else {
            statusEl.className = "api-key-status not-configured";
            statusEl.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> 未配置';
        }
    }

    /**
     * 保存指定提供者的API Key
     * @param {string} provider - 提供者名称
     * @param {string} apiKey - API密钥
     */
    async saveApiKey(provider, apiKey) {
        const btn = document.querySelector(`.api-key-save-btn[data-provider="${provider}"]`);
        const originalHtml = btn ? btn.innerHTML : "";

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<div class="btn-spinner"></div>';
        }

        try {
            const result = await API.updateApiKey(provider, apiKey);
            const data = result.data || result;
            const configured = data.configured !== false;

            // 更新状态指示器
            this.updateApiKeyStatus(provider, configured);

            // 清空输入框
            const input = document.getElementById(`apikey-input-${provider}`);
            if (input) input.value = "";

            Utils.showToast(`${provider} API Key 已保存`, "success");
        } catch (error) {
            Utils.showToast(`保存API Key失败: ${error.message}`, "error");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        }
    }

    /**
     * 提供者变化时更新模型列表
     */
    onProviderChange(providerName) {
        this.currentProvider = providerName;
        this.updateModelSelect(providerName);
    }

    /**
     * 更新模型选择下拉
     * @param {string} providerName - 提供者名称
     */
    updateModelSelect(providerName) {
        const modelSelect = document.getElementById("settings-model-select");
        if (!modelSelect) return;

        modelSelect.innerHTML = "";

        // 从缓存的提供者数据中查找模型列表
        let models = [];
        if (this.providersData) {
            const provider = this.providersData.find(p => (p.id || p.name) === providerName);
            if (provider && provider.models) {
                models = provider.models;
            }
        }

        // 如果没有找到模型列表，使用默认值
        if (models.length === 0) {
            const defaultModels = {
                ollama: ["qwen3:8b", "qwen2.5:7b", "llama3:8b"],
                qwen: ["qwen-plus", "qwen-turbo", "qwen-max"],
                openai: ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                deepseek: ["deepseek-chat", "deepseek-coder"],
                zhipu: ["glm-4", "glm-4-flash"]
            };
            models = defaultModels[providerName] || [];
        }

        models.forEach(model => {
            const option = document.createElement("option");
            option.value = model;
            option.textContent = model;
            if (model === this.currentModel) option.selected = true;
            modelSelect.appendChild(option);
        });
    }

    /**
     * 保存设置
     */
    async saveSettings() {
        const provider = document.getElementById("settings-provider-select")?.value;
        const model = document.getElementById("settings-model-select")?.value;

        if (!provider) {
            Utils.showToast("请选择LLM提供者", "warning");
            return;
        }

        try {
            await API.switchProvider(provider, model);
            this.currentProvider = provider;
            this.currentModel = model;

            // 更新顶部状态指示器
            const statusText = document.getElementById("llm-status-text");
            if (statusText) {
                statusText.textContent = `${provider}${model ? " / " + model : ""}`;
            }

            Utils.showToast("设置已保存", "success");
            this.hideSettings();
        } catch (error) {
            Utils.showToast("保存设置失败: " + error.message, "error");
        }
    }

    /**
     * 绑定文档导入事件
     */
    bindImportEvents() {
        // 导入按钮（图表面板头部）
        const importBtn = document.getElementById("kg-import-btn");
        if (importBtn) {
            importBtn.addEventListener("click", () => this.showImportModal());
        }

        // 关闭按钮
        const closeBtn = document.getElementById("kg-import-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", () => this.hideImportModal());
        }

        // 取消按钮
        const cancelBtn = document.getElementById("kg-import-cancel");
        if (cancelBtn) {
            cancelBtn.addEventListener("click", () => this.hideImportModal());
        }

        // 点击遮罩关闭
        const overlay = document.getElementById("kg-import-overlay");
        if (overlay) {
            overlay.addEventListener("click", () => this.hideImportModal());
        }

        // 导入提交按钮
        const submitBtn = document.getElementById("kg-import-submit");
        if (submitBtn) {
            submitBtn.addEventListener("click", () => this.submitImport());
        }
    }

    /**
     * 显示文档导入弹窗
     */
    showImportModal() {
        const modal = document.getElementById("kg-import-modal");
        const overlay = document.getElementById("kg-import-overlay");
        if (modal) modal.classList.remove("hidden");
        if (overlay) overlay.classList.remove("hidden");

        // 清空之前的内容和结果
        const content = document.getElementById("kg-import-content");
        if (content) content.value = "";
        const labels = document.getElementById("kg-import-labels");
        if (labels) labels.value = "";
        const result = document.getElementById("kg-import-result");
        if (result) {
            result.classList.add("hidden");
            result.innerHTML = "";
        }
    }

    /**
     * 隐藏文档导入弹窗
     */
    hideImportModal() {
        const modal = document.getElementById("kg-import-modal");
        const overlay = document.getElementById("kg-import-overlay");
        if (modal) modal.classList.add("hidden");
        if (overlay) overlay.classList.add("hidden");
    }

    /**
     * 提交文档导入
     */
    async submitImport() {
        const content = document.getElementById("kg-import-content")?.value.trim();
        if (!content) {
            Utils.showToast("请输入文档内容", "warning");
            return;
        }

        // 解析实体标签
        const labelsStr = document.getElementById("kg-import-labels")?.value.trim();
        const entityLabels = labelsStr
            ? labelsStr.split(",").map(s => s.trim()).filter(s => s)
            : null;

        const submitBtn = document.getElementById("kg-import-submit");
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<div class="btn-spinner"></div> 导入中...';
        }

        try {
            const result = await API.importDocument(content, entityLabels);
            const data = result.data || result;

            // 显示导入结果
            const resultEl = document.getElementById("kg-import-result");
            if (resultEl && data) {
                const entities = data.entities || [];
                const relations = data.relations || [];
                resultEl.innerHTML = `
                    <div class="kg-import-success">
                        <i class="fa-solid fa-circle-check" style="color: var(--color-success)"></i>
                        <span>导入成功！</span>
                    </div>
                    <div class="kg-import-stats">
                        <div class="kg-import-stat">
                            <span class="kg-import-stat-num">${entities.length}</span>
                            <span class="kg-import-stat-label">实体</span>
                        </div>
                        <div class="kg-import-stat">
                            <span class="kg-import-stat-num">${relations.length}</span>
                            <span class="kg-import-stat-label">关系</span>
                        </div>
                    </div>
                `;
                resultEl.classList.remove("hidden");
            }

            Utils.showToast("文档导入成功", "success");

            // 重新加载知识图谱
            if (this.graphPanel) {
                await this.graphPanel.loadData();
            }

            // 2秒后关闭弹窗
            setTimeout(() => this.hideImportModal(), 2000);
        } catch (error) {
            Utils.showToast("文档导入失败: " + error.message, "error");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> 导入';
            }
        }
    }

    /**
     * 绑定面板切换和工具栏事件
     */
    bindPanelToggle() {
        // === 右侧工具栏按钮 ===

        // 切换聊天面板
        const toggleChat = document.getElementById("toolbar-toggle-chat");
        if (toggleChat) {
            toggleChat.addEventListener("click", () => {
                const panel = document.getElementById("chat-panel");
                if (panel) {
                    panel.classList.toggle("panel-collapsed");
                    toggleChat.classList.toggle("active");
                }
                setTimeout(() => {
                    if (this.mapPanel && this.mapPanel.map) {
                        this.mapPanel.map.invalidateSize();
                    }
                }, 300);
            });
        }

        // 切换知识图谱覆盖层
        const toggleGraph = document.getElementById("toolbar-toggle-graph");
        if (toggleGraph) {
            toggleGraph.addEventListener("click", () => {
                const overlay = document.getElementById("graph-overlay");
                if (overlay) {
                    overlay.classList.toggle("hidden");
                    toggleGraph.classList.toggle("active");
                    // 打开时重新调整图谱大小，关闭时停止仿真节省CPU
                    if (!overlay.classList.contains("hidden")) {
                        setTimeout(() => {
                            if (this.graphPanel) {
                                this.graphPanel.handleResize();
                                // 重新启动仿真
                                if (this.graphPanel.simulation) {
                                    this.graphPanel.simulation.alpha(0.3).restart();
                                }
                            }
                        }, 300);
                    } else {
                        // 关闭时停止D3仿真
                        if (this.graphPanel && this.graphPanel.simulation) {
                            this.graphPanel.simulation.stop();
                        }
                    }
                }
            });
        }

        // 路径规划
        const routeBtn = document.getElementById("toolbar-route");
        if (routeBtn) {
            routeBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.toggleRoutePanel();
                    routeBtn.classList.toggle("active");
                }
            });
        }

        // 图层管理
        const layersBtn = document.getElementById("toolbar-layers");
        if (layersBtn) {
            layersBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.toggleLayerPanel();
                    layersBtn.classList.toggle("active");
                }
            });
        }

        // 切换底图主题
        const themeBtn = document.getElementById("toolbar-theme");
        if (themeBtn) {
            themeBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.cycleTheme();
                }
            });
        }

        // 编辑模式（QGIS/ArcGIS 式几何编辑）
        const editBtn = document.getElementById("toolbar-edit");
        if (editBtn) {
            editBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.toggleEditMode();
                }
            });
        }

        // 导出地图
        const exportBtn = document.getElementById("toolbar-export");
        if (exportBtn) {
            exportBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.showExportMenu();
                }
            });
        }

        // 导入文档
        const importBtn = document.getElementById("toolbar-import");
        if (importBtn) {
            importBtn.addEventListener("click", () => {
                this.showImportModal();
            });
        }

        // 回到中心
        const centerBtn = document.getElementById("toolbar-center");
        if (centerBtn) {
            centerBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.resetView();
                }
            });
        }

        // 清除地图
        const clearBtn = document.getElementById("toolbar-clear");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.clearAllLayers();
                    this.mapPanel.clearRoute();
                    Utils.showToast("地图已清除", "info", 1500);
                }
            });
        }

        // === 顶部导航按钮 ===

        // 新会话
        const newSessionBtn = document.getElementById("header-new-session");
        if (newSessionBtn) {
            newSessionBtn.addEventListener("click", () => {
                if (this.chatPanel) {
                    this.chatPanel.createNewSession();
                }
            });
        }

        // 历史记录（会话抽屉）
        const historyBtn = document.getElementById("header-history");
        if (historyBtn) {
            historyBtn.addEventListener("click", () => {
                this.toggleSessionDrawer();
            });
        }

        // 分享
        const shareBtn = document.getElementById("header-share");
        if (shareBtn) {
            shareBtn.addEventListener("click", () => {
                Utils.showToast("分享功能开发中", "info", 1500);
            });
        }

        // 下载（导出）
        const downloadBtn = document.getElementById("header-download");
        if (downloadBtn) {
            downloadBtn.addEventListener("click", () => {
                if (this.mapPanel) {
                    this.mapPanel.showExportMenu();
                }
            });
        }

        // === 会话抽屉关闭按钮 ===
        const drawerClose = document.getElementById("drawer-close");
        if (drawerClose) {
            drawerClose.addEventListener("click", () => {
                this.toggleSessionDrawer(false);
            });
        }
    }

    /**
     * 切换会话历史抽屉
     * @param {boolean|null} show - 是否显示，null为切换
     */
    toggleSessionDrawer(show = null) {
        const drawer = document.getElementById("session-drawer");
        if (!drawer) return;

        if (show === null) {
            drawer.classList.toggle("hidden");
        } else {
            drawer.classList.toggle("hidden", !show);
        }

        // 打开时重新加载会话列表
        if (!drawer.classList.contains("hidden") && this.chatPanel) {
            this.chatPanel.loadSessions();
        }
    }

    /**
     * 重新加载所有数据
     */
    async reload() {
        await this.chatPanel.loadSessions();
        await this.graphPanel.loadData();
        await this.loadLLMStatus();
    }
}

/**
 * DOM加载完成后初始化应用
 */
document.addEventListener("DOMContentLoaded", () => {
    const app = new App();
    app.init();
});
