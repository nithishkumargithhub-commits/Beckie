import sqlite3
import os
import json
import math
import re
import logging
from typing import List, Dict, Any
import config

logger = logging.getLogger("VoiceAssistant.MemoryRAG")

DB_PATH = os.path.join(config.BASE_DIR, "jarvis.db")

def _get_connection():
    return sqlite3.connect(DB_PATH)

def init_rag_table():
    """Initializes the rag_memories table if it does not exist."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rag_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tokens_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logger.info("RAG memory table initialized.")
    except Exception as e:
        logger.error(f"Error initializing RAG table: {e}")

def _tokenize(text: str) -> List[str]:
    """Tokenizes and cleans text for vector TF-IDF indexing."""
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    return [w for w in words if len(w) > 2]

def store_memory(content: str, category: str = "user_preference") -> bool:
    """
    Stores a new memory entry with token frequency vectors.
    """
    if not getattr(config, "ENABLE_RAG_MEMORY", True):
        return False

    content_clean = content.strip()
    if not content_clean:
        return False

    init_rag_table()
    tokens = _tokenize(content_clean)
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1

    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO rag_memories (content, category, tokens_json) VALUES (?, ?, ?)",
            (content_clean, category, json.dumps(tf))
        )
        conn.commit()
        conn.close()
        logger.info(f"Stored RAG memory ({category}): '{content_clean}'")
        return True
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        return False

def query_memories(query: str, top_k: int = 3) -> List[str]:
    """
    Retrieves top_k relevant memory content strings using cosine similarity over token frequencies.
    """
    if not getattr(config, "ENABLE_RAG_MEMORY", True):
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    q_tf = {}
    for t in query_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1

    q_norm = math.sqrt(sum(v*v for v in q_tf.values()))
    if q_norm == 0:
        return []

    init_rag_table()
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT content, tokens_json FROM rag_memories")
        rows = cursor.fetchall()
        conn.close()

        scored_memories = []
        for content, tokens_json in rows:
            if not tokens_json:
                continue
            doc_tf = json.loads(tokens_json)
            doc_norm = math.sqrt(sum(v*v for v in doc_tf.values()))
            if doc_norm == 0:
                continue

            dot_product = sum(q_tf[t] * doc_tf.get(t, 0) for t in q_tf)
            similarity = dot_product / (q_norm * doc_norm)

            if similarity > 0.15:
                scored_memories.append((similarity, content))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_results = [mem for _, mem in scored_memories[:top_k]]
        return top_results
    except Exception as e:
        logger.error(f"Error querying memory RAG: {e}")
        return []
