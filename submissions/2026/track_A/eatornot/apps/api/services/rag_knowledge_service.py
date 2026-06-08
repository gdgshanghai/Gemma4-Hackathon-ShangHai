"""RAG 知识库服务 — 使用向量检索为 Agent 提供知识支持"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 全局变量
_chroma_client = None
_collection = None

KNOWLEDGE_DIR = Path(__file__).parent.parent.parent.parent / "knowledge"
CHROMA_DIR = KNOWLEDGE_DIR / "chroma_db"


def _get_collection():
    """获取或创建 ChromaDB collection"""
    global _chroma_client, _collection

    if _collection is None:
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建持久化目录
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)

            # 初始化 ChromaDB 客户端
            _chroma_client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False)
            )

            # 获取或创建 collection（使用默认 embedding）
            _collection = _chroma_client.get_or_create_collection(
                name="nutrition_knowledge",
                metadata={"description": "营养学知识库"}
            )

            # 如果 collection 为空，加载知识
            if _collection.count() == 0:
                _load_knowledge_to_collection()

            logger.info(f"ChromaDB collection loaded with {_collection.count()} documents")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            _collection = None

    return _collection


def _load_knowledge_to_collection():
    """加载知识到 ChromaDB"""
    knowledge_path = KNOWLEDGE_DIR / "nutrition.json"
    if not knowledge_path.exists():
        logger.warning(f"Knowledge file not found: {knowledge_path}")
        return

    with open(knowledge_path, "r", encoding="utf-8") as f:
        knowledge = json.load(f)

    documents = []
    metadatas = []
    ids = []

    # 1. 加载知识来源
    for source_key, source_data in knowledge.get("sources", {}).items():
        source_name = source_data["name"]
        for i, point in enumerate(source_data.get("key_points", [])):
            doc_id = f"source_{source_key}_{i}"
            documents.append(point)
            metadatas.append({
                "category": "nutrition_guideline",
                "source": source_name,
                "publisher": source_data.get("publisher", ""),
            })
            ids.append(doc_id)

    # 2. 加载公式
    for formula_key, formula_data in knowledge.get("formulas", {}).items():
        doc_id = f"formula_{formula_key}"
        doc_text = f"{formula_data['name']}: {formula_data['description']}"
        if "formula" in formula_data:
            if isinstance(formula_data["formula"], dict):
                for k, v in formula_data["formula"].items():
                    doc_text += f"\n{k}: {v}"
            else:
                doc_text += f"\n{formula_data['formula']}"
        if "source" in formula_data:
            doc_text += f"\n来源: {formula_data['source']}"

        documents.append(doc_text)
        metadatas.append({
            "category": "formula",
            "source": formula_data.get("source", ""),
        })
        ids.append(doc_id)

    # 3. 加载情绪性进食知识
    emotional = knowledge.get("emotional_eating", {})
    if emotional:
        for i, finding in enumerate(emotional.get("key_findings", [])):
            doc_id = f"emotional_finding_{i}"
            documents.append(finding)
            metadatas.append({
                "category": "emotional_eating",
                "source": emotional.get("source", ""),
            })
            ids.append(doc_id)

        for i, strategy in enumerate(emotional.get("management_strategies", [])):
            doc_id = f"emotional_strategy_{i}"
            documents.append(strategy)
            metadatas.append({
                "category": "emotional_eating",
                "source": emotional.get("source", ""),
            })
            ids.append(doc_id)

    # 4. 加载食物分类知识
    food_categories = knowledge.get("food_categories", {})
    for category_key, category_data in food_categories.items():
        if isinstance(category_data, dict):
            for sub_key, sub_data in category_data.items():
                if isinstance(sub_data, dict):
                    doc_text = f"{sub_key}: {sub_data.get('特点', '')}"
                    if "推荐" in sub_data:
                        doc_text += f"\n推荐: {sub_data['推荐']}"
                    if "建议" in sub_data:
                        doc_text += f"\n建议: {sub_data['建议']}"

                    doc_id = f"food_{category_key}_{sub_key}"
                    documents.append(doc_text)
                    metadatas.append({
                        "category": "food_category",
                        "source": category_key,
                    })
                    ids.append(doc_id)

    # 添加到 collection（使用 ChromaDB 默认 embedding）
    if documents:
        _collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Loaded {len(documents)} documents to ChromaDB")


def search_knowledge(query: str, agent_name: str = "", n_results: int = 3) -> list[dict]:
    """
    搜索知识库

    Args:
        query: 查询文本
        agent_name: Agent 名称（用于过滤）
        n_results: 返回结果数量

    Returns:
        检索结果列表
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        # 构建查询
        search_query = query
        if agent_name:
            search_query = f"{agent_name}: {query}"

        # 使用 ChromaDB 默认 embedding 查询
        results = collection.query(
            query_texts=[search_query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        # 格式化结果
        formatted_results = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })

        return formatted_results

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return []


def get_evidence_for_agent(agent_name: str, context: dict = None) -> list[str]:
    """
    为 Agent 获取相关证据

    Args:
        agent_name: Agent 名称
        context: 上下文信息

    Returns:
        证据列表
    """
    # 构建查询
    query_map = {
        "档案Agent": "用户档案分析 BMI TDEE 基础代谢",
        "减脂Agent": "减脂 热量缺口 体重管理",
        "营养Agent": "营养成分 食物热量 蛋白质 脂肪",
        "预算Agent": "预算 餐饮消费 性价比",
        "食欲Agent": "情绪性进食 压力 疲惫 食欲",
        "时间Agent": "时间管理 快餐 出餐效率",
        "安全Agent": "食品安全 过敏原 健康风险",
        "未来模拟Agent": "热量平衡 用餐规划",
    }

    query = query_map.get(agent_name, "营养学知识")

    # 搜索知识库
    results = search_knowledge(query, agent_name, n_results=2)

    if results:
        return [r["content"] for r in results]

    # 如果没有搜索结果，返回默认证据
    return ["综合分析"]
