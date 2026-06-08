N8N_NODE_SCHEMA = {
    "ManualTrigger": {
        "type": "n8n-nodes-base.manualTrigger",
        "parameters": {},
    },
    "Webhook": {
        "type": "n8n-nodes-base.webhook",
        "parameters": {
            "httpMethod": "POST",
            "path": "",
            "options": {},
        },
    },
    "HTTPRequest": {
        "type": "n8n-nodes-base.httpRequest",
        "parameters": {
            "url": "",
            "method": "GET",
            "authentication": "none",
            "sendBody": False,
            "options": {},
        },
    },
    "IF": {
        "type": "n8n-nodes-base.if",
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                },
                "conditions": [],
            },
        },
    },
    "Code": {
        "type": "n8n-nodes-base.code",
        "parameters": {
            "jsCode": "",
            "language": "javascript",
        },
    },
    "Feishu": {
        "type": "n8n-nodes-base.feishu",
        "parameters": {
            "resource": "message",
            "operation": "send",
            "message": {
                "msg_type": "text",
                "content": {},
            },
        },
    },
    "Slack": {
        "type": "n8n-nodes-base.slack",
        "parameters": {
            "channel": "",
            "text": "",
        },
    },
    "GitHub": {
        "type": "n8n-nodes-base.github",
        "parameters": {
            "repository": "",
            "owner": "",
        },
    },
    "Set": {
        "type": "n8n-nodes-base.set",
        "parameters": {
            "values": {},
            "options": {},
        },
    },
    "SplitInBatches": {
        "type": "n8n-nodes-base.splitInBatches",
        "parameters": {
            "batchSize": 10,
        },
    },
    "Merge": {
        "type": "n8n-nodes-base.merge",
        "parameters": {
            "mode": "combine",
        },
    },
    "Switch": {
        "type": "n8n-nodes-base.switch",
        "parameters": {
            "dataType": "string",
            "value1": "",
            "outputs": [],
        },
    },
}

WORKFLOW_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "typeVersion": {"type": "number", "default": 1},
                    "position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[x, y] 坐标",
                    },
                    "parameters": {"type": "object"},
                },
                "required": ["name", "type", "position", "parameters"],
            },
        },
        "connections": {
            "type": "object",
            "description": "{ nodeIndex: { outputIndex: [{ node: string, outputIndex: number }] } }",
        },
        "settings": {"type": "object"},
        "version": {"type": "number", "default": 2},
    },
    "required": ["name", "nodes", "connections"],
}
