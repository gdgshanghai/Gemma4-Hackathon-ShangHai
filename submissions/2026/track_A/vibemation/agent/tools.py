N8N_GENERATE_WORKFLOW = {
    "type": "function",
    "function": {
        "name": "generate_n8n_workflow",
        "description": "根据用户需求生成可执行的 n8n 工作流 JSON",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "工作流名称"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "n8n 节点列表，每个节点包含 type、parameters、position 等字段",
                },
                "connections": {
                    "type": "object",
                    "description": "节点连接关系，key 为源节点索引，value 为 {outputIndex: [目标节点连接]}",
                },
            },
            "required": ["name", "nodes", "connections"],
        },
    },
}

N8N_MODIFY_WORKFLOW = {
    "type": "function",
    "function": {
        "name": "modify_n8n_workflow",
        "description": "修改已有的 n8n 工作流（增删节点或调整连接）",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add_node", "remove_node", "update_node", "reconnect"],
                    "description": "操作类型",
                },
                "target_node": {
                    "type": "string",
                    "description": "目标节点名称或索引",
                },
                "changes": {
                    "type": "object",
                    "description": "修改内容",
                },
            },
            "required": ["operation", "target_node", "changes"],
        },
    },
}

N8N_VALIDATE_WORKFLOW = {
    "type": "function",
    "function": {
        "name": "validate_n8n_workflow",
        "description": "验证 n8n 工作流 JSON 的完整性和正确性",
        "parameters": {
            "type": "object",
            "properties": {
                "workflow_json": {
                    "type": "string",
                    "description": "待验证的工作流 JSON 字符串",
                },
            },
            "required": ["workflow_json"],
        },
    },
}

N8N_TOOLS = [N8N_GENERATE_WORKFLOW, N8N_MODIFY_WORKFLOW, N8N_VALIDATE_WORKFLOW]


def generate_n8n_workflow(name: str, nodes: list[dict], connections: dict) -> dict:
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {},
        "version": 2,
        "id": None,
        "tags": [],
    }


def modify_n8n_workflow(operation: str, target_node: str, changes: dict) -> dict:
    return {"operation": operation, "target": target_node, "changes": changes, "status": "pending"}


def validate_n8n_workflow(workflow_json: str) -> dict:
    import json
    try:
        wf = json.loads(workflow_json)
        errors = []
        if "nodes" not in wf:
            errors.append("缺少 nodes 字段")
        if "connections" not in wf:
            errors.append("缺少 connections 字段")
        return {"valid": len(errors) == 0, "errors": errors}
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"JSON 解析错误: {e}"]}
