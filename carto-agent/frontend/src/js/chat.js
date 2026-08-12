/**
 * 聊天面板逻辑
 * ChatPanel类：管理消息列表、输入框、快捷指令、历史会话
 * 与后端API交互，发送消息并渲染回复（含思考过程、执行步骤、地图数据）
 */

class ChatPanel {
    /**
     * 构造函数
     * @param {object} app - 主应用实例，用于跨面板调用
     */
    constructor(app) {
        this.app = app;
        this.currentSessionId = null;       // 当前会话ID
        this.sessions = [];                  // 会话列表
        this.messages = [];                  // 当前会话消息列表
        this.isSending = false;             // 是否正在发送（防重复）
        this.typingIndicatorId = null;      // 打字指示器消息ID

        // DOM元素引用
        this.elements = {};
    }

    /**
     * 初始化聊天面板
     * 绑定事件监听器，加载会话列表
     */
    init() {
        this.bindElements();
        this.bindEvents();
        this.renderQuickCommands();
        this.loadSessions();
    }

    /**
     * 绑定DOM元素引用
     */
    bindElements() {
        this.elements = {
            messageList: document.getElementById("chat-message-list"),
            inputBox: document.getElementById("chat-input-box"),
            sendBtn: document.getElementById("chat-send-btn"),
            sessionList: document.getElementById("chat-session-list"),
            quickCommands: document.getElementById("chat-quick-commands")
        };
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 发送按钮点击
        this.elements.sendBtn.addEventListener("click", () => this.sendMessage());

        // 输入框回车发送（Shift+Enter换行）
        this.elements.inputBox.addEventListener("keydown", (e) => {
            // Enter发送 / Shift+Enter换行 / Ctrl+Enter也可发送
            if (e.key === "Enter" && (!e.shiftKey || e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 输入框内容变化时调整高度
        this.elements.inputBox.addEventListener("input", () => {
            this.autoResizeTextarea();
        });
    }

    /**
     * 渲染快捷指令按钮
     */
    renderQuickCommands() {
        const container = this.elements.quickCommands;
        container.innerHTML = "";

        // 仅在无消息时显示（新对话），发送第一条消息后自动隐藏
        if (this.messages.length > 0) {
            container.style.display = "none";
            return;
        }
        container.style.display = "flex";

        CONFIG.quickCommands.forEach(cmd => {
            const btn = document.createElement("button");
            btn.className = "quick-command-btn";
            btn.innerHTML = `<i class="fa-solid ${cmd.icon}"></i> <span>${cmd.label}</span>`;
            btn.addEventListener("click", () => {
                this.elements.inputBox.value = cmd.message;
                this.autoResizeTextarea();
                this.sendMessage();
            });
            container.appendChild(btn);
        });
    }

    /**
     * 自动调整输入框高度
     */
    autoResizeTextarea() {
        const textarea = this.elements.inputBox;
        textarea.style.height = "auto";
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
    }

    /**
     * 加载会话列表
     */
    async loadSessions() {
        try {
            const data = await API.listSessions();
            // 兼容不同的返回格式
            this.sessions = Array.isArray(data) ? data : (data.sessions || data.data || []);
            this.renderSessionList();

            // 如果有会话，自动选中第一个
            if (this.sessions.length > 0 && !this.currentSessionId) {
                await this.switchSession(this.sessions[0].session_id);
            } else if (this.sessions.length === 0) {
                // 没有会话时自动创建一个
                await this.createNewSession();
            }
        } catch (error) {
            console.error("加载会话列表失败:", error);
            // 失败时显示空状态
            this.renderSessionList();
        }
    }

    /**
     * 渲染会话列表
     */
    renderSessionList() {
        const container = this.elements.sessionList;
        container.innerHTML = "";

        if (this.sessions.length === 0) {
            container.innerHTML = '<div class="empty-hint">暂无会话</div>';
            return;
        }

        this.sessions.forEach(session => {
            const item = document.createElement("div");
            item.className = "session-item";
            if (session.session_id === this.currentSessionId) {
                item.classList.add("active");
            }

            item.innerHTML = `
                <div class="session-item-content" data-session-id="${session.session_id}">
                    <i class="fa-solid fa-comments session-icon"></i>
                    <span class="session-title">${Utils.escapeHtml(session.title)}</span>
                </div>
                <button class="session-delete-btn" data-session-id="${session.session_id}" title="删除会话">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;

            // 点击切换会话
            item.querySelector(".session-item-content").addEventListener("click", () => {
                this.switchSession(session.session_id);
            });

            // 删除会话
            item.querySelector(".session-delete-btn").addEventListener("click", (e) => {
                e.stopPropagation();
                this.deleteSession(session.session_id);
            });

            container.appendChild(item);
        });
    }

    /**
     * 创建新会话
     */
    async createNewSession() {
        try {
            const data = await API.createSession("新会话");
            const session = data.data || data;
            this.sessions.unshift(session);
            this.currentSessionId = session.session_id;
            this.messages = [];
            this.renderSessionList();
            this.renderMessageList();
            this.elements.inputBox.focus();
        } catch (error) {
            Utils.showToast("创建会话失败: " + error.message, "error");
        }
    }

    /**
     * 切换到指定会话
     * @param {string} sessionId - 会话ID
     */
    async switchSession(sessionId) {
        if (this.isSending) {
            Utils.showToast("正在发送消息，请稍候", "warning");
            return;
        }

        this.currentSessionId = sessionId;
        this.messages = [];

        // 更新会话列表高亮
        this.renderSessionList();

        // 显示加载状态
        this.elements.messageList.innerHTML = `
            <div class="chat-loading">
                <div class="spinner"></div>
                <span>加载会话...</span>
            </div>
        `;

        try {
            // 获取会话详情（含消息历史）
            const data = await API.getSession(sessionId);
            const session = data.data || data;
            this.messages = session.messages || [];
            this.renderMessageList();
        } catch (error) {
            console.error("加载会话详情失败:", error);
            this.elements.messageList.innerHTML = `
                <div class="chat-error">
                    <i class="fa-solid fa-circle-exclamation"></i>
                    <span>加载失败: ${Utils.escapeHtml(error.message)}</span>
                </div>
            `;
        }
    }

    /**
     * 删除会话
     * @param {string} sessionId - 会话ID
     */
    async deleteSession(sessionId) {
        if (!confirm("确定要删除这个会话吗？")) return;

        try {
            await API.deleteSession(sessionId);
            this.sessions = this.sessions.filter(s => s.session_id !== sessionId);

            // 如果删除的是当前会话，切换到第一个或创建新的
            if (this.currentSessionId === sessionId) {
                this.currentSessionId = null;
                this.messages = [];
                if (this.sessions.length > 0) {
                    await this.switchSession(this.sessions[0].session_id);
                } else {
                    await this.createNewSession();
                }
            }
            this.renderSessionList();
            Utils.showToast("会话已删除", "success");
        } catch (error) {
            Utils.showToast("删除会话失败: " + error.message, "error");
        }
    }

    /**
     * 渲染消息列表
     */
    renderMessageList() {
        const container = this.elements.messageList;
        container.innerHTML = "";

        if (this.messages.length === 0) {
            container.innerHTML = `
                <div class="chat-welcome">
                    <div class="chat-welcome-icon">
                        <i class="fa-solid fa-map-location-dot"></i>
                    </div>
                    <h2 class="chat-welcome-title">欢迎使用地图制图智能体</h2>
                    <p class="chat-welcome-hint">描述你想要的地图效果，我来帮你生成</p>
                </div>
            `;
            return;
        }

        this.messages.forEach(msg => {
            this.addMessage(msg.role, msg.content, {
                thinking: msg.thinking,
                steps: msg.steps,
                map_data: msg.map_data,
                timestamp: msg.timestamp
            });
        });

        // 滚动到底部
        this.scrollToBottom();
    }

    /**
     * 添加消息到UI
     * @param {string} role - 消息角色 user/assistant
     * @param {string} content - 消息内容
     * @param {object} extra - 额外信息 {thinking, steps, map_data, timestamp}
     */
    addMessage(role, content, extra = {}) {
        const container = this.elements.messageList;
        const msgDiv = document.createElement("div");
        msgDiv.className = `message message-${role}`;

        const time = extra.timestamp ? Utils.formatTime(extra.timestamp) : Utils.formatTime(Date.now() / 1000);

        // 构建消息内容HTML
        let contentHtml = "";

        // 助手消息可能有思考过程
        if (role === "assistant" && extra.thinking) {
            contentHtml += `
                <div class="thinking-panel">
                    <div class="thinking-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <i class="fa-solid fa-brain"></i>
                        <span>思考过程</span>
                        <i class="fa-solid fa-chevron-down thinking-arrow"></i>
                    </div>
                    <div class="thinking-body">${Utils.escapeHtml(extra.thinking)}</div>
                </div>
            `;
        }

        // 助手消息可能有执行步骤
        if (role === "assistant" && extra.steps && extra.steps.length > 0) {
            contentHtml += '<div class="steps-panel">';
            extra.steps.forEach((step, index) => {
                const statusIcon = {
                    pending: "fa-clock",
                    running: "fa-spinner fa-spin",
                    success: "fa-circle-check",
                    failed: "fa-circle-xmark"
                };
                contentHtml += `
                    <div class="step-item step-${step.status || "pending"}">
                        <i class="fa-solid ${statusIcon[step.status] || statusIcon.pending}"></i>
                        <div class="step-info">
                            <span class="step-name">${Utils.escapeHtml(step.name || step.step_id)}</span>
                            <span class="step-desc">${Utils.escapeHtml(step.description || "")}</span>
                        </div>
                    </div>
                `;
            });
            contentHtml += '</div>';
        }

        // 消息正文
        contentHtml += `<div class="message-text">${Utils.renderMarkdown(content)}</div>`;

        // 如果有地图数据，显示地图提示（使用占位符，后面通过事件监听器绑定）
        let mapLinkPlaceholder = "";
        if (role === "assistant" && extra.map_data) {
            const mapName = extra.map_data.name || "地图";
            mapLinkPlaceholder = `<div class="message-map-link" data-has-map="true">
                    <i class="fa-solid fa-map"></i>
                    <span>查看地图: ${Utils.escapeHtml(mapName)}</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </div>`;
            contentHtml += mapLinkPlaceholder;
        }

        // 助手消息显示模型信息
        let footerHtml = "";
        if (role === "assistant" && extra.provider) {
            footerHtml = `<div class="message-footer">
                <span class="message-model"><i class="fa-solid fa-microchip"></i> ${Utils.escapeHtml(extra.provider)}${extra.model ? " / " + Utils.escapeHtml(extra.model) : ""}</span>
            </div>`;
        }

        msgDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid ${role === "user" ? "fa-user" : "fa-robot"}"></i>
            </div>
            <div class="message-body">
                <div class="message-meta">
                    <span class="message-role">${role === "user" ? "我" : "智能体"}</span>
                    <span class="message-time">${time}</span>
                </div>
                ${contentHtml}
                ${footerHtml}
            </div>
        `;

        container.appendChild(msgDiv);
        this.scrollToBottom();

        // 为地图链接绑定点击事件（使用闭包捕获map_data，避免JSON嵌入HTML属性的风险）
        if (extra.map_data) {
            const mapLink = msgDiv.querySelector(".message-map-link[data-has-map]");
            if (mapLink) {
                const mapData = extra.map_data;
                mapLink.addEventListener("click", () => {
                    if (this.app && this.app.mapPanel) {
                        this.app.mapPanel.renderMap(mapData);
                    }
                });
            }
        }

        // 如果有地图数据，自动渲染到地图面板
        if (extra.map_data && this.app && this.app.mapPanel) {
            this.app.mapPanel.renderMap(extra.map_data);
        }
    }

    /**
     * 显示打字指示器
     */
    showTypingIndicator() {
        const container = this.elements.messageList;
        const div = document.createElement("div");
        this.typingIndicatorId = Utils.generateId();
        div.id = this.typingIndicatorId;
        div.className = "message message-assistant";
        div.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="message-body">
                <div class="message-meta">
                    <span class="message-role">智能体</span>
                </div>
                <div class="typing-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            </div>
        `;
        container.appendChild(div);
        this.scrollToBottom();
    }

    /**
     * 移除打字指示器
     */
    removeTypingIndicator() {
        if (this.typingIndicatorId) {
            const el = document.getElementById(this.typingIndicatorId);
            if (el) el.remove();
            this.typingIndicatorId = null;
        }
    }

    /**
     * 发送消息
     */
    async sendMessage() {
        const input = this.elements.inputBox;
        const message = input.value.trim();

        // 输入验证
        if (!message) return;
        if (this.isSending) {
            Utils.showToast("正在处理中，请稍候", "warning");
            return;
        }
        if (message.length > CONFIG.maxMessageLength) {
            Utils.showToast(`消息过长，最多${CONFIG.maxMessageLength}个字符`, "warning");
            return;
        }

        // 如果没有当前会话，先创建一个
        if (!this.currentSessionId) {
            await this.createNewSession();
            if (!this.currentSessionId) {
                Utils.showToast("无法创建会话", "error");
                return;
            }
        }

        // 设置发送状态
        this.isSending = true;
        this.updateSendButton();

        // 添加用户消息到UI
        this.addMessage("user", message, { timestamp: Date.now() / 1000 });
        this.messages.push({ role: "user", content: message, timestamp: Date.now() / 1000 });

        // 发送第一条消息后隐藏快捷指令
        this.renderQuickCommands();

        // 清空输入框
        input.value = "";
        this.autoResizeTextarea();

        // 显示打字指示器（连接阶段）
        this.showTypingIndicator();

        // 流式响应数据收集
        let assistantDiv = null;
        let textContent = "";
        let thinkingText = "";
        let stepsData = [];
        let mapData = null;
        let geotokenInfo = null;
        let ragSources = [];
        let graphragEntities = [];
        let knowledgeSources = {};
        let provider = "";
        let model = "";

        try {
            await API.streamMessage(this.currentSessionId, message, {
                onThinking: (text) => {
                    thinkingText = text;
                    if (!assistantDiv) {
                        this.removeTypingIndicator();
                        assistantDiv = this.createStreamingMessage();
                    }
                    this.updateStreamingThinking(assistantDiv, thinkingText);
                    this.scrollToBottom();
                },
                onChunk: (chunk) => {
                    if (!assistantDiv) {
                        this.removeTypingIndicator();
                        assistantDiv = this.createStreamingMessage();
                    }
                    textContent += chunk;
                    this.updateStreamingText(assistantDiv, textContent, true);
                    this.scrollToBottom();
                },
                onMap: (data) => {
                    mapData = data;
                    if (this.app && this.app.mapPanel) {
                        this.app.mapPanel.renderMap(mapData);
                    }
                },
                onSteps: (steps) => {
                    stepsData = steps;
                    if (assistantDiv) {
                        this.updateStreamingSteps(assistantDiv, stepsData);
                        this.scrollToBottom();
                    }
                },
                onRag: (sources) => {
                    ragSources = sources;
                },
                onGraphrag: (data) => {
                    graphragEntities = data.entities || [];
                },
                onGeotoken: (info) => {
                    geotokenInfo = info;
                },
                onKnowledgeSources: (sources) => {
                    knowledgeSources = sources;
                },
                onDone: (data) => {
                    provider = data.provider || "";
                    model = data.model || "";
                },
                onError: (msg) => {
                    throw new Error(msg);
                }
            });

            // 流式结束后，如果还没有创建消息（比如只有map没有chunk），创建一个
            if (!assistantDiv) {
                this.removeTypingIndicator();
            }

            // 如果没有文本但有地图数据，使用默认文本
            if (!textContent && mapData) {
                textContent = "地图已生成，请查看右侧地图面板。";
            }
            if (!textContent && !mapData) {
                textContent = "处理完成。";
            }

            // 完成流式消息：移除光标、添加知识来源和GeoToken卡片
            if (assistantDiv) {
                this.finalizeStreamingMessage(assistantDiv, {
                    content: textContent,
                    thinking: thinkingText,
                    steps: stepsData,
                    map_data: mapData,
                    geotoken_info: geotokenInfo,
                    rag_sources: ragSources,
                    graphrag_entities: graphragEntities,
                    knowledge_sources: knowledgeSources,
                    provider,
                    model,
                });
            } else {
                // 没有收到任何流式数据，直接渲染完整消息
                const assistantMsg = {
                    role: "assistant",
                    content: textContent,
                    thinking: thinkingText,
                    steps: stepsData,
                    map_data: mapData,
                    geotoken_info: geotokenInfo,
                    rag_sources: ragSources,
                    knowledge_sources: knowledgeSources,
                    timestamp: Date.now() / 1000,
                    provider,
                    model,
                };
                this.messages.push(assistantMsg);
                this.addMessage("assistant", assistantMsg.content, assistantMsg);
            }

            // 添加到消息列表
            if (assistantDiv) {
                this.messages.push({
                    role: "assistant",
                    content: textContent,
                    thinking: thinkingText,
                    steps: stepsData,
                    map_data: mapData,
                    geotoken_info: geotokenInfo,
                    rag_sources: ragSources,
                    knowledge_sources: knowledgeSources,
                    timestamp: Date.now() / 1000,
                    provider,
                    model,
                });
            }

            // 如果是第一条消息，更新会话标题
            if (this.messages.length === 2) {
                const title = Utils.generateSessionTitle(message);
                this.updateSessionTitle(this.currentSessionId, title);
            }

        } catch (error) {
            this.removeTypingIndicator();
            if (assistantDiv) {
                assistantDiv.remove();
            }
            this.addMessage("assistant", "抱歉，处理时出现错误: " + error.message, { timestamp: Date.now() / 1000 });
            Utils.showToast("发送消息失败: " + error.message, "error");
        } finally {
            this.isSending = false;
            this.updateSendButton();
        }
    }

    /**
     * 创建流式消息容器（空内容的助手消息气泡）
     * @returns {HTMLElement} 消息DOM元素
     */
    createStreamingMessage() {
        const container = this.elements.messageList;
        const msgDiv = document.createElement("div");
        msgDiv.className = "message message-assistant streaming";
        msgDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="message-body">
                <div class="message-meta">
                    <span class="message-role">智能体</span>
                    <span class="message-time">${Utils.formatTime(Date.now() / 1000)}</span>
                </div>
                <div class="streaming-content"></div>
            </div>
        `;
        container.appendChild(msgDiv);
        return msgDiv;
    }

    /**
     * 更新流式消息的思考过程面板
     */
    updateStreamingThinking(msgDiv, text) {
        const contentDiv = msgDiv.querySelector(".streaming-content");
        let panel = contentDiv.querySelector(".thinking-panel");
        if (!panel) {
            panel = document.createElement("div");
            panel.className = "thinking-panel expanded";
            panel.innerHTML = `
                <div class="thinking-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <i class="fa-solid fa-brain"></i>
                    <span>思考过程</span>
                    <i class="fa-solid fa-chevron-down thinking-arrow"></i>
                </div>
                <div class="thinking-body"></div>
            `;
            contentDiv.insertBefore(panel, contentDiv.firstChild);
        }
        panel.querySelector(".thinking-body").textContent = text;
    }

    /**
     * 更新流式消息的执行步骤面板
     */
    updateStreamingSteps(msgDiv, steps) {
        const contentDiv = msgDiv.querySelector(".streaming-content");
        let panel = contentDiv.querySelector(".steps-panel");
        if (!panel) {
            panel = document.createElement("div");
            panel.className = "steps-panel";
            contentDiv.insertBefore(panel, contentDiv.firstChild.nextSibling || contentDiv.firstChild);
        }
        const statusIcon = {
            pending: "fa-clock",
            running: "fa-spinner fa-spin",
            success: "fa-circle-check",
            failed: "fa-circle-xmark"
        };
        panel.innerHTML = steps.map(step => `
            <div class="step-item step-${step.status || "pending"}">
                <i class="fa-solid ${statusIcon[step.status] || statusIcon.pending}"></i>
                <div class="step-info">
                    <span class="step-name">${Utils.escapeHtml(step.name || step.step_id)}</span>
                    <span class="step-desc">${Utils.escapeHtml(step.description || "")}</span>
                </div>
            </div>
        `).join("");
    }

    /**
     * 更新流式消息的正文（带光标动画）
     */
    updateStreamingText(msgDiv, text, isStreaming) {
        const contentDiv = msgDiv.querySelector(".streaming-content");
        let textDiv = contentDiv.querySelector(".message-text");
        if (!textDiv) {
            textDiv = document.createElement("div");
            textDiv.className = "message-text";
            contentDiv.appendChild(textDiv);
        }
        textDiv.innerHTML = Utils.renderMarkdown(text) + (isStreaming ? '<span class="streaming-cursor"></span>' : "");
    }

    /**
     * 完成流式消息：移除光标，添加知识来源、GeoToken、地图链接、模型信息
     */
    finalizeStreamingMessage(msgDiv, data) {
        const contentDiv = msgDiv.querySelector(".streaming-content");

        // 移除流式光标
        const cursor = contentDiv.querySelector(".streaming-cursor");
        if (cursor) cursor.remove();

        // 渲染最终正文（确保Markdown完整渲染）
        let textDiv = contentDiv.querySelector(".message-text");
        if (!textDiv) {
            textDiv = document.createElement("div");
            textDiv.className = "message-text";
            contentDiv.appendChild(textDiv);
        }
        // 如果有GeoToken信息，对长文本做精简处理：截断冗余图层罗列
        let displayContent = data.content || "";
        if (data.geotoken_info && data.geotoken_info.layer_count > 0 && displayContent.length > 200) {
            // 如果回复中包含冗长的图层列表（如"地图包含"后面跟着很长的罗列），自动精简
            const truncatePatterns = [
                /(地图包含[^。\n]{100,})/,
                /(图层包括[^。\n]{100,})/,
                /(包含以下图层[^。\n]{100,})/,
            ];
            for (const pattern of truncatePatterns) {
                displayContent = displayContent.replace(pattern, (match) => {
                    return match.substring(0, 80) + '...（完整图层信息见下方统计卡片）';
                });
            }
        }
        textDiv.innerHTML = Utils.renderMarkdown(displayContent);

        // 折叠思考过程面板
        const thinkingPanel = contentDiv.querySelector(".thinking-panel");
        if (thinkingPanel) {
            thinkingPanel.classList.remove("expanded");
        }

        // 添加知识来源卡片（问答场景）
        if (data.knowledge_sources && (data.knowledge_sources.rag?.length || data.knowledge_sources.graphrag?.entities?.length)) {
            const sourcesHtml = this.renderKnowledgeSourcesHtml(data.knowledge_sources);
            contentDiv.insertAdjacentHTML("beforeend", sourcesHtml);
        }

        // 添加RAG知识来源（制图场景）
        if (data.rag_sources && data.rag_sources.length > 0 && !data.knowledge_sources.rag?.length) {
            const ragHtml = this.renderRagSourcesHtml(data.rag_sources);
            contentDiv.insertAdjacentHTML("beforeend", ragHtml);
        }

        // 添加GraphRAG实体标签（制图场景）
        if (data.graphrag_entities && data.graphrag_entities.length > 0) {
            const graphragHtml = this.renderGraphragEntitiesHtml(data.graphrag_entities);
            contentDiv.insertAdjacentHTML("beforeend", graphragHtml);
        }

        // 添加GeoToken信息卡片
        if (data.geotoken_info && data.geotoken_info.layer_count > 0) {
            const geoHtml = this.renderGeotokenHtml(data.geotoken_info);
            contentDiv.insertAdjacentHTML("beforeend", geoHtml);
        }

        // 添加地图链接
        if (data.map_data) {
            const mapName = data.map_data.name || "地图";
            const mapLinkHtml = `
                <div class="message-map-link" data-has-map="true">
                    <i class="fa-solid fa-map"></i>
                    <span>查看地图: ${Utils.escapeHtml(mapName)}</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </div>
            `;
            contentDiv.insertAdjacentHTML("beforeend", mapLinkHtml);

            // 绑定点击事件
            const mapLink = contentDiv.querySelector(".message-map-link[data-has-map]");
            if (mapLink) {
                const mapData = data.map_data;
                mapLink.addEventListener("click", () => {
                    if (this.app && this.app.mapPanel) {
                        this.app.mapPanel.renderMap(mapData);
                    }
                });
            }
        }

        // 添加模型信息footer
        if (data.provider) {
            const footerHtml = `
                <div class="message-footer">
                    <span class="message-model">
                        <i class="fa-solid fa-microchip"></i>
                        ${Utils.escapeHtml(data.provider)}${data.model ? " / " + Utils.escapeHtml(data.model) : ""}
                    </span>
                </div>
            `;
            contentDiv.insertAdjacentHTML("beforeend", footerHtml);
        }

        // 移除streaming标记
        msgDiv.classList.remove("streaming");
        this.scrollToBottom();
    }

    /**
     * 渲染知识来源卡片HTML（问答场景，含RAG+GraphRAG+KG）
     */
    renderKnowledgeSourcesHtml(sources) {
        let html = '<div class="knowledge-sources-card">';
        html += '<div class="ks-header"><i class="fa-solid fa-book-open"></i> <span>知识来源</span></div>';

        // RAG来源
        if (sources.rag && sources.rag.length > 0) {
            html += '<div class="ks-section"><div class="ks-section-title">RAG检索</div>';
            sources.rag.forEach(item => {
                html += `<div class="ks-item ks-rag">
                    <span class="ks-badge">RAG</span>
                    <span class="ks-title">${Utils.escapeHtml(item.title)}</span>
                    <span class="ks-score">${item.score ? (item.score * 100).toFixed(0) + "%" : ""}</span>
                </div>`;
            });
            html += '</div>';
        }

        // GraphRAG实体
        if (sources.graphrag && sources.graphrag.entities && sources.graphrag.entities.length > 0) {
            html += '<div class="ks-section"><div class="ks-section-title">GraphRAG实体</div>';
            sources.graphrag.entities.forEach(e => {
                html += `<span class="ks-tag ks-graphrag">${Utils.escapeHtml(e)}</span>`;
            });
            html += '</div>';
        }

        // KG答案
        if (sources.kg_answer) {
            html += `<div class="ks-section"><div class="ks-section-title">知识图谱</div>`;
            html += `<div class="ks-item ks-kg"><span class="ks-badge">KG</span><span class="ks-title">${Utils.escapeHtml(sources.kg_answer.substring(0, 100))}...</span></div>`;
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    /**
     * 渲染RAG知识来源卡片HTML（制图场景）
     */
    renderRagSourcesHtml(sources) {
        let html = '<div class="knowledge-sources-card compact">';
        html += '<div class="ks-header"><i class="fa-solid fa-book-open"></i> <span>制图规范参考</span></div>';
        sources.forEach(item => {
            html += `<div class="ks-item ks-rag">
                <span class="ks-badge">RAG</span>
                <span class="ks-title">${Utils.escapeHtml(item.title)}</span>
            </div>`;
        });
        html += '</div>';
        return html;
    }

    /**
     * 渲染GraphRAG实体标签HTML
     */
    renderGraphragEntitiesHtml(entities) {
        let html = '<div class="graphrag-entities-card">';
        html += '<div class="ks-header"><i class="fa-solid fa-diagram-project"></i> <span>GraphRAG检索实体</span></div>';
        html += '<div class="ge-tags">';
        entities.forEach(e => {
            html += `<span class="ks-tag ks-graphrag">${Utils.escapeHtml(e)}</span>`;
        });
        html += '</div></div>';
        return html;
    }

    /**
     * 渲染GeoToken信息卡片HTML
     */
    renderGeotokenHtml(info) {
        const layers = info.layer_details || [];
        const totalElements = info.total_elements || 0;
        const layerCount = info.layer_count || 0;
        const areaKm2 = info.total_area_km2 || 0;

        let html = '<div class="geotoken-card">';
        html += '<div class="gt-header"><i class="fa-solid fa-map"></i> <span>地图统计</span></div>';

        // 卡片式数字概览
        html += '<div class="gt-stat-cards">';
        html += `<div class="gt-stat-card"><span class="gt-card-num">${layerCount}</span><span class="gt-card-label">图层</span></div>`;
        html += `<div class="gt-stat-card"><span class="gt-card-num">${totalElements.toLocaleString()}</span><span class="gt-card-label">要素</span></div>`;
        if (areaKm2 > 0) {
            html += `<div class="gt-stat-card"><span class="gt-card-num">${areaKm2.toFixed(0)}</span><span class="gt-card-label">km²</span></div>`;
        }
        html += '</div>';

        // 可折叠图层详情
        if (layers.length > 0) {
            const detailId = 'gt-detail-' + Date.now();
            html += `<button class="gt-toggle-btn" onclick="
                const d=document.getElementById('${detailId}');
                const btn=this;
                d.classList.toggle('hidden');
                btn.innerHTML=d.classList.contains('hidden')?'<i class=\\'fa-solid fa-chevron-down\\'></i> 查看图层详情':'<i class=\\'fa-solid fa-chevron-up\\'></i> 收起图层详情';
            "><i class="fa-solid fa-chevron-down"></i> 查看图层详情</button>`;
            html += `<div id="${detailId}" class="gt-layer-list hidden">`;
            layers.forEach((l) => {
                html += `<div class="gt-layer-row">`;
                html += `<span class="gt-layer-dot" style="background:${l.color || '#6366f1'}"></span>`;
                html += `<span class="gt-layer-name">${Utils.escapeHtml(l.name || '未命名')}</span>`;
                html += `<span class="gt-layer-count">${(l.element_count || 0).toLocaleString()}个</span>`;
                html += `</div>`;
            });
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    /**
     * 更新发送按钮状态
     */
    updateSendButton() {
        const btn = this.elements.sendBtn;
        if (this.isSending) {
            btn.disabled = true;
            btn.innerHTML = '<div class="btn-spinner"></div>';
        } else {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i>';
        }
    }

    /**
     * 更新会话标题（UI层面）
     * @param {string} sessionId - 会话ID
     * @param {string} title - 新标题
     */
    async updateSessionTitle(sessionId, title) {
        const session = this.sessions.find(s => s.session_id === sessionId);
        if (session) {
            session.title = title;
            this.renderSessionList();
            // 持久化到后端
            try {
                const sessionData = await API.getSession(sessionId);
                if (sessionData && sessionData.data) {
                    // 更新会话标题（通过获取会话详情后更新）
                    // 后端暂无专门的更新标题API，使用session数据保存机制
                }
            } catch (e) {
                console.warn("会话标题持久化失败:", e);
            }
        }
    }

    /**
     * 滚动消息列表到底部
     */
    scrollToBottom() {
        const container = this.elements.messageList;
        container.scrollTop = container.scrollHeight;
    }

    /**
     * 清空当前会话并开始新对话
     */
    clearMessages() {
        this.messages = [];
        this.renderMessageList();
    }
}
