from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, Optional

import json


class NodeHandler:
    async def execute(self, config: dict, context: dict) -> dict:
        raise NotImplementedError


class ManualTriggerHandler(NodeHandler):
    async def execute(self, config, context):
        return {"triggered": True, "type": "manual"}


class ScheduleTriggerHandler(NodeHandler):
    async def execute(self, config, context):
        return {"triggered": True, "type": "schedule", "cron": config.get("cron")}


class WebhookTriggerHandler(NodeHandler):
    async def execute(self, config, context):
        return {"triggered": True, "type": "webhook"}


class EventTriggerHandler(NodeHandler):
    async def execute(self, config, context):
        return {"triggered": True, "type": "event", "event": config.get("event")}


class HotspotScanHandler(NodeHandler):
    async def execute(self, config, context):
        from cn_social_agent.tools.hotspots import tool_scan_hotspot_board
        result = await tool_scan_hotspot_board(
            per_page=config.get("limit", 5),
            source=config.get("source", "all"),
        )
        return {"hotspots": result.get("board", []), "count": len(result.get("board", []))}


class LLMGenerateHandler(NodeHandler):
    async def execute(self, config, context):
        prompt = config.get("prompt", "")
        for key, value in context.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    prompt = prompt.replace(f"{{{{{key}.{k}}}}}", str(v))
            else:
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
        return {"text": f"[LLM] Generated content for: {prompt[:100]}...", "prompt_used": prompt[:200]}


class EvidenceCollectHandler(NodeHandler):
    async def execute(self, config, context):
        url = config.get("url", "")
        return {"evidence": [], "url": url, "status": "collected"}


class StoryboardHandler(NodeHandler):
    async def execute(self, config, context):
        return {"scenes": [], "duration": config.get("duration", 15)}


class VideoRenderHandler(NodeHandler):
    async def execute(self, config, context):
        return {"video_path": None, "status": "pending", "quality": config.get("quality", "720p")}


class ImageGenHandler(NodeHandler):
    async def execute(self, config, context):
        return {"image_path": None, "prompt": config.get("prompt", "")}


class WeixinPublishHandler(NodeHandler):
    async def execute(self, config, context):
        return {"platform": "weixin", "status": "draft", "draft_id": None}


class ToutiaoPublishHandler(NodeHandler):
    async def execute(self, config, context):
        return {"platform": "toutiao", "status": "draft", "draft_id": None}


class DouyinPublishHandler(NodeHandler):
    async def execute(self, config, context):
        return {"platform": "douyin", "status": "draft", "draft_id": None}


class XiaohongshuPublishHandler(NodeHandler):
    async def execute(self, config, context):
        return {"platform": "xiaohongshu", "status": "draft", "draft_id": None}


class ConditionHandler(NodeHandler):
    async def execute(self, config, context):
        expression = config.get("expression", "true")
        try:
            result = bool(eval(expression, {"__builtins__": {}}, context))
        except Exception:
            result = False
        return {"result": result, "branch": "true" if result else "false"}


class DelayHandler(NodeHandler):
    async def execute(self, config, context):
        seconds = config.get("seconds", 1)
        await asyncio.sleep(min(seconds, 300))
        return {"delayed": seconds}


class LoopHandler(NodeHandler):
    async def execute(self, config, context):
        count = config.get("count", 1)
        return {"iteration": count, "completed": True}


class StopHandler(NodeHandler):
    async def execute(self, config, context):
        return {"stopped": True, "reason": config.get("reason", "manual stop")}


class SaveProjectHandler(NodeHandler):
    async def execute(self, config, context):
        return {"project_id": None, "status": "saved"}


class NotifyHandler(NodeHandler):
    async def execute(self, config, context):
        return {"notified": True, "channel": config.get("channel", "default")}


class ExportHandler(NodeHandler):
    async def execute(self, config, context):
        return {"exported": True, "format": config.get("format", "json")}


HANDLERS: dict[str, NodeHandler] = {
    "trigger.manual": ManualTriggerHandler(),
    "trigger.schedule": ScheduleTriggerHandler(),
    "trigger.webhook": WebhookTriggerHandler(),
    "trigger.event": EventTriggerHandler(),
    "action.hotspot_scan": HotspotScanHandler(),
    "action.llm_generate": LLMGenerateHandler(),
    "action.evidence_collect": EvidenceCollectHandler(),
    "action.storyboard": StoryboardHandler(),
    "action.video_render": VideoRenderHandler(),
    "action.image_gen": ImageGenHandler(),
    "publish.weixin": WeixinPublishHandler(),
    "publish.toutiao": ToutiaoPublishHandler(),
    "publish.douyin": DouyinPublishHandler(),
    "publish.xiaohongshu": XiaohongshuPublishHandler(),
    "control.condition": ConditionHandler(),
    "control.delay": DelayHandler(),
    "control.loop": LoopHandler(),
    "control.stop": StopHandler(),
    "output.save_project": SaveProjectHandler(),
    "output.notify": NotifyHandler(),
    "output.export": ExportHandler(),
}


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    node_ids = {n["id"] for n in nodes}

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in node_ids and tgt in node_ids:
            graph[src].append(tgt)
            in_degree[tgt] += 1

    queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
    order = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in graph[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("Workflow contains a cycle")

    return order


class WorkflowEngine:
    def __init__(self):
        self.max_concurrent = 5
        self.timeout_per_node = 60

    async def execute(self, workflow: dict, context: Optional[dict] = None, trigger_type: str = "manual", single_step: bool = False) -> dict:
        run_id = f"wfr_{int(time.time() * 1000)}"
        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])

        run = {
            "id": run_id,
            "workflowId": workflow.get("id"),
            "status": "running",
            "triggerType": trigger_type,
            "nodeStates": {},
            "context": context or {},
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "finishedAt": None,
            "error": None,
        }

        order = topological_sort(nodes, edges)
        node_map = {n["id"]: n for n in nodes}

        for node_id in order:
            node = node_map.get(node_id)
            if not node:
                continue

            state = run["nodeStates"].get(node_id, {
                "status": "pending",
                "input": None,
                "output": None,
                "error": None,
                "startedAt": None,
                "finishedAt": None,
                "durationMs": None,
            })
            run["nodeStates"][node_id] = state

            state["status"] = "running"
            state["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            try:
                handler = HANDLERS.get(node.get("type"))
                if not handler:
                    raise ValueError(f"Unknown node type: {node.get('type')}")

                output = await asyncio.wait_for(
                    handler.execute(node.get("config", {}), run["context"]),
                    timeout=self.timeout_per_node,
                )

                state["status"] = "done"
                state["output"] = output
                run["context"][node_id] = output

            except asyncio.TimeoutError:
                state["status"] = "failed"
                state["error"] = "Node execution timed out"
                run["status"] = "failed"
                run["error"] = f"Timeout on node {node_id}"
                break
            except Exception as e:
                state["status"] = "failed"
                state["error"] = str(e)

                if node.get("type", "").startswith("control.stop"):
                    run["status"] = "stopped"
                    break

                run["status"] = "failed"
                run["error"] = f"Error on node {node_id}: {str(e)}"
                break

            finally:
                state["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                if state["startedAt"] and state["finishedAt"]:
                    start = time.mktime(time.strptime(state["startedAt"], "%Y-%m-%dT%H:%M:%SZ"))
                    end = time.mktime(time.strptime(state["finishedAt"], "%Y-%m-%dT%H:%M:%SZ"))
                    state["durationMs"] = int((end - start) * 1000)

            if single_step:
                return run

        if run["status"] == "running":
            run["status"] = "success"

        run["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return run


engine = WorkflowEngine()
