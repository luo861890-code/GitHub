# 智能体对话 API

> 前缀：`/api/chat`
> 源码：`backend/app/api/chat.py`

## 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sessions` | 创建会话 |
| GET | `/sessions` | 获取会话列表 |
| GET | `/sessions/{session_id}` | 获取会话详情 |
| PUT | `/sessions/{session_id}` | 更新会话 |
| DELETE | `/sessions/{session_id}` | 删除会话 |
| POST | `/sessions/{session_id}/messages` | 发送消息 |
| GET | `/sessions/{session_id}/messages` | 获取消息列表 |
| POST | `/sessions/{session_id}/stream` | 流式对话（SSE） |
| GET | `/evaluation` | 获取评估结果 |

---

## 1. 创建会话

**POST** `/api/chat/sessions`

创建新的智能体对话会话。

### 请求体

```json
{
  "title": "武汉市交通图",
  "map_type": "traffic",
  "region": "武汉市"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 会话标题 |
| map_type | string | 否 | 地图类型 |
| region | string | 否 | 区域 |

### 响应

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_abc123",
    "title": "武汉市交通图",
    "created_at": "2026-08-30T10:00:00Z",
    "messages": []
  }
}
```

---

## 2. 获取会话列表

**GET** `/api/chat/sessions`

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 返回数量，默认 20 |
| offset | int | 偏移量，默认 0 |

### 响应

```json
{
  "code": 0,
  "data": {
    "sessions": [
      {
        "session_id": "sess_abc123",
        "title": "武汉市交通图",
        "updated_at": "2026-08-30T10:30:00Z",
        "message_count": 5
      }
    ],
    "total": 1
  }
}
```

---

## 3. 获取会话详情

**GET** `/api/chat/sessions/{session_id}`

### 路径参数

| 参数 | 说明 |
|------|------|
| session_id | 会话 ID |

### 响应

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_abc123",
    "title": "武汉市交通图",
    "created_at": "2026-08-30T10:00:00Z",
    "messages": [
      {
        "role": "user",
        "content": "生成武汉市交通图",
        "timestamp": "2026-08-30T10:01:00Z"
      },
      {
        "role": "assistant",
        "content": "好的，正在为您生成...",
        "map_id": "map_xxx",
        "timestamp": "2026-08-30T10:02:00Z"
      }
    ]
  }
}
```

---

## 4. 更新会话

**PUT** `/api/chat/sessions/{session_id}`

### 请求体

```json
{
  "title": "新标题"
}
```

---

## 5. 删除会话

**DELETE** `/api/chat/sessions/{session_id}`

### 响应

```json
{
  "code": 0,
  "message": "会话已删除"
}
```

---

## 6. 发送消息

**POST** `/api/chat/sessions/{session_id}/messages`

发送一条消息并获取智能体回复（非流式）。

### 请求体

```json
{
  "content": "生成武汉市交通图，要求道路完整、注记横向",
  "map_id": "map_xxx"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 消息内容 |
| map_id | string | 否 | 关联的地图 ID（修改已有地图时传入） |

### 响应

```json
{
  "code": 0,
  "data": {
    "reply": "已为您生成武汉市交通图...",
    "map_id": "map_xxx",
    "thinking": [
      "用户需要武汉市交通图",
      "从OSM获取道路数据",
      "应用交通图样式",
      "放置注记"
    ]
  }
}
```

---

## 7. 获取消息列表

**GET** `/api/chat/sessions/{session_id}/messages`

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 返回数量 |
| offset | int | 偏移量 |

---

## 8. 流式对话（SSE）

**POST** `/api/chat/sessions/{session_id}/stream`

通过 SSE 流式输出智能体的思考过程、工具调用和地图更新。

### 请求体

```json
{
  "content": "生成武汉市交通图",
  "map_id": null
}
```

### SSE 事件流

```
event: thinking
data: {"content": "解析用户需求：武汉市交通图"}

event: tool_call
data: {"tool": "osm_fetch", "params": {"region": "武汉市", "type": "highway"}}

event: tool_result
data: {"tool": "osm_fetch", "result": {"roads": 4189, "status": "success"}}

event: map_update
data: {"map_id": "map_xxx", "layers": [...]}

event: message
data: {"content": "武汉市交通图已生成完成"}

event: done
data: {"map_id": "map_xxx"}
```

### 事件类型

| 事件 | 说明 |
|------|------|
| `thinking` | 智能体思考过程 |
| `tool_call` | 调用工具 |
| `tool_result` | 工具返回结果 |
| `map_update` | 地图数据更新（增量） |
| `message` | 文本回复 |
| `done` | 任务完成 |
| `error` | 错误信息 |
| `heartbeat` | 心跳（每15秒） |

### JavaScript 调用示例

```javascript
const evtSource = new EventSource(
  `/api/chat/sessions/${sessionId}/stream`,
  { method: 'POST', body: JSON.stringify({ content: '生成地图' }) }
);

evtSource.addEventListener('thinking', (e) => {
  console.log('思考:', JSON.parse(e.data).content);
});

evtSource.addEventListener('map_update', (e) => {
  const mapData = JSON.parse(e.data);
  renderMap(mapData);
});

evtSource.addEventListener('done', () => {
  evtSource.close();
});
```

---

## 9. 获取评估结果

**GET** `/api/chat/evaluation`

获取智能体制图质量评估结果。

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| map_id | string | 地图 ID |

### 响应

```json
{
  "code": 0,
  "data": {
    "score": 85,
    "dimensions": {
      "data_completeness": 90,
      "topology": 80,
      "annotation": 85,
      "symbol_standard": 88
    },
    "issues": [
      {"type": "road_gap", "location": "...", "suggestion": "..."}
    ]
  }
}
```
