"""对话API路由 - 会话管理与消息交互

提供会话的增删改查以及智能体消息交互能力。
用户发送消息后，由 AgentService 编排 LLM、知识图谱、OSM、地图服务完成制图任务。
支持SSE流式响应，实现LLM输出的实时推送。
"""
import asyncio
import json
import threading
import time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_session_service, get_agent_service, get_llm_service, get_evaluation_service,
    get_map_service,
)
from app.core.exceptions import CartoAgentError
from app.models.schemas import (
    CreateSessionRequest,
    RenameSessionRequest,
    SendMessageRequest,
    ApiResponse,
)
from app.services.session_service import SessionService
from app.services.agent_service import AgentService
from app.services.llm_service import LLMService
from app.services.evaluation_service import EvaluationService
from app.services.map_service import MapService
from app.utils.helpers import safe_json_loads, get_timestamp, run_in_thread
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["对话"])


def _sanitize(obj):
    """递归将 NaN/Infinity 转为 None，并把 pydantic 模型/其他非标准对象转为可 JSON 序列化的结构。

    Python json.dumps 默认把 float('nan')/float('inf') 序列化为非标准的 NaN/Infinity，
    而 JS 的 JSON.parse 严格拒绝这些 token（SyntaxError），会导致 map 事件解析失败、
    前端 onMap 不触发、地图不渲染。此函数在序列化前兜底清洗。
    同时把 pydantic BaseModel（如 AgentStep）转为 dict，避免 SSE 序列化抛
    "Object of type AgentStep is not JSON serializable" 导致整条流以 error 结束、
    前端看不到智能体回复。
    """
    # pydantic v2 模型
    if hasattr(obj, "model_dump"):
        try:
            return _sanitize(obj.model_dump())
        except Exception:
            pass
    # pydantic v1 模型
    if hasattr(obj, "dict") and not isinstance(obj, dict):
        try:
            return _sanitize(obj.dict())
        except Exception:
            pass
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    # 其他不可序列化对象（dataclass 等）转 str 兜底
    if not isinstance(obj, (str, int, bool, type(None))):
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)
    return obj


def _sse_json(data) -> str:
    """带 NaN 清洗与模型转义的 JSON 序列化，用于 SSE 事件推送"""
    return json.dumps(_sanitize(data), ensure_ascii=False)


@router.post("/sessions", response_model=ApiResponse, summary="创建会话")
async def create_session(
    request: CreateSessionRequest,
    session_service: SessionService = Depends(get_session_service),
):
    """创建一个新的对话会话"""
    try:
        session = session_service.create_session(title=request.title)
        return ApiResponse(success=True, message="会话创建成功", data=session)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"创建会话失败: {e}")


@router.get("/sessions", response_model=ApiResponse, summary="获取会话列表")
async def list_sessions(
    session_service: SessionService = Depends(get_session_service),
):
    """获取所有会话列表"""
    try:
        sessions = session_service.list_sessions()
        return ApiResponse(success=True, data=sessions)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取会话列表失败: {e}")


@router.get("/sessions/{session_id}", response_model=ApiResponse, summary="获取会话详情")
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """获取指定会话的完整信息（含历史消息）"""
    try:
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")
        return ApiResponse(success=True, data=session)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取会话详情失败: {e}")


@router.delete("/sessions/{session_id}", response_model=ApiResponse, summary="删除会话")
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """删除指定会话及其所有消息"""
    try:
        session_service.delete_session(session_id)
        return ApiResponse(success=True, message="会话已删除")
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"删除会话失败: {e}")


@router.put("/sessions/{session_id}", response_model=ApiResponse, summary="重命名会话")
async def rename_session(
    session_id: str,
    request: RenameSessionRequest,
    session_service: SessionService = Depends(get_session_service),
):
    """重命名会话（会话抽屉双击标题触发）"""
    try:
        session = session_service.rename_session(session_id, request.title)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")
        return ApiResponse(
            success=True,
            message="会话已重命名",
            data={"session_id": session.session_id, "title": session.title},
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"重命名会话失败: {e}")


@router.post("/sessions/{session_id}/messages", response_model=ApiResponse, summary="发送消息")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    session_service: SessionService = Depends(get_session_service),
    agent_service: AgentService = Depends(get_agent_service),
    evaluation_service: EvaluationService = Depends(get_evaluation_service),
):
    """发送消息并获取智能体响应

    流程：
    1. 先将用户消息保存到会话历史
    2. 调用 AgentService.process_request 编排制图流程
    3. 将智能体响应（含地图数据、步骤、思考过程）保存到会话历史
    4. 返回完整响应结果
    """
    try:
        # 校验会话是否存在
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")

        # 保存用户消息
        session_service.add_message(
            session_id=session_id,
            role="user",
            content=request.message,
        )

        # 调用智能体处理用户请求（在线程池中运行以避免阻塞事件循环）
        # 记录端到端延迟，供实证驱动评估系统使用
        _t0 = time.monotonic()
        result = await run_in_thread(
            agent_service.process_request,
            message=request.message,
            session_id=session_id,
            map_id=request.map_id,
        )
        _latency_ms = (time.monotonic() - _t0) * 1000.0

        # 实证驱动评估埋点：记录任务完成率/端到端延迟/场景
        _map_data = result.get("map_data") or {}
        try:
            evaluation_service.record(
                message=request.message,
                success=result.get("success", True),
                latency_ms=_latency_ms,
                map_id=_map_data.get("map_id"),
                map_name=_map_data.get("name"),
                map_type=_map_data.get("map_type"),
            )
        except Exception as _e:
            pass  # 评估埋点失败不影响主流程

        # 保存助手响应消息（含地图数据、执行步骤、思考过程）
        session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=result.get("response", ""),
            map_data=result.get("map_data"),
            steps=result.get("steps"),
            thinking=result.get("thinking"),
        )

        return ApiResponse(
            success=result.get("success", True),
            message="消息处理完成",
            data={
                "response": result.get("response", ""),
                "map_data": result.get("map_data"),
                "steps": result.get("steps"),
                "thinking": result.get("thinking"),
                "provider": result.get("provider"),
                "model": result.get("model"),
                # 增强数据
                "geotoken_info": result.get("geotoken_info", {}),
                "rag_sources": result.get("rag_sources", []),
                "graphrag_entities": result.get("graphrag_entities", []),
                "knowledge_sources": result.get("knowledge_sources", {}),
            },
        )
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"消息处理失败: {e}")


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse, summary="获取历史消息")
async def get_messages(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """获取指定会话的全部历史消息"""
    try:
        session = session_service.get_session(session_id)
        if session is None:
            return ApiResponse(success=False, message="会话不存在")
        # 兼容 Session 对象与字典两种返回形式
        messages = getattr(session, "messages", None)
        if messages is None and isinstance(session, dict):
            messages = session.get("messages", [])
        return ApiResponse(success=True, data=messages)
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"获取历史消息失败: {e}")


@router.get("/evaluation", response_model=ApiResponse, summary="实证驱动评估统计（完成率/延迟/规范性5分制）")
async def evaluation_stats(
    evaluation_service: EvaluationService = Depends(get_evaluation_service),
    map_service: MapService = Depends(get_map_service),
):
    """获取智能体任务评估统计（申报书"实证驱动"）

    返回：任务完成率、端到端延迟（平均/最大/中位）、规范性 5 分制
    （基于最新地图的 QA 1000 分制报告映射）、三场景（基础/核心/压力）分组、
    近 10 条任务趋势。
    """
    try:
        # 规范性 5 分制：对最新一张地图实时生成 QA 报告（1000 分制 → /200）
        normativity = None
        latest_map = map_service.get_latest_map()
        if latest_map:
            try:
                from app.services.map_qa_service import MapQAService
                report = await run_in_thread(MapQAService().generate_report, latest_map)
                score = report.get("total_score") or 0
                normativity = {
                    "score_5": round(min(score / 200.0, 5.0), 2),
                    "score_1000": score,
                    "grade": report.get("grade"),
                    "status": report.get("status"),
                    "map_id": latest_map.get("map_id"),
                    "map_name": latest_map.get("name"),
                }
            except Exception as e:
                logger.warning(f"[Evaluation] 生成规范性报告失败: {e}")
        return ApiResponse(success=True, data=evaluation_service.stats(normativity=normativity))
    except CartoAgentError as e:
        return ApiResponse(success=False, message=str(e))
    except Exception as e:
        return ApiResponse(success=False, message=f"评估统计失败: {e}")


# ========== SSE流式响应端点 ==========

@router.post("/sessions/{session_id}/stream", summary="流式发送消息（SSE）")
async def send_message_stream(
    session_id: str,
    request: SendMessageRequest,
    session_service: SessionService = Depends(get_session_service),
    agent_service: AgentService = Depends(get_agent_service),
    llm_service: LLMService = Depends(get_llm_service),
):
    """流式发送消息 - 通过SSE实时推送LLM生成的文本

    流程：
    1. 先通过AgentService执行完整的制图流程（非流式）
    2. 如果是问答类请求，额外通过LLM流式生成回复
    3. 通过SSE逐步推送文本块给前端

    SSE事件格式：
    - data: {"type": "thinking", "content": "..."}  思考过程
    - data: {"type": "chunk", "content": "..."}     文本块
    - data: {"type": "map", "content": {...}}        地图数据
    - data: {"type": "done", "content": "..."}       完成
    """
    async def event_generator():
        try:
            # 校验会话
            session = session_service.get_session(session_id)
            if session is None:
                yield f"data: {_sse_json({'type': 'error', 'content': '会话不存在'})}\n\n"
                return

            # 保存用户消息
            session_service.add_message(
                session_id=session_id,
                role="user",
                content=request.message,
            )

            # 推送思考过程
            yield f"data: {_sse_json({'type': 'thinking', 'content': '正在分析您的请求...'})}\n\n"

            # 在后台线程执行智能体处理，同时通过队列实时推送步骤进度
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()
            result_holder: dict = {}

            def progress_cb(event: dict):
                # 透传 steps 和 thinking 进度事件（地图生成期间的"正在获取数据..."等提示需实时推送）
                # 第一个 thinking 已在上方统一推送，后续 thinking 直接透传避免重复
                etype = event.get("type")
                if etype in ("steps", "thinking"):
                    loop.call_soon_threadsafe(queue.put_nowait, event)

            def run_agent():
                try:
                    result_holder["result"] = agent_service.process_request(
                        message=request.message,
                        session_id=session_id,
                        progress_cb=progress_cb,
                        map_id=request.map_id,
                    )
                except Exception as e:  # noqa: BLE001
                    result_holder["error"] = e
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            threading.Thread(target=run_agent, daemon=True).start()

            # 处理过程中逐条推送步骤进度；加心跳保活，避免地图生成（OSM拉取）期间前端假死
            last_heartbeat = time.time()
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    # 15秒无事件：推送心跳/进度提示，让前端知道连接仍存活
                    elapsed = time.time() - last_heartbeat
                    if elapsed >= 15:
                        last_heartbeat = time.time()
                        yield f"data: {_sse_json({'type': 'thinking', 'content': '正在处理中（地图数据获取/生成可能需要较长时间），请稍候...'})}\n\n"
                    continue
                if item is None:
                    break
                yield f"data: {_sse_json(item)}\n\n"

            if "error" in result_holder:
                error_content = f"处理失败: {result_holder['error']}"
                yield f"data: {_sse_json({'type': 'error', 'content': error_content})}\n\n"
                return

            result = result_holder.get("result") or {}

            # 如果有地图数据，推送地图
            if result.get("map_data"):
                yield f"data: {_sse_json({'type': 'map', 'content': result['map_data']})}\n\n"

            # 推送GeoToken信息（制图场景）
            geotoken_info = result.get("geotoken_info", {})
            if geotoken_info:
                yield f"data: {_sse_json({'type': 'geotoken', 'content': geotoken_info})}\n\n"

            # 推送RAG知识来源
            rag_sources = result.get("rag_sources", [])
            if rag_sources:
                yield f"data: {_sse_json({'type': 'rag', 'content': rag_sources})}\n\n"

            # 推送GraphRAG实体信息
            graphrag_entities = result.get("graphrag_entities", [])
            if graphrag_entities:
                yield f"data: {_sse_json({'type': 'graphrag', 'content': {'entities': graphrag_entities}})}\n\n"

            # 推送 GraphRAG 推理路径（计划 1.4，前端可视化多跳推理链）
            graphrag_chain = result.get("graphrag_reasoning_chain", [])
            if graphrag_chain:
                yield f"data: {_sse_json({'type': 'graphrag_chain', 'content': graphrag_chain})}\n\n"

            # 推送知识来源（问答场景）
            knowledge_sources = result.get("knowledge_sources", {})
            if knowledge_sources and not result.get("map_data"):
                yield f"data: {_sse_json({'type': 'knowledge_sources', 'content': knowledge_sources})}\n\n"

            # 推送执行步骤
            steps = result.get("steps", [])
            if steps:
                yield f"data: {_sse_json({'type': 'steps', 'content': steps})}\n\n"

            # 推送思考过程
            thinking = result.get("thinking", "")
            if thinking:
                yield f"data: {_sse_json({'type': 'thinking', 'content': thinking})}\n\n"

            # 推送LLM生成的回复（复用process_request已生成的回复，避免二次LLM调用）
            response_text = result.get("response", "")

            if response_text:
                # 直接推送完整回复文本（process_request已完成全部处理，无需分块延迟）
                yield f"data: {_sse_json({'type': 'chunk', 'content': response_text})}\n\n"

            # 保存助手响应
            session_service.add_message(
                session_id=session_id,
                role="assistant",
                content=response_text,
                map_data=result.get("map_data"),
                steps=result.get("steps"),
                thinking=result.get("thinking"),
            )

            # 推送完成信号
            yield f"data: {_sse_json({'type': 'done', 'content': '完成', 'provider': result.get('provider'), 'model': result.get('model')})}\n\n"

        except Exception as e:
            error_content = f"处理失败: {e}"
            yield f"data: {_sse_json({'type': 'error', 'content': error_content})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
