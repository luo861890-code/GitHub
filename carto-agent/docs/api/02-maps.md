# 地图管理 API

> 前缀：`/api/maps`
> 源码：`backend/app/api/maps.py`

## 端点列表

### 地图生成与查询
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 生成地图 |
| GET | `/` | 获取地图列表 |
| GET | `/{map_id}` | 获取地图详情 |
| DELETE | `/{map_id}` | 删除地图 |
| GET | `/wiki` | 地图百科 |
| GET | `/thematic/types` | 专题图类型 |

### 地图操作
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{map_id}/modify` | 修改地图 |
| POST | `/{map_id}/export` | 导出地图 |
| POST | `/{map_id}/cleanup` | 清理地图 |
| POST | `/{map_id}/route` | 路径规划 |
| POST | `/{map_id}/marker` | 添加标记 |

### 图层管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{map_id}/layers` | 添加图层 |
| POST | `/{map_id}/layers/import` | 导入图层 |
| POST | `/{map_id}/layers/reorder` | 图层排序 |
| POST | `/{map_id}/layers/{layer_id}/duplicate` | 复制图层 |
| GET | - | （图层详情包含在地图详情中） |
| PUT | `/{map_id}/layers/{layer_id}` | 更新图层 |
| PATCH | `/{map_id}/layers/{layer_id}` | 部分更新图层 |
| DELETE | `/{map_id}/layers/{layer_id}` | 删除图层 |
| PUT | `/{map_id}/layers/{layer_id}/geometry` | 更新图层几何 |
| PUT | `/{map_id}/layers/{layer_id}/visible` | 切换图层可见性 |

### 样式与视图
| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/{map_id}/view` | 更新视图 |
| PUT | `/{map_id}/theme` | 更新主题 |
| POST | `/{map_id}/style-package` | 应用样式包 |

### 质量评估
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{map_id}/quality` | 地图质量 |
| GET | `/{map_id}/qa` | 地图质检 |
| POST | `/{map_id}/quality/accept` | 接受质量 |

---

## 1. 生成地图

**POST** `/api/maps/generate`

根据自然语言描述生成地图。

### 请求体

```json
{
  "prompt": "生成武汉市交通图，道路完整，注记横向",
  "region": "武汉市",
  "map_type": "traffic",
  "options": {
    "include_railway": true,
    "annotation_horizontal": true
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| prompt | string | 是 | 自然语言描述 |
| region | string | 否 | 区域名称 |
| map_type | string | 否 | 地图类型（admin/traffic/water/tour/...） |
| options | object | 否 | 额外选项 |

### 响应

```json
{
  "code": 0,
  "data": {
    "map_id": "map_4a364bba42bb",
    "name": "武汉市交通图",
    "type": "traffic",
    "layers": [...],
    "created_at": "2026-08-30T10:00:00Z"
  }
}
```

---

## 2. 获取地图列表

**GET** `/api/maps/`

### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 返回数量，默认 20 |
| offset | int | 偏移量 |
| type | string | 按类型筛选 |
| keyword | string | 关键词搜索 |

### 响应

```json
{
  "code": 0,
  "data": {
    "maps": [
      {
        "map_id": "map_4a364bba42bb",
        "name": "武汉市交通图",
        "type": "traffic",
        "layer_count": 31,
        "updated_at": "2026-08-30T10:30:00Z"
      }
    ],
    "total": 1
  }
}
```

---

## 3. 获取地图详情

**GET** `/api/maps/{map_id}`

返回完整的地图数据，包括所有图层、样式、注记。

### 响应

```json
{
  "code": 0,
  "data": {
    "map_id": "map_4a364bba42bb",
    "name": "武汉市交通图",
    "type": "traffic",
    "crs": "EPSG:4326",
    "center": [30.59, 114.30],
    "zoom": 11,
    "layers": [
      {
        "id": "layer_001",
        "name": "道路-高速公路",
        "type": "line",
        "visible": true,
        "style": {"color": "#FF0000", "weight": 4},
        "coordinates": [[[30.5, 114.3], [30.6, 114.4]]],
        "properties": [...]
      }
    ],
    "created_at": "2026-08-30T10:00:00Z",
    "updated_at": "2026-08-30T10:30:00Z"
  }
}
```

---

## 4. 删除地图

**DELETE** `/api/maps/{map_id}`

---

## 5. 修改地图

**POST** `/api/maps/{map_id}/modify`

通过自然语言指令修改已有地图。

### 请求体

```json
{
  "prompt": "将所有注记改为横向排布，统一底色为浅灰色",
  "auto_apply": true
}
```

### 响应

```json
{
  "code": 0,
  "data": {
    "map_id": "map_4a364bba42bb",
    "modified": true,
    "changes": ["注记方向已改为横向", "底色已统一"],
    "layers": [...]
  }
}
```

---

## 6. 导出地图

**POST** `/api/maps/{map_id}/export`

导出地图为指定格式。

### 请求体

```json
{
  "format": "geojson",
  "layers": ["layer_001", "layer_002"],
  "options": {"crs": "EPSG:4326"}
}
```

| 格式 | 说明 |
|------|------|
| geojson | GeoJSON |
| json | 系统内部 JSON 格式 |
| shp | Shapefile（需要 GDAL） |
| png | 图片（需要前端渲染） |

---

## 7. 清理地图

**POST** `/api/maps/{map_id}/cleanup`

清理地图中的无效数据、重复要素、空图层等。

### 响应

```json
{
  "code": 0,
  "data": {
    "removed_layers": 2,
    "removed_features": 15,
    "fixed_geometry": 3
  }
}
```

---

## 8. 路径规划

**POST** `/api/maps/{map_id}/route`

在地图上进行两点间路径规划。

### 请求体

```json
{
  "start": [30.59, 114.30],
  "end": [30.65, 114.40],
  "mode": "driving"
}
```

---

## 9. 添加标记

**POST** `/api/maps/{map_id}/marker`

在地图上添加点标记。

### 请求体

```json
{
  "lat": 30.59,
  "lng": 114.30,
  "title": "标记点",
  "icon": "default"
}
```

---

## 10. 添加图层

**POST** `/api/maps/{map_id}/layers`

### 请求体

```json
{
  "name": "新图层",
  "type": "point",
  "style": {"color": "#FF0000"},
  "coordinates": [[30.59, 114.30]],
  "properties": [{"name": "点1"}]
}
```

---

## 11. 导入图层

**POST** `/api/maps/{map_id}/layers/import`

从 GeoJSON/SHP 文件导入图层。

### 请求体（multipart/form-data）

| 字段 | 类型 | 说明 |
|------|------|------|
| file | file | 地理数据文件 |
| layer_name | string | 图层名称 |
| target_crs | string | 目标坐标系 |

---

## 12. 图层排序

**POST** `/api/maps/{map_id}/layers/reorder`

### 请求体

```json
{
  "order": ["layer_003", "layer_001", "layer_002"]
}
```

---

## 13. 复制图层

**POST** `/api/maps/{map_id}/layers/{layer_id}/duplicate`

---

## 14. 更新图层

**PUT** `/api/maps/{map_id}/layers/{layer_id}`

全量更新图层（替换整个图层对象）。

---

## 15. 部分更新图层

**PATCH** `/api/maps/{map_id}/layers/{layer_id}`

部分更新图层（只更新指定字段）。

### 请求体

```json
{
  "name": "新名称",
  "visible": false,
  "style": {"color": "#00FF00"}
}
```

---

## 16. 删除图层

**DELETE** `/api/maps/{map_id}/layers/{layer_id}`

---

## 17. 更新图层几何

**PUT** `/api/maps/{map_id}/layers/{layer_id}/geometry`

更新图层的几何坐标（矢量编辑后保存）。

### 请求体

```json
{
  "coordinates": [[[30.5, 114.3], [30.6, 114.4]]],
  "feature_index": 0
}
```

---

## 18. 切换图层可见性

**PUT** `/api/maps/{map_id}/layers/{layer_id}/visible`

### 请求体

```json
{
  "visible": false
}
```

---

## 19. 更新视图

**PUT** `/api/maps/{map_id}/view`

保存地图视图状态（中心点、缩放级别）。

### 请求体

```json
{
  "center": [30.59, 114.30],
  "zoom": 12,
  "bounds": [[30.4, 114.1], [30.8, 114.6]]
}
```

---

## 20. 更新主题

**PUT** `/api/maps/{map_id}/theme`

应用地图主题（配色方案）。

### 请求体

```json
{
  "theme": "light",
  "overrides": {"background": "#F0F0F0"}
}
```

---

## 21. 应用样式包

**POST** `/api/maps/{map_id}/style-package`

批量应用样式配置到多个图层。

### 请求体

```json
{
  "styles": [
    {"layer_id": "layer_001", "style": {"color": "#FF0000"}},
    {"layer_id": "layer_002", "style": {"color": "#00FF00"}}
  ]
}
```

---

## 22. 地图质量

**GET** `/api/maps/{map_id}/quality`

获取地图质量评分。

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
      "symbol": 88
    },
    "issues": [...]
  }
}
```

---

## 23. 地图质检

**GET** `/api/maps/{map_id}/qa`

获取详细的质检报告。

---

## 24. 接受质量

**POST** `/api/maps/{map_id}/quality/accept`

确认接受当前地图质量，关闭质检问题。

---

## 25. 地图百科

**GET** `/api/maps/wiki`

获取地图类型、制图规范等百科信息。

---

## 26. 专题图类型

**GET** `/api/maps/thematic/types`

获取支持的专题图类型列表。

### 响应

```json
{
  "code": 0,
  "data": {
    "types": [
      {"id": "admin", "name": "行政区划图", "description": "..."},
      {"id": "traffic", "name": "交通图", "description": "..."},
      {"id": "water", "name": "水系图", "description": "..."},
      {"id": "tour", "name": "旅游图", "description": "..."},
      {"id": "medical", "name": "医疗资源图", "description": "..."},
      {"id": "education", "name": "教育资源图", "description": "..."}
    ]
  }
}
```

---

## 图层数据结构

### 通用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 图层唯一 ID |
| name | string | 图层名称 |
| type | string | 类型：point/line/polygon/textLabel |
| visible | boolean | 是否可见 |
| style | object | 样式配置 |
| coordinates | array | 几何坐标 |
| properties | array | 属性数据（与 coordinates 一一对应） |
| min_zoom | int | 最小显示缩放级别 |
| max_zoom | int | 最大显示缩放级别 |

### 样式字段

| 类型 | 字段 |
|------|------|
| point | color, radius, fillColor, weight, opacity |
| line | color, weight, opacity, dashArray, lineCap |
| polygon | fillColor, color, weight, fillOpacity, opacity |
| textLabel | color, fontSize, fontFamily, textDirection, rotation, haloColor, haloWidth |
