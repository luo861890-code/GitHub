# 系统设置 API

> 前缀：`/api/settings`
> 源码：`backend/app/api/settings.py`

## 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取全局设置 |
| PUT | `/` | 更新全局设置 |
| GET | `/llm/providers` | 获取 LLM 提供商列表 |
| PUT | `/llm/provider` | 设置当前 LLM 提供商 |
| PUT | `/llm/apikey` | 更新 API Key |
| GET | `/llm/models` | 获取可用模型列表 |
| GET | `/map/themes` | 获取地图主题列表 |

---

## 1. 获取全局设置

**GET** `/api/settings/`

### 响应

```json
{
  "code": 0,
  "data": {
    "app": {
      "name": "CartoAgent",
      "version": "0.1.0",
      "debug": true,
      "language": "zh-CN"
    },
    "llm": {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com",
      "temperature": 0.7,
      "max_tokens": 4096
    },
    "knowledge": {
      "enabled": true,
      "backend": "local",
      "neo4j_uri": "bolt://localhost:7687"
    },
    "map": {
      "default_center": [30.59, 114.30],
      "default_zoom": 11,
      "default_crs": "EPSG:4326",
      "export_formats": ["json", "geojson", "shp"]
    },
    "storage": {
      "data_dir": "../data",
      "osm_cache_ttl": 86400,
      "max_map_layers": 50
    }
  }
}
```

---

## 2. 更新全局设置

**PUT** `/api/settings/`

### 请求体

```json
{
  "app": {
    "debug": false,
    "language": "zh-CN"
  },
  "llm": {
    "temperature": 0.5,
    "max_tokens": 8192
  },
  "map": {
    "default_zoom": 12
  }
}
```

> 只传需要更新的字段，未传字段保持不变。

### 响应

```json
{
  "code": 0,
  "message": "设置已更新",
  "data": { ... }
}
```

---

## 3. 获取 LLM 提供商列表

**GET** `/api/settings/llm/providers`

### 响应

```json
{
  "code": 0,
  "data": {
    "providers": [
      {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "configured": true
      },
      {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "configured": false
      },
      {
        "id": "qwen",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo"],
        "configured": false
      }
    ],
    "current": "deepseek"
  }
}
```

---

## 4. 设置当前 LLM 提供商

**PUT** `/api/settings/llm/provider`

### 请求体

```json
{
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat"
}
```

---

## 5. 更新 API Key

**PUT** `/api/settings/llm/apikey`

更新 LLM API Key（加密存储）。

### 请求体

```json
{
  "provider": "deepseek",
  "api_key": "sk-your-api-key-here"
}
```

### 响应

```json
{
  "code": 0,
  "message": "API Key 已更新",
  "data": {
    "provider": "deepseek",
    "key_masked": "sk-...f7a9"
  }
}
```

> 响应中只返回脱敏后的 Key，不会返回完整 Key。

---

## 6. 获取可用模型列表

**GET** `/api/settings/llm/models`

获取当前提供商下可用的模型列表。

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| provider | string | 提供商 ID（不传则用当前提供商） |

### 响应

```json
{
  "code": 0,
  "data": {
    "provider": "deepseek",
    "models": [
      {
        "id": "deepseek-chat",
        "name": "DeepSeek Chat",
        "context_window": 65536,
        "max_output": 8192,
        "description": "通用对话模型，适合日常问答和代码生成"
      },
      {
        "id": "deepseek-reasoner",
        "name": "DeepSeek Reasoner",
        "context_window": 65536,
        "max_output": 16384,
        "description": "推理模型，适合复杂逻辑和数学问题"
      }
    ]
  }
}
```

---

## 7. 获取地图主题列表

**GET** `/api/settings/map/themes`

获取可用的地图配色主题。

### 响应

```json
{
  "code": 0,
  "data": {
    "themes": [
      {
        "id": "light",
        "name": "浅色",
        "background": "#FFFFFF",
        "text_color": "#333333",
        "description": "适合屏幕显示和打印"
      },
      {
        "id": "dark",
        "name": "深色",
        "background": "#1a1a2e",
        "text_color": "#EEEEEE",
        "description": "适合夜间使用和大屏展示"
      },
      {
        "id": "print",
        "name": "打印友好",
        "background": "#FFFFFF",
        "text_color": "#000000",
        "description": "高对比度，适合打印输出"
      },
      {
        "id": "colorblind",
        "name": "色盲友好",
        "background": "#F5F5F5",
        "text_color": "#333333",
        "description": "使用色盲安全配色方案"
      }
    ],
    "current": "light"
  }
}
```

---

## 配置文件说明

系统设置同时支持环境变量（`backend/.env`）和 API 动态配置。

### 环境变量优先级

1. API 动态设置（运行时，优先级最高）
2. 环境变量（`.env` 文件）
3. 默认值

### 主要环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | https://api.deepseek.com |
| `DEEPSEEK_MODEL` | 默认模型 | deepseek-chat |
| `NEO4J_URI` | Neo4j 连接地址 | bolt://localhost:7687 |
| `NEO4J_USER` | Neo4j 用户名 | neo4j |
| `NEO4J_PASSWORD` | Neo4j 密码 | - |
| `HOST` | 服务监听地址 | 0.0.0.0 |
| `PORT` | 服务端口 | 8080 |
| `DEBUG` | 调试模式 | true |
| `API_TOKEN` | API 认证 Token | -（不设置则不启用认证） |
