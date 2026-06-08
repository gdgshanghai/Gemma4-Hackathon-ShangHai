"""CareerCraft FastAPI Main Application Entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.v1 import agent, careers, missions, user
from app.core.config import settings
from app.core.logging_config import build_log_config, setup_logging
from app.core.paths import generated_dir
from app.db.session import engine, base
from app.services.rag import populate_knowledge_base
import app.models.orm 
setup_logging()

logger = logging.getLogger(__name__)


def _self_heal_schema() -> None:
  """Add columns introduced after the table was first created.

  ``base.metadata.create_all`` only creates *missing tables*; it does not
  add new columns to existing tables. We inspect the live schema and ALTER
  in any column the ORM declares but the DB lacks. Idempotent.
  """
  inspector = inspect(engine)
  if "mission_records" not in inspector.get_table_names():
    return
  existing = {col["name"] for col in inspector.get_columns("mission_records")}
  columns = {
      "mock_data_filename": "VARCHAR",
      "career_id": "VARCHAR",
      "role_id": "VARCHAR",
      "difficulty": "VARCHAR DEFAULT 'medium'",
      "task_direction": "VARCHAR",
      "mission_style": "VARCHAR",
      "reward_xp": "INTEGER DEFAULT 150",
      "reward_skills_json": "TEXT DEFAULT '[]'",
      "evaluation_criteria_json": "TEXT DEFAULT '[]'",
      "display_metadata_json": "TEXT DEFAULT '{}'",
  }
  for column_name, column_type in columns.items():
    if column_name in existing:
      continue
    with engine.begin() as conn:
      conn.execute(text(
          f"ALTER TABLE mission_records ADD COLUMN {column_name} {column_type}"
      ))
    logger.info("schema migration: added mission_records.%s", column_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
  # Initialize SQL database tables on application startup (Self-healing Schema)
  base.metadata.create_all(bind=engine)
  _self_heal_schema()
  # Populate ChromaDB local knowledge base asynchronously in a background thread to avoid blocking FastAPI main thread
  asyncio.create_task(asyncio.to_thread(populate_knowledge_base))
  yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "CareerCraft 职业模拟沙盒 MVP 异步后端中枢。整合多角色 Agent 存根、"
        "结构化成果打分与本地 Markdown RAG 知识库检索服务。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Enable CORS for matching 2D pixel frontend requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount modular API routers.
app.include_router(
    careers.router,
    prefix="/api/v1/careers",
    tags=["Careers & Islands"],
)
app.include_router(
    missions.router,
    prefix="/api/v1/missions",
    tags=["Missions & Evaluations"],
)
app.include_router(
    user.router,
    prefix="/api/v1/user",
    tags=["User Profile & Progression"],
)
app.include_router(
    agent.router,
    prefix="/api/v1/agent",
    tags=["Character Roleplay"],
)


# Serve generated mission artifacts as static downloads. The directory is
# created on first access by ``generated_dir()`` so this mount works on a
# fresh checkout. URLs are produced by ``LocalArtifactStorage.build_url``
# using ``settings.mock_data_public_base``; the path component must match.
app.mount(
    "/mock_data",
    StaticFiles(directory=str(generated_dir())),
    name="mock_data",
)



@app.get("/", summary="基础健康检查接口", tags=["System"])
async def health_check() -> dict[str, str]:
  """Validates basic connectivity and application alive status."""
  return {"status": "healthy", "service": settings.app_name}


if __name__ == "__main__":
  import uvicorn

  uvicorn.run(
      "app.main:app",
      host="127.0.0.1",
      port=8000,
      reload=True,
      reload_excludes=["logs/*", "*.log"],
      log_config=build_log_config(),
  )
