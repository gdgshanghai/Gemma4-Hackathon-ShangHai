"""RAG knowledge base retrieval service with local hashing embeddings."""

import logging
import os
import re
import math
import hashlib
from typing import Any
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from app.core.paths import docs_dir
from app.db.session import chroma_client

logger = logging.getLogger(__name__)


class CustomHashingEmbeddingFunction(EmbeddingFunction):
  """Custom hashing-based embedding function to avoid network model downloads."""

  def __init__(self) -> None:
    pass

  def __call__(self, input: Documents) -> Embeddings:
    embeddings = []
    dim = 128
    for doc in input:
      vector = [0.0] * dim
      tokens = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]+', doc.lower())
      if tokens:
        for token in tokens:
          # Use deterministic md5 hashing to ensure stability across server reboots
          h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16) % dim
          vector[h] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
          vector = [v / norm for v in vector]
      embeddings.append(vector)
    return embeddings


def get_collection():
  """Initializes and returns the ChromaDB collection with custom embeddings."""
  embed_fn = CustomHashingEmbeddingFunction()
  return chroma_client.get_or_create_collection(
      name="careercraft_kb", embedding_function=embed_fn
  )


def chunk_markdown(content: str) -> list[tuple[str, str]]:
  """Splits markdown content into sections based on ## headers.

  Returns:
      A list of tuples: (subheading_title, chunk_content)
  """
  lines = content.split('\n')
  chunks = []
  current_subheading = '概述'
  current_lines = []

  for line in lines:
    if line.startswith('## '):
      if current_lines:
        chunks.append((current_subheading, '\n'.join(current_lines).strip()))
      current_subheading = line.replace('## ', '').strip()
      current_lines = [line]  # Keep heading in chunk for embedding context
    else:
      current_lines.append(line)

  if current_lines:
    chunks.append((current_subheading, '\n'.join(current_lines).strip()))

  return [c for c in chunks if c[1]]


def populate_knowledge_base():
  """Checks and populates the ChromaDB knowledge base collection from docs/knowledge_base."""
  collection = get_collection()
  try:
    if collection.count() > 0:
      # Already populated
      return
  except Exception:
    # Collection not yet materialized; fall through to populate.
    logger.debug("RAG collection count() failed; assuming empty.", exc_info=True)

  kb_dir = str(docs_dir() / "knowledge_base")

  if not os.path.exists(kb_dir):
    logger.warning("RAG: knowledge base directory %s not found.", kb_dir)
    return

  indexed_count = 0
  # Map physical folders to career categories
  dir_mapping = {
      'data_analyst': 'core_data',
      'software_engineer': 'core_software',
  }

  for sub_folder, category in dir_mapping.items():
    sub_path = os.path.join(kb_dir, sub_folder)
    if not os.path.exists(sub_path):
      continue

    # Walk sub_path
    for root, _, files in os.walk(sub_path):
      for file in files:
        if file.endswith('.md'):
          file_path = os.path.join(root, file)
          try:
            with open(file_path, 'r', encoding='utf-8') as f:
              content = f.read()

            # Extract primary title
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            doc_title = title_match.group(1).strip() if title_match else file

            chunks = chunk_markdown(content)
            # Calculate file relative path to generate a 100% unique chunk ID
            rel_path = os.path.relpath(file_path, kb_dir)
            safe_id_base = rel_path.replace(os.sep, '_')

            for idx, (subheading, chunk_text) in enumerate(chunks):
              chunk_id = f"{safe_id_base}_{idx}"
              full_title = f"{doc_title} - {subheading}"

              collection.add(
                  documents=[chunk_text],
                  metadatas=[{
                      "title": full_title,
                      "career_category": category,
                      "source": file,
                  }],
                  ids=[chunk_id],
              )
              indexed_count += 1
          except (OSError, UnicodeDecodeError):
            logger.exception("RAG: failed to index %s", file)

  logger.info("RAG: populated knowledge base with %d chunks.", indexed_count)


async def query_knowledge_base(
    query: str,
    career_category: str = "core_data",
) -> list[dict[str, Any]]:
  """Performs semantic search against populated markdown knowledge.

  Args:
      query: The user's search phrase or keywords.
      career_category: The active career track domain ('core_data' or
        'core_software').

  Returns:
      A list of top relevant document segments matching the front-end format.
  """
  # Populate on first query if empty
  populate_knowledge_base()

  collection = get_collection()
  try:
    results = collection.query(
        query_texts=[query],
        n_results=3,
        where={"career_category": career_category},
    )

    if not results or not results['documents'] or not results['documents'][0]:
      return []

    output = []
    query_terms = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]+', query.lower())

    for idx in range(len(results['documents'][0])):
      doc_text = results['documents'][0][idx]
      meta = results['metadatas'][0][idx]
      # ChromaDB distance can be converted to similarity score
      # Cosine distance ranges [0, 2]. Similarity = 1 - (distance / 2)
      dist = results['distances'][0][idx] if 'distances' in results else 0.5
      sim = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

      # Simple Keyword-Boosting/Hybrid Search overlap evaluation
      match_count = 0
      for term in query_terms:
        if term in doc_text.lower() or term in meta.get("title", "").lower():
          match_count += 1
      
      boost = 0.0
      if query_terms:
        boost = 0.15 * (match_count / len(query_terms))
      
      sim_boosted = max(0.0, min(1.0, sim + boost))

      output.append({
          "doc_id": results['ids'][0][idx],
          "title": meta.get("title", "知识卡片"),
          "snippet": doc_text,
          "relevance_score": round(sim_boosted, 2),
          "source": meta.get("source"),
          "tags": [career_category],
      })
    return output
  except Exception:
    logger.exception("RAG query failed for query=%r category=%r", query, career_category)
    return []
