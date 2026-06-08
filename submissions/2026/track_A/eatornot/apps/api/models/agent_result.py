from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    agent_name: str
    score: float = 0.0  # -1.0 (strongly against) to 1.0 (strongly for)
    decision: str = "neutral"  # approve / neutral / reject / warn
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)

    # 圆桌辩论字段
    position: str = ""  # 立场
    objection: str = ""  # 反对意见
    concession: str = ""  # 让步
    final_vote: str = ""  # 最终投票
    confidence: float = 0.0  # 置信度 0-1
    evidence: list[str] = Field(default_factory=list)  # 证据
