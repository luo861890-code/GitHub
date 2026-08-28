"""地图API路由 - 地图生成、图层/要素管理与动态修改"""
import asyncio
import json
from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from pydantic import BaseModel, Field
from typing import Optional as Opt, Any

from app.utils.helpers import run_in_thread
from app.api.deps import (
    get_map_service,
    get_agent_service,
    get_export_service,
    get_routing_service,
    get_cleanup_service,
)
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    GenerateMapRequest,
    AddLayerRequest,
    UpdateLayerStyleRequest,
    SetLayerVisibleRequest,
    UpdateViewRequest,
    UpdateThemeRequest,
    AddFeatureRequest,
    ModifyMapRequest,
    ExportMapRequest,
    PlanRouteRequest,
    ApiResponse,
)
from app.services.map_service import MapService
from app.services.agent_service import AgentService
from app.services.export_service import ExportService
from app.services.routing_service import RoutingService
from app.services.cleanup_service import MapCleanupService

router = APIRouter(prefix="/api/maps", tags=["地图"])



@router.get("/wiki", response_model=ApiResponse, summary="百科知识查询（重点建筑简介与图片）")
async def wiki_lookup(name: str = Query(..., description="要查询的建筑/地标名称")):
    """查询建筑/地标的百科简介与图片，用于地图弹窗展示"""
    from app.services.wiki_service import WikiService
    try:
        data = await run_in_thread(WikiService().lookup, name)
        return ApiResponse(success=True, message="百科查询成功" if data.get("found") else "未找到百科词条", data=data)
    except Exception as e:
        return ApiResponse(success=False, message=f"百科查询失败: {e}", data={"name": name, "found": False})

class AddMarkerRequest(BaseModel):
    """自定义标注点请求"""
    name: str = Field(..., min_length=1, max_length=40, description="标注名称")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lng: float = Field(..., ge=-180, le=180, description="经度")
    icon: Opt[str] = Field(default=None, description="象形符号(emoji)")
    color: Opt[str] = Field(default="#e11d48", description="标注颜色")


class UpdateLayerGeometryRequest(BaseModel):
    """编辑模式：整层几何/属性更新请求（QGIS/ArcGIS 式要素编辑保存）"""
    coordinates: Opt[Any] = Field(default=None, description="新的坐标数组（整层替换）")
    properties: Opt[Any] = Field(default=None, description="新的属性数组（整层替换）")
    style: Opt[dict] = Field(default=None, description="新的样式")
    features: Opt[Any] = Field(default=None, description="新的 features 数组（features 型图层）")


class StylePackageRequest(BaseModel):
    """风格包应用请求（计划 3.5）"""
    package: str = Field(..., description="风格包 key：classic/minimal/vintage/dark/academic/handdrawn")


@router.post("/{map_id}/marker", response_model=ApiResponse, summary="添加自定义标注点（答辩演示：标注赏樱点/卫生间等）")
async def add_custom_marker(
    map_id: str,
    request: AddMarkerRequest,
    map_service: MapService = Depends(get_map_service),
):
    """在地图上添加自定义标注点，自动创建/复用"自定义标注"图层"""
    try:
        updated = map_service.add_custom_marker(
            map_id, request.name, request.lat, request.lng, request.icon, request.color
        )
        return ApiResponse(success=True, message=f"已添加标注: {request.name}", data=updated)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e), data=None)


@router.put("/{map_id}/layers/{layer_id}/geometry", response_model=ApiResponse,
            summary="更新图层几何/属性（编辑模式保存）")
async def update_layer_geometry(
    map_id: str,
    layer_id: str,
    request: UpdateLayerGeometryRequest,
    map_service: MapService = Depends(get_map_service),
):
    """编辑模式保存：整层替换坐标/属性/样式（前端编辑几何后回写）"""
    try:
        result = map_service.update_layer_geometry(
            map_id=map_id,
            layer_id=layer_id,
            coordinates=request.coordinates,
            properties=request.properties,
            style=request.style,
            features=request.features,
        )
        return ApiResponse(success=True, message="图层几何已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新图层几何失败: {e}")


@router.put("/{map_id}/layers/{layer_id}/visible", response_model=ApiResponse,
            summary="设置图层可见性（持久化隐藏/显示）")
async def set_layer_visible(
    map_id: str,
    layer_id: str,
    request: SetLayerVisibleRequest,
    map_service: MapService = Depends(get_map_service),
):
    """图层管理：隐藏/显示图层并写入地图数据（QGIS/ArcGIS 式）"""
    try:
        result = map_service.set_layer_visible(map_id, layer_id, request.visible)
        return ApiResponse(success=True, message="图层可见性已更新", data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"设置图层可见性失败: {e}")


@router.get("/thematic/types", response_model=ApiResponse, summary="获取支持的专题地图类型")
async def get_thematic_types():
    """获取系统支持的所有专题地图类型及其渲染配置"""
    from app.core.constants import THEMATIC_MAP_CONFIG
    return ApiResponse(success=True, data=THEMATIC_MAP_CONFIG)

@router.post("/generate", response_model=ApiResponse, summary="生成地图")
async def generate_map(
    request: GenerateMapRequest,
    map_service: MapService = Depends(get_map_service),
):
    """根据地图类型与区域生成地图数据"""
    try:
        result = await run_in_thread(
            map_service.generate_map,
            map_type=request.map_type,
            region=request.region,
            center=request.center,
            zoom=request.zoom,
            layers=request.layers,
        )
        return ApiResponse(success=True, message="地图生成成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图生成失败: {e}")


@router.get("", response_model=ApiResponse, summary="获取地图列表")
@router.get("/", response_model=ApiResponse, include_in_schema=False)
async def list_maps(
    map_service: MapService = Depends(get_map_service),
):
    """获取所有已生成的地图列表"""
    try:
        result = map_service.list_maps()
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取地图列表失败: {e}")


@router.get("/{map_id}/quality", response_model=ApiResponse, summary="地图数据质量检测（拓扑/属性/统计/专题/标注）")
async def map_quality_check(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """对地图数据执行五类质量检测，返回结构化报告（支持前端定位跳转）"""
    try:
        from app.services.quality_service import QualityService
        map_data = map_service.get_map(map_id)
        if not map_data:
            return ApiResponse(success=False, message=f"地图不存在: {map_id}")
        # 质检为 O(n²) 几何计算，放线程池避免阻塞事件循环
        report = await run_in_thread(QualityService().check, map_data)
        return ApiResponse(success=True, message="质量检测完成", data=report)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"质量检测失败: {e}")


@router.get("/{map_id}/qa", response_model=ApiResponse, summary="地图质量验收报告（1000 分制）")
async def map_qa_report(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """对地图生成 1000 分制验收报告（六级评分 + 致命错误门槛 + 问题/缺失清单）"""
    try:
        map_data = map_service.get_map(map_id)
        if not map_data:
            return ApiResponse(success=False, message=f"地图不存在: {map_id}")
        from app.services.map_qa_service import MapQAService
        report = await run_in_thread(MapQAService().generate_report, map_data)
        return ApiResponse(success=True, message="验收报告生成成功", data=report)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"验收报告生成失败: {e}")


@router.get("/{map_id}", response_model=ApiResponse, summary="获取地图数据")
async def get_map(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """获取指定地图的完整数据（含图层、视图、样式等）"""
    try:
        result = map_service.get_map(map_id)
        if result is None:
            return ApiResponse(success=False, message="地图不存在")
        return ApiResponse(success=True, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取地图数据失败: {e}")


@router.delete("/{map_id}", response_model=ApiResponse, summary="删除地图")
async def delete_map(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定地图"""
    try:
        map_service.delete_map(map_id)
        return ApiResponse(success=True, message="地图已删除")
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除地图失败: {e}")


@router.post("/{map_id}/layers", response_model=ApiResponse, summary="添加图层")
async def add_layer(
    map_id: str,
    request: AddLayerRequest,
    map_service: MapService = Depends(get_map_service),
):
    """向指定地图添加新图层（支持OSM自动填充或直接写入坐标/要素数据）"""
    try:
        result = map_service.add_layer(
            map_id=map_id,
            layer_type=request.layer_type,
            name=request.name,
            query=request.query,
            coordinates=request.coordinates,
            properties=request.properties,
            style=request.style,
            features=request.features,
            group=request.group,
        )
        return ApiResponse(success=True, message="图层添加成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"添加图层失败: {e}")


@router.post("/{map_id}/layers/import", response_model=ApiResponse, summary="导入GeoJSON/SHP图层")
async def import_geojson_layer(
    map_id: str,
    file: UploadFile = File(..., description="GeoJSON / SHP(zip) 文件"),
    name: str = Form(..., description="图层名称"),
    layer_type: str = Form("auto", description="auto/point/line/polygon"),
    map_service: MapService = Depends(get_map_service),
):
    """导入用户上传的 GeoJSON / SHP 数据为地图图层

    按文件后缀自动识别：.zip/.shp 走 SHP 导入（含属性表 .dbf），否则按 GeoJSON 导入。
    """
    # 限制上传体积，防止内存/磁盘 DoS
    MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            return ApiResponse(success=False, message="文件过大（上限 20MB）")
        fname = (file.filename or "").lower()
        if fname.endswith(".zip") or fname.endswith(".shp"):
            result = map_service.import_shp_layer(
                map_id=map_id,
                name=name,
                file_bytes=content,
                filename=fname,
            )
            return ApiResponse(success=True, message="SHP 图层导入成功（含属性表）", data=result)
        geojson = json.loads(content.decode("utf-8"))
        result = map_service.import_geojson_layer(
            map_id=map_id,
            name=name,
            geojson=geojson,
            layer_type=layer_type,
        )
        return ApiResponse(success=True, message="GeoJSON 图层导入成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"数据导入失败: {e}")


class ReorderLayersRequest(BaseModel):
    """图层重排请求"""
    layer_ids: list = Field(..., description="按新顺序排列的图层ID列表")


@router.post("/{map_id}/layers/reorder", response_model=ApiResponse,
             summary="调整图层顺序")
async def reorder_layers(
    map_id: str,
    request: ReorderLayersRequest,
    map_service: MapService = Depends(get_map_service),
):
    """按给定顺序重排图层（图层面板“上移/下移”持久化）"""
    try:
        result = map_service.reorder_layers(map_id, request.layer_ids)
        return ApiResponse(success=True, message="图层顺序已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"调整图层顺序失败: {e}")


@router.post("/{map_id}/layers/{layer_id}/duplicate", response_model=ApiResponse,
             summary="复制图层")
async def duplicate_layer(
    map_id: str,
    layer_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """复制指定图层（含几何/属性/样式）"""
    try:
        result = map_service.duplicate_layer(map_id, layer_id)
        return ApiResponse(success=True, message="图层已复制", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"复制图层失败: {e}")


@router.delete("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="删除图层")
async def remove_layer(
    map_id: str,
    layer_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定地图中的某个图层"""
    try:
        result = map_service.remove_layer(map_id=map_id, layer_id=layer_id)
        return ApiResponse(success=True, message="图层已删除", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除图层失败: {e}")


@router.put("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="更新图层样式")
async def update_layer_style(
    map_id: str,
    layer_id: str,
    request: UpdateLayerStyleRequest,
    map_service: MapService = Depends(get_map_service),
):
    """更新指定图层的样式（颜色、线宽、透明度等）"""
    try:
        # 过滤出用户实际提供的样式字段（忽略未传的None值）
        style = {k: v for k, v in request.model_dump().items() if v is not None}
        result = map_service.update_layer_style(
            map_id=map_id,
            layer_id=layer_id,
            style=style,
        )
        return ApiResponse(success=True, message="图层样式已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新图层样式失败: {e}")


@router.patch("/{map_id}/layers/{layer_id}", response_model=ApiResponse, summary="增量更新图层")
async def patch_layer(
    map_id: str,
    layer_id: str,
    request: dict,
    map_service: MapService = Depends(get_map_service),
):
    """增量更新图层 - 仅修改传入的字段，不影响其他属性

    支持的增量操作：
    - style: 部分更新样式（如仅修改color，保留weight/opacity）
    - visible: 切换图层可见性
    - name: 重命名图层
    """
    try:
        # 获取当前地图数据
        map_data = map_service.get_map(map_id)
        if not map_data:
            return ApiResponse(success=False, message="地图不存在")

        # 找到目标图层
        layers = map_data.get("layers", [])
        target_layer = None
        for layer in layers:
            if layer.get("id") == layer_id:
                target_layer = layer
                break

        if not target_layer:
            return ApiResponse(success=False, message=f"图层不存在: {layer_id}")

        # 应用增量更新
        updated = False
        if "style" in request:
            current_style = target_layer.get("style", {})
            current_style.update(request["style"])
            result = map_service.update_layer_style(map_id, layer_id, current_style)
            updated = True

        if "visible" in request:
            target_layer["visible"] = request["visible"]
            updated = True

        if "name" in request:
            target_layer["name"] = request["name"]
            updated = True

        if "group" in request:
            map_service.set_layer_group(map_id, layer_id, request["group"] or None)
            updated = True

        if "opacity" in request:
            target_layer["opacity"] = float(request["opacity"])
            updated = True

        if "crs" in request:
            target_layer["crs"] = str(request["crs"])
            updated = True

        if not updated:
            return ApiResponse(success=False, message="未提供有效的更新字段")

        # 返回更新后的地图数据
        updated_map = map_service.get_map(map_id)
        return ApiResponse(success=True, message="图层已增量更新", data=updated_map)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"增量更新失败: {e}")


@router.put("/{map_id}/view", response_model=ApiResponse, summary="更新地图视图")
async def update_view(
    map_id: str,
    request: UpdateViewRequest,
    map_service: MapService = Depends(get_map_service),
):
    """更新地图中心点与缩放级别"""
    try:
        result = map_service.update_view(
            map_id=map_id,
            center=request.center,
            zoom=request.zoom,
        )
        return ApiResponse(success=True, message="地图视图已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新地图视图失败: {e}")


@router.put("/{map_id}/theme", response_model=ApiResponse, summary="更新地图主题")
async def update_theme(
    map_id: str,
    request: UpdateThemeRequest,
    map_service: MapService = Depends(get_map_service),
):
    """切换地图底图主题（标准/浅色/深色/卫星）"""
    try:
        result = map_service.update_theme(map_id=map_id, theme=request.theme)
        return ApiResponse(success=True, message="地图主题已更新", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"更新地图主题失败: {e}")


@router.post("/{map_id}/style-package", response_model=ApiResponse, summary="应用地图风格包")
async def apply_style_package(
    map_id: str,
    request: StylePackageRequest,
    map_service: MapService = Depends(get_map_service),
):
    """按风格包统一调整地图配色（经典/简约/复古/暗黑/学术/手绘）"""
    try:
        result = map_service.apply_style_package(map_id, request.package)
        return ApiResponse(success=True, message=f"风格包 {request.package} 已应用", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"应用风格包失败: {e}")


@router.post(
    "/{map_id}/layers/{layer_id}/features",
    response_model=ApiResponse,
    summary="添加要素",
)
async def add_feature(
    map_id: str,
    layer_id: str,
    request: AddFeatureRequest,
    map_service: MapService = Depends(get_map_service),
):
    """向指定图层添加地理要素（标注点/线/面）"""
    try:
        result = map_service.add_feature(
            map_id=map_id,
            layer_id=layer_id,
            feature_type=request.feature_type,
            coordinates=request.coordinates,
            properties=request.properties,
        )
        return ApiResponse(success=True, message="要素添加成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"添加要素失败: {e}")


@router.delete(
    "/{map_id}/layers/{layer_id}/features/{feature_id}",
    response_model=ApiResponse,
    summary="删除要素",
)
async def remove_feature(
    map_id: str,
    layer_id: str,
    feature_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """删除指定图层中的某个地理要素"""
    try:
        result = map_service.remove_feature(
            map_id=map_id,
            layer_id=layer_id,
            feature_id=feature_id,
        )
        return ApiResponse(success=True, message="要素已删除", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除要素失败: {e}")


@router.post("/{map_id}/quality/accept", response_model=ApiResponse,
             summary="接受质量检测结果")
async def accept_quality(
    map_id: str,
    map_service: MapService = Depends(get_map_service),
):
    """人工接受质量检测结果，写入编制说明（质检结论/时间）"""
    try:
        result = map_service.accept_quality(map_id)
        return ApiResponse(success=True, message="质量结果已接受", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"接受质量结果失败: {e}")


@router.post("/{map_id}/modify", response_model=ApiResponse, summary="自然语言修改地图")
async def modify_map(
    map_id: str,
    request: ModifyMapRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """通过自然语言指令动态修改已有地图

    示例指令："把道路颜色改成红色"、"添加武汉大学周边的餐饮点"
    """
    try:
        result = await run_in_thread(
            agent_service.modify_map,
            instruction=request.instruction,
            map_id=map_id,
        )
        return ApiResponse(success=True, message="地图修改完成", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图修改失败: {e}")


@router.post("/{map_id}/export", response_model=ApiResponse, summary="导出地图")
async def export_map(
    map_id: str,
    request: ExportMapRequest,
    map_service: MapService = Depends(get_map_service),
    export_service: ExportService = Depends(get_export_service),
):
    """将指定地图导出为 GeoJSON / SVG / PNG / SHP 格式"""
    try:
        # 先获取地图数据
        map_data = map_service.get_map(map_id)
        if map_data is None:
            return ApiResponse(success=False, message="地图不存在")

        fmt = request.format.lower()
        if fmt not in ("geojson", "svg", "png", "shp"):
            return ApiResponse(success=False, message=f"不支持的导出格式: {fmt}")

        # 重活（Pillow 渲染 / SVG/JSON 序列化 / shp 打包）在线程池执行，避免阻塞事件循环
        def _do_export():
            if fmt == "geojson":
                return export_service.export_geojson(map_data)
            if fmt == "svg":
                return export_service.export_svg(map_data)
            if fmt == "shp":
                return export_service.export_shp_zip(map_data)
            if request.layout:
                return export_service.export_layout_png(map_data, request.layout)
            return export_service.export_png(map_data)

        result = await run_in_thread(_do_export)

        # shp 二进制 zip 直接返回文件下载（不经 ApiResponse JSON 包装）
        if fmt == "shp":
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(
                content=result,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="map_{map_id}_shp.zip"'},
            )

        return ApiResponse(
            success=True,
            message=f"地图已导出为 {fmt} 格式",
            data=result,
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"地图导出失败: {e}")


class CleanupMapRequest(BaseModel):
    """质量清洗请求"""
    deep: bool = Field(False, description="是否深度清洗（含政区重叠修复/碎面删除）")


@router.post("/{map_id}/cleanup", response_model=ApiResponse, summary="地图几何质量清洗")
async def cleanup_map(
    map_id: str,
    request: CleanupMapRequest,
    map_service: MapService = Depends(get_map_service),
    cleanup_service: MapCleanupService = Depends(get_cleanup_service),
):
    """清洗地图几何硬伤：冗余折点/退化几何/重复要素（始终执行），
    深度模式额外修复区县政区重叠与删除碎面。"""
    try:
        map_data = map_service.get_map(map_id)
        if map_data is None:
            return ApiResponse(success=False, message="地图不存在")

        def _do_cleanup():
            cleaned = cleanup_service.cleanup_map(map_data, deep=request.deep)
            map_service._schedule_save()
            return cleaned

        result = await run_in_thread(_do_cleanup)
        report = result.get("cleanup_report") or {}
        mode = "深度清洗" if request.deep else "基础清洗"
        message = (
            f"{mode}完成：去重 {report.get('dedupe', 0)}、退化 {report.get('degenerate', 0)}、"
            f"折点 {report.get('vertices', 0)}、重叠 {report.get('overlap', 0)}、碎面 {report.get('sliver', 0)}"
        )
        return ApiResponse(success=True, message=message, data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"质量清洗失败: {e}")


@router.post("/{map_id}/route", response_model=ApiResponse, summary="规划路径")
async def plan_route(
    map_id: str,
    request: PlanRouteRequest,
    routing_service: RoutingService = Depends(get_routing_service),
):
    """在指定地图上规划两点之间的路径

    支持驾车(driving)、步行(walking)、骑行(cycling)三种模式，
    可选途经点。返回路径坐标、距离、预计时间及导航步骤。
    """
    try:
        result = await run_in_thread(
            routing_service.plan_route,
            start=request.start,
            end=request.end,
            profile=request.profile,
            waypoints=request.waypoints,
        )
        return ApiResponse(success=True, message="路径规划成功", data=result)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"路径规划失败: {e}")
