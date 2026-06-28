import os
import json
import sqlite3
import requests
import time
import numpy as np
import tiktoken
from datetime import datetime, timezone
import math

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")
OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
EMBED_MODEL = "nomic-embed-text:latest"
SIMILARITY_THRESHOLD = 0.5

def get_embedding(text: str) -> list[float]:
    """Fetch native embedding from Ollama."""
    for attempt in range(2):
        try:
            response = requests.post(
                OLLAMA_EMBEDDING_URL,
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except requests.exceptions.ReadTimeout as e:
            if attempt == 0:
                print("ReadTimeout fetching embedding, retrying in 2s...")
                time.sleep(2)
            else:
                print(f"Error fetching embedding after retry: {e}")
                return [0.0] * 768
        except Exception as e:
            print(f"Error fetching embedding: {e}")
            return [0.0] * 768
    return [0.0] * 768

def backfill_embeddings():
    """Generate and save vectors for rows where embedding is NULL."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, summary, body_markdown FROM skills WHERE embedding IS NULL")
    rows = cursor.fetchall()
    
    for row in rows:
        skill_id, title, summary, body = row
        content_to_embed = f"{title}\n{summary}\n{body}"
        print(f"Backfilling embedding for skill: {title}")
        
        emb = get_embedding(content_to_embed)
        if emb:
            cursor.execute("UPDATE skills SET embedding = ? WHERE id = ?", (json.dumps(emb), skill_id))
            conn.commit()
            print(f"Saved embedding for {skill_id}.")
        else:
            print(f"Failed to get embedding for {skill_id}.")
    
    conn.close()

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def calculate_time_decay(created_at_iso: str) -> float:
    """Exponential time decay: C(t) = C0 * e^(-lambda * t)"""
    try:
        if created_at_iso.endswith('Z'):
            created_at_iso = created_at_iso[:-1] + '+00:00'
        
        created_at = datetime.fromisoformat(created_at_iso)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        delta = now - created_at
        days = max(delta.days, 0)
        
        lmbda = 0.023 # roughly half-life of 30 days
        decay_factor = math.exp(-lmbda * days)
        return decay_factor
    except Exception as e:
        print(f"Error calculating time decay: {e}")
        return 1.0

def expand_query(raw_query: str) -> str:
    """Rewrite raw user query into a search-optimized string.

    Timeout is intentionally short (5 s) so a slow Ollama does not stall the
    entire retrieval pipeline.  On any failure we fall back to the raw query.
    """
    try:
        prompt = (
            f"Rewrite the following user query into a concise list of keywords "
            f"optimized for semantic search. Return ONLY the keywords, nothing else. "
            f"Query: {raw_query}"
        )
        resp = requests.post(
            OLLAMA_GENERATE_URL,
            json={"model": "qwen2.5:3b", "prompt": prompt, "stream": False},
            timeout=5,  # Reduced from 10 s — fail fast so FTS5 fallback kicks in quickly
        )
        resp.raise_for_status()
        optimized = resp.json().get("response", "").strip()
        print(f"Query Expansion: '{raw_query}' -> '{optimized}'")
        return optimized if optimized else raw_query
    except requests.exceptions.ReadTimeout:
        print(f"[WARN] Ollama timeout during query expansion — using raw query as-is")
        return raw_query
    except Exception as e:
        print(f"[WARN] Query expansion failed ({type(e).__name__}) — using raw query as-is")
        return raw_query

def _is_zero_vector(vec: list) -> bool:
    """Return True if the vector is all-zeros (i.e. an embedding failure placeholder)."""
    return all(v == 0.0 for v in vec)


def search_skills(query: str):
    """Hybrid Search with Time Decay and Query Expansion.

    Degradation path:
      1. Normal path  — FTS5 candidate set + semantic re-ranking (Ollama available).
      2. Keyword mode — Ollama embedding timed out; FTS5 results returned with
                        synthetic scores so the caller still gets useful matches.
    """
    optimized_query = expand_query(query)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ---- FTS5 candidate retrieval ----
    fts_query = optimized_query.replace('"', '""')
    tokens = [f'"{t}"' for t in fts_query.split() if t]
    fts_match = " OR ".join(tokens)

    fts_candidates = []
    if fts_match:
        try:
            cursor.execute(
                '''
                SELECT s.id, s.title, s.summary, s.body_markdown,
                       s.created_at, s.embedding, s.tags
                FROM skills s
                JOIN skills_fts f ON s.rowid = f.rowid
                WHERE skills_fts MATCH ?
                LIMIT 50
                ''',
                (fts_match,)
            )
            fts_candidates = cursor.fetchall()
        except Exception as e:
            print(f"FTS5 Error: {e}")

    # Broad fallback when FTS5 yields nothing
    if not fts_candidates:
        print("No FTS5 matches — falling back to recent-rows scan for semantic search.")
        cursor.execute(
            '''
            SELECT s.id, s.title, s.summary, s.body_markdown,
                   s.created_at, s.embedding, s.tags
            FROM skills s
            ORDER BY created_at DESC
            LIMIT 50
            '''
        )
        fts_candidates = cursor.fetchall()

    # ---- Embedding-based re-ranking ----
    query_emb = get_embedding(optimized_query)
    ollama_available = not _is_zero_vector(query_emb)

    if not ollama_available:
        # ------------------------------------------------------------------ #
        # KEYWORD-ONLY FALLBACK                                               #
        # Ollama is unavailable (embedding returned all zeros).               #
        # Assign synthetic scores to FTS5 matches so the caller still gets   #
        # a ranked list.  Scores are position-based (first match = highest). #
        # ------------------------------------------------------------------ #
        print("[WARN] Ollama timeout — Falling back to Keyword Search")
        results = []
        total = len(fts_candidates)
        for rank, row in enumerate(fts_candidates):
            decay_factor = calculate_time_decay(row["created_at"])
            # Synthetic score: starts at 0.55 for rank-0, decays by position
            synthetic_score = (0.55 - rank * (0.05 / max(total, 1))) * decay_factor
            synthetic_score = max(synthetic_score, SIMILARITY_THRESHOLD)  # floor at threshold
            results.append({
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "body_markdown": row["body_markdown"],
                "tags": row["tags"],
                "score": round(synthetic_score, 4),
            })
        conn.close()
        return results

    # ---- Normal semantic path ----
    results = []
    for row in fts_candidates:
        if not row["embedding"]:
            continue
        db_emb = json.loads(row["embedding"])
        sim_score = cosine_similarity(query_emb, db_emb)
        decay_factor = calculate_time_decay(row["created_at"])
        final_score = sim_score * decay_factor

        if final_score >= SIMILARITY_THRESHOLD:
            results.append({
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "body_markdown": row["body_markdown"],
                "tags": row["tags"],
                "score": final_score,
            })

    conn.close()
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def trust_ladder_router(score: float) -> str:
    """Classify the skill score into a Trust Tier."""
    if score < 0.6:
        return 'Suggest-Only'
    elif score <= 0.8:
        return 'Auto-Apply w/ Notify'
    else:
        return 'Silent Auto-Heal'

class ContextBudgetManager:
    """Strictly truncates text to protect the context window."""
    def __init__(self, max_tokens: int = 2048):
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
        
    def truncate_to_budget(self, text: str) -> str:
        tokens = self.encoding.encode(text)
        if len(tokens) <= self.max_tokens:
            return text
        truncated_tokens = tokens[:self.max_tokens]
        return self.encoding.decode(truncated_tokens)

if __name__ == '__main__':
    print("Running Backfill...")
    backfill_embeddings()
    
    test_query = "stdbool.h not found"
    print(f"\nSearching for: '{test_query}'")
    top_results = search_skills(test_query)
    
    if top_results:
        top_skill = top_results[0]
        
        budget_mgr = ContextBudgetManager()
        raw_content = f"Title: {top_skill['title']}\nSummary: {top_skill['summary']}\nBody: {top_skill['body_markdown']}"
        token_count = budget_mgr.count_tokens(raw_content)
        truncated_content = budget_mgr.truncate_to_budget(raw_content)
        
        print("\n--- Top Result ---")
        print(f"Title: {top_skill['title']}")
        print(f"Final Score: {top_skill['score']:.4f}")
        print(f"Trust Tier: {trust_ladder_router(top_skill['score'])}")
        print(f"Token Count (Pre-truncate): {token_count}")
        print("------------------")
    else:
        print("No skills found.")
