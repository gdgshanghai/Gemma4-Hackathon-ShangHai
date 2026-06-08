"""Unit tests for the RAG custom hashing and chunking mechanics."""

import unittest
import math
from app.services.rag import CustomHashingEmbeddingFunction, chunk_markdown


class TestRagMechanics(unittest.TestCase):
  """RAG mechanics testing suite."""

  def test_custom_hashing_embedding_is_deterministic_and_normalized(self):
    """Tests that the embedding function generates exact, normalized 128-dimensional vectors."""
    embed_fn = CustomHashingEmbeddingFunction()
    
    docs = [
        "Pandas is great for data cleaning and exploration.",
        "SQL joins are essential database skills.",
    ]
    
    embeddings = embed_fn(docs)
    
    # Ensure we have vectors for each document
    self.assertEqual(len(embeddings), len(docs))
    
    for vector in embeddings:
      # Ensure standard dimension is exactly 128
      self.assertEqual(len(vector), 128)
      
      # Ensure vectors are normalized (L2 norm is approximately 1.0)
      norm = math.sqrt(sum(v * v for v in vector))
      self.assertTrue(math.isclose(norm, 1.0, rel_tol=1e-5) or norm == 0.0)

    # Ensure determinism (stability across calls and reboots)
    emb1 = embed_fn(["determinism_check"])
    emb2 = embed_fn(["determinism_check"])
    self.assertEqual(len(emb1), len(emb2))
    for v1, v2 in zip(emb1, emb2):
      self.assertEqual(len(v1), len(v2))
      for val1, val2 in zip(v1, v2):
        self.assertAlmostEqual(val1, val2)

  def test_chunk_markdown_splits_correctly_by_headers(self):
    """Tests that the chunking parser splits document texts accurately at ## subsections."""
    md_content = """# Main Document Title
This is some intro text.

## Section 1: Intro
Here is the first section content.
With multiple lines.

## Section 2: Code Example
```python
print("Hello RAG")
```
"""
    
    chunks = chunk_markdown(md_content)
    
    # We expect 3 sections: 概述 (intro), Section 1, and Section 2
    self.assertEqual(len(chunks), 3)
    
    # Verify headers
    headings = [c[0] for c in chunks]
    self.assertIn("概述", headings)
    self.assertIn("Section 1: Intro", headings)
    self.assertIn("Section 2: Code Example", headings)

    # Check section content
    section_1_content = [c[1] for c in chunks if c[0] == "Section 1: Intro"][0]
    self.assertIn("Here is the first section content.", section_1_content)
    self.assertIn("## Section 1: Intro", section_1_content)
