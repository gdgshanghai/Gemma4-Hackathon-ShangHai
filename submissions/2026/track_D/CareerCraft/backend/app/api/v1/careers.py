"""Careers and world map islands routing endpoints."""

from fastapi import APIRouter, Query
from app.models import schemas
from app.services import rag

router = APIRouter()


@router.get(
    "",
    summary="获取职业岛屿分布与简要概况",
    response_model=list[schemas.CareerResponse],
)
async def list_career_islands() -> list[schemas.CareerResponse]:
  """Returns available career tracks for world map rendering."""
  return [
      {
          "career_id": "career_data_analyst",
          "name": "数据山脉 (Data Mounts)",
          "description": "专注于数据清洗、探索性分析与商业指标洞察。",
          "unlocked": True,
          "role_id": "mentor_ying",
          "resource_domain": "core_data",
          "api_supported": True,
      },
      {
          "career_id": "career_software_engineer",
          "name": "硅屿 (Silicon Isle)",
          "description": "专注于代码重构、单元测试与高并发架构调优。",
          "unlocked": True,
          "role_id": "mentor_ling",
          "resource_domain": "core_software",
          "api_supported": True,
      },
  ]


@router.get(
    "/resources",
    summary="根据查询触发 RAG 知识库检索",
    response_model=list[schemas.ResourceResponse],
)
async def get_learning_resources(
    query: str = Query(..., description="用户遇到的问题关键字"),
    domain: str = Query("core_data", description="所属领域"),
) -> list[schemas.ResourceResponse]:
  """Retrieves top relevant markdown segments supporting active task."""
  return await rag.query_knowledge_base(query=query, career_category=domain)
