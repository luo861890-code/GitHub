# CartoAgent API 文档

> 基于 FastAPI 的 RESTful API，所有接口默认前缀 `/api`
> 运行后可访问交互式文档：http://127.0.0.1:8080/docs

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://127.0.0.1:8080/api` |
| 认证方式 | 可选 Bearer Token（配置 `API_TOKEN` 后启用） |
| 数据格式 | JSON（UTF-8） |
| 流式接口 | SSE（Server-Sent Events） |

## API 分类索引

| 分类 | 文件 | 端点数 | 说明 |
|------|------|--------|------|
| 智能体对话 | [01-agent-chat.md](01-agent-chat.md) | 9 | 会话管理、消息发送、流式对话、评估 |
| 地图管理 | [02-maps.md](02-maps.md) | 28 | 地图生成、CRUD、图层管理、样式、导出、质检 |
| 知识图谱 | [03-knowledge.md](03-knowledge.md) | 18 | 实体/关系管理、图谱查询、RAG、符号推荐、本体 |
| 系统设置 | [04-settings.md](04-settings.md) | 7 | 全局设置、LLM 配置、地图主题 |

## 通用响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 状态码，0 表示成功，非 0 表示错误 |
| message | string | 状态描述 |
| data | object | 响应数据（错误时可能为 null） |

## 错误码

| code | 说明 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 流式接口（SSE）

智能体对话使用 SSE 流式输出，事件类型：

| 事件 | 说明 |
|------|------|
| `thinking` | 智能体思考过程 |
| `tool_call` | 工具调用 |
| `tool_result` | 工具返回结果 |
| `map_update` | 地图数据更新 |
| `message` | 文本消息 |
| `done` | 完成 |
| `error` | 错误 |
| `heartbeat` | 心跳保活 |

## 测试集合

- [carto-agent.http](examples/carto-agent.http) - VS Code REST Client 格式的 API 测试集合

## 快速开始

```bash
# 1. 启动服务
.\start.bat

# 2. 查看交互式文档
# 浏览器打开 http://127.0.0.1:8080/docs

# 3. 测试 API
curl http://127.0.0.1:8080/api/maps/
```
