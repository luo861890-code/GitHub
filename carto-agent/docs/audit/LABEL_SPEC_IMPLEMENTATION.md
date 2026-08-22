# 地图注记规范落地说明（Label Specification Implementation）

> 对应《地图注记规范》全文（用户提供），集中实现于
> `backend/app/core/label_spec.py`，前端渲染在 `public/legacy/map.js` 与
> `src/components/MapCanvas.vue`。

## 一、注记优先级分级（规范 §二）

| 等级 | 对象 | priority |
|---|--|--:|
| P0 | 市名、核心河流（长江/汉江）、核心交通枢纽（武汉站等） | 100 |
| P1 | 区名、主要道路（高速/干线/主干道）、铁路/轨道、核心景区、大湖 | 80 |
| P2 | 次要道路（次干道）、一般景点、普通地名、小湖/支流 | 50 |
| P3 | 普通 POI、辅助信息 | 20 |

避让规则（规范 §十八）：P0 不得被普通注记压盖；P1 尽量不受影响；
P2 允许移位/缩小；P3 冲突时隐藏。

## 二、字体/字号/字重/字色层级（规范 §十六/§十七）

| 等级 | 字体 | 基准字号 | 字重 | 默认字色 |
|---|--|--:|--:|--|
| P0 | 黑体（black） | 20px | 800 | #1F2937 |
| P1 | 半粗（bold） | 15px | 700 | #1F2937 |
| P2 | 宋体（song） | 12px | 500 | #374151 |
| P3 | 宋体（song） | 10px | 400 | #6B7280 |

要素类别字色覆盖：水系注记 #1E3A8A（蓝）、山峰 #7A5230（棕褐）、
交通注记 #374151（深灰）、旅游 POI #B91C1C（红）。

**高德式水系注记**（参考高德地图样式）：湖泊/河流注记使用
蓝色 #2E6FA3 + 宋体斜体（font-style: italic）+ 白色描边光晕（halo，
`text-shadow: 0 0 2px #fff` 三层），名称水平放置不随湖形旋转；
字重按湖泊等级（P1 大湖 700 / P2 中湖 500）。

字号随比例尺缩放：前端按 zoom 乘以 1.12^(z-12)（范围 0.7~2.2 倍，最小 9px），
同一等级字体完全一致。

## 三、字向（规范 §六）

- 线注记旋转角取沿线中点前后 ±2 点平滑方向，避免局部折角抖动；
- 角度归一化到 [-90,90]：90°<angle<270° 翻转 180°，保证文字从左向右可读；
- 前端再次归一化并加“字头朝上”处理。

## 四、尺度范围（规范 §十）

每个注记带 `scale_range`（分母区间）与 `min_zoom`：

| min_zoom | scale_range | 显示内容 |
|--:|--|--|
| 6 | [1000000, 25000] | 市名（常显） |
| 7 | [1000000, 25000] | 特大型湖泊（≥100km²） |
| 8 | [1000000, 25000] | 区名/大湖（≥30km²，1:100万 起，13 区可识别） |
| 9 | [250000, 25000] | 山峰/轨道（1:25万 起） |
| 10 | [100000, 25000] | 地标/主干道/中型湖泊（≥5km²，1:10万 起） |
| 12 | [100000, 25000] | 小型湖泊/支流（<5km²，1:10万 起） |
| 13/14 | [25000, 25000] | 次干道/支路（1:2.5万） |

湖泊注记按面积分档（`area_km2` 来自本地水系数据，市域裁剪后实际无 ≥100km² 湖）：
实测 z7 仅市名 → z8 大湖 3 个 → z10 中型湖 22 个 → z12 全部 57 个，数量随比例尺逐级递增。

## 五、注记对象结构（规范 §23）

每个注记 properties 包含：`label_id / name / feature_type / priority / anchor
(point|line) / font / size / fontSize / weight / color / scale_range / min_zoom /
importance / rotation / visibility`，前端按属性渲染（字色/字重/字号/字向）。

## 六、质量指标（规范 §24）

`label_metrics` 输出：label_count / suppressed_count / important_label_recall /
label_overlap_rate / label_density / **priority_preservation（P0 保留率，目标 100%）** /
**out_of_bounds_rate（越界率，目标 <1%）** / rejected_out_of_bounds_count（越界拒绝数）。

实测（行政图 1:10万）：important_label_recall=1.0、priority_preservation=1.0、
out_of_bounds_rate=0。

## 七、未实现（如实标注）

- 曲线注记（curved label，沿弯曲河流/道路贴线排布）：PARTIAL
- 要素感知位移（feature-aware displacement）与候选位置评分制：PARTIAL
- 长河/长道路有限重复标注（LabelRepeatPolicy）：未实现（当前整图名称去重一次）
