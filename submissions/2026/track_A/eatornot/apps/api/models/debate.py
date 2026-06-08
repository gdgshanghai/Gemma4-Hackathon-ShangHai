"""Round Table Debate 数据模型"""

from pydantic import BaseModel, Field
from datetime import datetime


class DebateMessage(BaseModel):
    """辩论中的单条消息"""
    agent: str
    position: str  # 立场陈述
    evidence: list[str] = Field(default_factory=list)  # 支撑证据
    confidence: float = 0.0  # 置信度 0-1
    conflict_with: str | None = None  # 与谁冲突
    reason: str | None = None  # 冲突原因
    vote: str | None = None  # approve / reject / warn
    warning: str | None = None  # 警告信息
    accepted_by: list[str] = Field(default_factory=list)  # 被哪些 Agent 接受


class DebateStage(BaseModel):
    """辩论的一个阶段"""
    stage: str  # initial_opinions / conflicts / compromise / final_vote
    title: str
    messages: list[DebateMessage] = Field(default_factory=list)


class DebateResult(BaseModel):
    """完整的辩论结果"""
    debate_id: str
    stages: list[DebateStage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    def get_stage(self, stage_name: str) -> DebateStage | None:
        """获取指定阶段"""
        for s in self.stages:
            if s.stage == stage_name:
                return s
        return None
