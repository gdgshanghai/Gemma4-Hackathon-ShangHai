import json
import os

import requests


class DecisionService:
    """Gemma 4 multimodal decision adapter with deterministic local fallback."""

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.gemma_model = os.getenv("GEMMA_MODEL", "gemma4:2b")
        self.timeout_seconds = float(os.getenv("GEMMA_TIMEOUT_SECONDS", "8"))

    def analyze(self, state: dict) -> dict:
        fallback = self._rule_based_analyze(state)
        if os.getenv("GEMMA_ENABLED", "1").lower() in {"0", "false", "no"}:
            return fallback

        try:
            return self._gemma_analyze(state, fallback)
        except Exception as exc:
            fallback["model"] = "gemma4-rule-fallback"
            fallback["gemma_error"] = str(exc)
            return fallback

    def _gemma_analyze(self, state: dict, fallback: dict) -> dict:
        payload = {
            "model": self.gemma_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Gemma 4 running an elderly care safety decision layer. "
                        "Use visual fall detection, speech intent, and response context to decide "
                        "whether the system should continue monitoring, start a voice check, or "
                        "trigger emergency escalation. Return concise, safe, structured decisions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "multimodal_state": state,
                            "fallback_decision": fallback,
                            "required_json_fields": [
                                "risk_level",
                                "risk_score",
                                "emergency_alert",
                                "action",
                                "reason",
                                "reply_analysis",
                            ],
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            "tools": self._native_tools(),
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }
        response = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        decision = self._decision_from_tool_call(message) or self._decision_from_content(message)
        normalized = self._normalize_decision(decision, fallback)
        normalized["model"] = self.gemma_model
        normalized["gemma_runtime"] = "ollama"
        return normalized

    def _native_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "continue_monitoring",
                    "description": "Use when the elder appears safe and no immediate intervention is needed.",
                    "parameters": self._tool_parameters_schema(False),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "start_voice_check",
                    "description": "Use when visual or context signals are uncertain and the system should ask for confirmation.",
                    "parameters": self._tool_parameters_schema(False),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trigger_emergency_alert",
                    "description": "Use when fall, help request, or no-response signals justify emergency escalation.",
                    "parameters": self._tool_parameters_schema(True),
                },
            },
        ]

    def _tool_parameters_schema(self, emergency_default: bool) -> dict:
        return {
            "type": "object",
            "properties": {
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "emergency_alert": {"type": "boolean", "default": emergency_default},
                "action": {"type": "string"},
                "reason": {"type": "string"},
                "reply_analysis": {"type": "string"},
            },
            "required": ["risk_level", "risk_score", "emergency_alert", "action", "reason", "reply_analysis"],
        }

    def _decision_from_tool_call(self, message: dict) -> dict | None:
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return None
        function = (tool_calls[0] or {}).get("function") or {}
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            return json.loads(arguments)
        if isinstance(arguments, dict):
            return arguments
        return None

    def _decision_from_content(self, message: dict) -> dict:
        content = message.get("content") or "{}"
        return json.loads(content)

    def _normalize_decision(self, decision: dict, fallback: dict) -> dict:
        risk_level = str(decision.get("risk_level") or fallback["risk_level"]).lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = fallback["risk_level"]
        risk_score = int(decision.get("risk_score", fallback["risk_score"]))
        risk_score = max(0, min(100, risk_score))
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "emergency_alert": bool(decision.get("emergency_alert", fallback["emergency_alert"])),
            "action": str(decision.get("action") or fallback["action"]),
            "reason": str(decision.get("reason") or fallback["reason"]),
            "reply_analysis": str(decision.get("reply_analysis") or fallback["reply_analysis"]),
        }

    def _rule_based_analyze(self, state: dict) -> dict:
        vision = state.get("vision", {})
        speech = state.get("speech", {})
        context = state.get("context", {})

        fall_detected = bool(vision.get("fall_detected"))
        confidence = max(0.0, min(1.0, float(vision.get("confidence") or 0)))
        confidence_pct = round(confidence * 100)
        detections = vision.get("detections") or []
        posture_fall = any(item.get("posture_fall") for item in detections if isinstance(item, dict))
        transcript = str(speech.get("transcript") or "")
        intent = str(speech.get("intent") or "none")
        no_response_seconds = int(context.get("no_response_seconds") or 0)

        if intent == "help":
            score = 96 if fall_detected else 82
            return {
                "risk_level": "high",
                "risk_score": score,
                "emergency_alert": fall_detected,
                "action": "Escalate rescue response",
                "reason": (
                    "The user verbally asked for help"
                    + (f" while vision confidence is {confidence_pct}%." if fall_detected else ".")
                ),
                "reply_analysis": f"User replied: {transcript}",
                "model": "gemma4-rule-fallback",
            }

        if intent == "safe" and not fall_detected:
            score = max(5, min(18, round(6 + confidence * 8)))
            return {
                "risk_level": "low",
                "risk_score": score,
                "emergency_alert": False,
                "action": "User confirmed safe",
                "reason": "The user gave a safe voice reply and vision does not detect a fall.",
                "reply_analysis": f"User replied: {transcript}",
                "model": "gemma4-rule-fallback",
            }

        if fall_detected and confidence >= 0.85 and no_response_seconds >= 60:
            return {
                "risk_level": "high",
                "risk_score": 100,
                "emergency_alert": True,
                "action": "Trigger emergency alert",
                "reason": (
                    f"Fall risk is very high ({confidence_pct}% visual confidence) "
                    f"and there has been no response for {no_response_seconds} seconds."
                ),
                "reply_analysis": "No response after repeated voice checks.",
                "model": "gemma4-rule-fallback",
            }

        if fall_detected and intent == "safe":
            score = max(18, min(38, round(18 + confidence * 18)))
            return {
                "risk_level": "low",
                "risk_score": score,
                "emergency_alert": False,
                "action": "Record safe reply and keep monitoring",
                "reason": (
                    f"The user replied that they are safe. Visual confidence is {confidence_pct}%, "
                    "so monitoring continues without emergency escalation."
                ),
                "reply_analysis": f"User replied: {transcript}",
                "model": "gemma4-rule-fallback",
            }

        if fall_detected and no_response_seconds >= 30:
            score = max(82, min(96, round(70 + confidence * 20 + no_response_seconds / 6)))
            return {
                "risk_level": "high",
                "risk_score": score,
                "emergency_alert": False,
                "action": "Escalate voice prompt and prepare alert",
                "reason": (
                    f"Fall risk remains active ({confidence_pct}% visual confidence) "
                    f"and no response has been received for {no_response_seconds} seconds."
                ),
                "reply_analysis": "No response yet.",
                "model": "gemma4-rule-fallback",
            }

        if fall_detected:
            if posture_fall:
                score = max(36, min(58, round(28 + confidence * 42)))
                reason = (
                    f"Posture looks like a possible fall ({confidence_pct}% posture confidence), "
                    "but it needs voice confirmation before escalation."
                )
            else:
                score = max(52, min(82, round(42 + confidence * 38)))
                reason = (
                    f"Vision detected a suspected fall with {confidence_pct}% confidence. "
                    "Ask the user to confirm whether they are safe."
                )
            return {
                "risk_level": "medium",
                "risk_score": score,
                "emergency_alert": False,
                "action": "Start voice check",
                "reason": reason,
                "reply_analysis": "Voice check required.",
                "model": "gemma4-rule-fallback",
            }

        score = max(6, min(28, round(8 + confidence * 14)))
        return {
            "risk_level": "low",
            "risk_score": score,
            "emergency_alert": False,
            "action": "Continue monitoring",
            "reason": (
                f"No fall is currently detected. Person confidence is {confidence_pct}%."
                if confidence
                else "No fall is currently detected."
            ),
            "reply_analysis": "No active voice check.",
            "model": "gemma4-rule-fallback",
        }
