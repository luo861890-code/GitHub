# CartoAgent 部署指南

## 1. 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 / Ubuntu 20.04 / macOS 11 | Windows 11 / Ubuntu 22.04 |
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 20+ |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 2GB | 10GB+（含地理数据缓存） |
| 网络 | 可访问外网（OSM/LLM API） | - |

## 2. 快速部署（Windows）

### 2.1 一键启动

```bash
# 克隆或解压项目
cd carto-agent

# 双击运行或命令行执行
start.bat
# 或
powershell -ExecutionPolicy Bypass -File start.ps1
```

脚本会自动完成：
1. 检查 Python 虚拟环境
2. 检查前端依赖
3. 构建前端（如未构建）
4. 启动后端服务
5. 打开浏览器

### 2.2 手动部署

```bash
# 1. 创建并激活 Python 虚拟环境
cd backend
python -m venv .venv
.\.venv\Scripts\activate

# 2. 安装后端依赖
pip install fastapi uvicorn pydantic pydantic-settings python-dotenv
pip install httpx requests shapely pyproj
pip install neo4j  # 可选，使用知识图谱时需要

# 3. 配置环境变量
copy .env.example .env
# 编辑 .env，填入 DeepSeek API Key

# 4. 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# 5. 另开终端，安装前端依赖
cd ../frontend/vue-app
npm install

# 6. 构建前端（生产模式）
npm run build

# 7. 访问
# 前端页面: http://127.0.0.1:8080/app
# API文档:  http://127.0.0.1:8080/docs
```

## 3. Linux/macOS 部署

```bash
# 1. 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # 如有
cp .env.example .env
# 编辑 .env

# 2. 启动后端（生产模式，使用 gunicorn/uvicorn）
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2

# 3. 前端
cd ../frontend/vue-app
npm install
npm run build

# 4. 使用 Nginx 托管前端（可选）
# 将 dist/ 目录配置到 Nginx
# API 请求代理到后端 8080
```

## 4. 环境变量配置

### 4.1 后端配置（backend/.env）

```env
# ===== LLM 配置 =====
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 可选：其他 LLM 提供商
# OPENAI_API_KEY=sk-your-openai-key
# OPENAI_BASE_URL=https://api.openai.com/v1

# ===== Neo4j 配置（可选）=====
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_ENABLED=false  # 设为 true 启用 Neo4j，false 使用本地文件兜底

# ===== 服务配置 =====
HOST=0.0.0.0
PORT=8080
DEBUG=true
LOG_LEVEL=info

# ===== 安全配置（可选）=====
# API_TOKEN=your-secret-token  # 设置后所有 API 需要 Bearer Token
# CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:8080

# ===== 数据配置 =====
DATA_DIR=../data
OSM_CACHE_TTL=86400  # OSM 缓存 TTL（秒）
MAX_MAP_LAYERS=50     # 单地图最大图层数
```

### 4.2 前端配置（frontend/vue-app/.env）

```env
# 开发模式 API 代理
VITE_API_BASE_URL=http://127.0.0.1:8080

# 生产模式 API 地址（构建时注入）
VITE_PROD_API_URL=/api
```

## 5. Docker 部署（可选）

### 5.1 Dockerfile（后端）

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/vue-app/dist/ /app/static/

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 5.2 docker-compose.yml

```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - NEO4J_ENABLED=false
    volumes:
      - ./data:/app/data
      - ./backend/runtime:/app/runtime
    restart: unless-stopped

  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/your-password
    volumes:
      - neo4j_data:/data
    restart: unless-stopped

volumes:
  neo4j_data:
```

## 6. Nginx 反向代理配置（生产环境）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location /app {
        root /var/www/carto-agent/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # 静态资源
    location /static {
        alias /var/www/carto-agent/static;
        expires 30d;
    }
}
```

## 7. 知识图谱部署（可选）

### 7.1 安装 Neo4j

```bash
# Docker 方式（推荐）
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -v neo4j_data:/data \
  neo4j:5

# 访问 http://localhost:7474 确认安装
```

### 7.2 初始化制图知识图谱

```bash
cd backend
.\.venv\Scripts\activate
python -m app.services.kg_service --init
```

### 7.3 启用 Neo4j

在 `backend/.env` 中设置：
```env
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

## 8. 数据备份与恢复

### 8.1 备份

```bash
# 备份地图数据
cp -r data/users/local/maps data/backup/maps_$(date +%Y%m%d)
cp data/users/local/maps.json data/backup/maps_$(date +%Y%m%d).json

# 备份 OSM 缓存
cp backend/runtime/osm_cache.json data/backup/

# 备份会话数据
cp data/users/local/sessions.json data/backup/
```

### 8.2 恢复

```bash
# 恢复地图数据
cp data/backup/maps_20240101.json data/users/local/maps.json
cp -r data/backup/maps_20240101/* data/users/local/maps/

# 重启后端服务
```

## 9. 常见问题

### Q1: 后端启动失败，提示端口被占用
```bash
# Windows: 查找并关闭占用 8080 的进程
netstat -ano | findstr :8080
taskkill /PID <进程ID> /F

# 或修改端口
uvicorn app.main:app --port 9000
```

### Q2: 前端页面空白
- 确认后端已启动：访问 http://127.0.0.1:8080/docs
- 确认前端已构建：检查 `frontend/vue-app/dist/index.html` 是否存在
- 浏览器控制台查看错误信息

### Q3: 智能体回复"请求失败: network error"
- 检查 DeepSeek API Key 是否正确
- 检查网络是否可访问 api.deepseek.com
- 查看后端日志：`backend/runtime/` 或控制台输出

### Q4: 地图生成超时
- OSM 数据获取可能较慢，首次生成需等待
- 检查 OSM 缓存是否正常：`backend/runtime/osm_cache.json`
- 可尝试缩小区域范围或减少图层数量

### Q5: 知识图谱不可用
- 系统默认使用本地文件兜底，无需 Neo4j
- 如需启用 Neo4j，参考第 7 节
- 确认 `.env` 中 `NEO4J_ENABLED=true`

## 10. 性能优化建议

1. **启用 OSM 缓存**：默认已启用，缓存文件在 `backend/runtime/osm_cache.json`
2. **使用 SSD**：地理数据读写频繁，SSD 可显著提升性能
3. **增加内存**：大区域地图生成需要较多内存，建议 8GB+
4. **生产模式**：使用 `--workers 2` 或 gunicorn 启动多进程
5. **CDN 加速**：前端静态资源可配置 CDN
6. **定期清理**：定期清理过期的 OSM 缓存和临时文件
