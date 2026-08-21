# 最终遗留问题（如实标注）

## PARTIAL（未伪实现）

1. LabelEngine 曲线注记（curved label）与要素感知位移（feature-aware displacement）：
   点注记/线注记/碰撞消解已接入渲染链，曲线注记未实现（PARTIAL）。
2. 行政区划数据源 11 处微小 overlap（DataV 边界精度，0.002-0.166 km²）：
   dataset_gate=SOURCE_DATA_WARNING；正式出版需换用民政部权威边界，不伪修复。
3. 铁路 geometry_quality=approximate、source_confidence=unverified（未与官方核验）。

## QA 框架子项（主题规范限制，非错误）

- E7 坍缩层：部分地图类型按 Profile 禁止点状符号坍缩层（如行政图禁止湖泊点符号）。
- F 色彩数量：专题图 >8 主色，符合主题区分需要。
- C3 点归属：无点要素的地图类型（如交通图去点状符号）按规则给 12/20。

## 建议下一步（超出本次收尾范围）

1. LabelEngine 曲线注记（沿弯曲道路/河流贴线排布）+ 行政边界避让。
2. 接入官方铁路/枢纽精确坐标，将 geometry_verified 提升到 1.0。
3. 行政边界 overlap 自动修复（以 13 区官方界线为基准做 snapping/清理）。
4. 自动版式按地图类型切换横/竖幅（当前统一竖版默认）。
