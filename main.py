from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sqlite3
import os
import json
import logging
import asyncio
import time
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="ASCEL API (SQLite)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")
TRIGGERS_DIR = os.path.join(os.path.dirname(__file__), "triggers")

os.makedirs(TRIGGERS_DIR, exist_ok=True)

# SSE throttle: track the last time a client opened the /events/skills connection.
# If a new connection arrives within SSE_THROTTLE_SECONDS of the last one we send
# a single ping and close immediately, preventing rapid-reconnect log storms.
_sse_last_connect: float = 0.0
SSE_THROTTLE_SECONDS: float = 5.0

class LogTurnRequest(BaseModel):
    conversation_id: str
    role: str
    content: str

class SaveSkillRequest(BaseModel):
    conversation_id: str

class ChatRequest(BaseModel):
    conversation_id: str
    message: str

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

from retriever import search_skills

def build_prompt(user_query, history):
    injected_skills_text = "None"
    used_skill = None
    trust_tier = "Suggest-Only"
    reason = "default"

    # Force Context Injection logic
    candidates = search_skills(user_query)
    if candidates:
        top_candidate = candidates[0]
        logger.info(f"Top Candidate Match: '{top_candidate['title']}' | Score: {top_candidate['score']}")

        FORCE_INJECT_THRESHOLD = 0.50  # Lowered from 0.65 — accounts for keyword-only fallback scores
        if top_candidate['score'] > FORCE_INJECT_THRESHOLD:
            injected_skills_text = f"Title: {top_candidate['title']}\nSummary: {top_candidate['summary']}\nBody: {top_candidate['body_markdown']}"
            used_skill = top_candidate
            trust_tier = "Suggest-Only"
            reason = "force_injected_by_score"
            logger.info(f"Force-injected top candidate as Suggested Fix due to score > {FORCE_INJECT_THRESHOLD}")

    # --- Fix #9: Build multi-turn conversation context ---
    # Include all prior turns so the model has memory of the conversation.
    # The current user message is already the last entry in history, so we
    # render everything except the final turn as context.
    conversation_context = ""
    prior_turns = history[:-1]  # exclude the current user message already appended
    if prior_turns:
        context_lines = []
        for turn in prior_turns:
            role_label = "User" if turn["role"] == "user" else "Assistant"
            context_lines.append(f"{role_label}: {turn['content']}")
        conversation_context = "\n".join(context_lines)
        conversation_context = f"\n\nPREVIOUS CONVERSATION:\n{conversation_context}\n"

    prompt = (
        f"You are a helpful coding assistant. You have access to a verified local Knowledge Vault."
        f" INJECTED SKILLS: {injected_skills_text}"
        f" --- CRITICAL INSTRUCTION: You are provided with 'INJECTED SKILLS'."
        f" You MUST ignore any skill that is not strictly relevant to the user's specific problem domain."
        f" Do not force-fit or mention fixes that do not match the user's query context."
        f" If the fix involves a shell command, output the fix command wrapped in <execute>...</execute> tags"
        f" and a verification probe wrapped in <probe>...</probe> tags."
        f"{conversation_context}"
        f"\nUser Query: {user_query}"
    )

    return prompt, used_skill, trust_tier, reason

@app.get("/health")
def health_check():
    return {"status": "ASCEL SQLite Core Online"}

# --- Fix #3: GET /skills with real filter/search support ---
@app.get("/skills")
def get_skills(
    domain: str = None,
    tier: str = None,
    q: str = None,
    domain_type: str = None,
    vault_tier: str = None,
    search: str = None,
    limit: int = 100,
    snippet: bool = False,
):
    """Return skills with optional filtering by domain, tier, and full-text search query."""
    # Accept both old and new param names from the frontend
    effective_domain = domain_type or domain
    effective_tier = vault_tier or tier
    effective_q = search or q

    conn = get_db()
    try:
        params = []
        where_clauses = []

        if effective_domain:
            where_clauses.append("tags LIKE ?")
            params.append(f"%{effective_domain}%")

        if effective_q:
            # Simple LIKE search across title, tags, and summary as a fallback
            # (FTS5 is the primary search path in retriever.py; this keeps the list
            # endpoint self-contained and fast for small vaults.)
            like = f"%{effective_q}%"
            where_clauses.append("(title LIKE ? OR tags LIKE ? OR summary LIKE ?)")
            params.extend([like, like, like])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT id as skill_id, title, tags, tech_stack, confidence,
                   summary, body_markdown, created_at, updated_at
            FROM skills
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        cursor = conn.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]

        # Mark skills that have an embedding (is_searchable) for the UI badge
        for row in rows:
            emb_cursor = conn.execute("SELECT embedding FROM skills WHERE id = ?", (row["skill_id"],))
            emb_row = emb_cursor.fetchone()
            row["is_searchable"] = bool(emb_row and emb_row["embedding"])
            if snippet and row.get("body_markdown"):
                row["snippet"] = row["body_markdown"][:120] + "..." if len(row["body_markdown"]) > 120 else row["body_markdown"]

        return rows
    finally:
        conn.close()


@app.get("/skills/count")
def get_skills_count():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT COUNT(*) as count FROM skills")
        row = cursor.fetchone()
        return {"count": row["count"]}
    finally:
        conn.close()


# --- SSE stream for /events/skills (throttled) ---
@app.get("/events/skills")
async def get_events_skills():
    """Server-Sent Events stream with connection throttling.

    Normal clients (EventSource) hold this connection open and receive a ping
    every 15 seconds.  If a client reconnects faster than SSE_THROTTLE_SECONDS
    (e.g. due to rapid error/retry loops) we emit a single ping and close
    immediately — this stops log storms without breaking the SSE contract.
    """
    global _sse_last_connect
    now = time.monotonic()
    throttled = (now - _sse_last_connect) < SSE_THROTTLE_SECONDS
    _sse_last_connect = now

    if throttled:
        # Fast-path: send one ping and end the stream so the client backs off.
        logger.debug("SSE throttled — returning immediate ping to rapid-reconnect client")
        async def _one_shot():
            yield 'data: {"event": "ping"}\n\n'
        return StreamingResponse(
            _one_shot(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        try:
            while True:
                yield 'data: {"event": "ping"}\n\n'
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            # Client disconnected — exit cleanly
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --- Fix #1: Missing skill CRUD + preview / history / rollback endpoints ---

@app.get("/skills/{skill_id}/preview")
def get_skill_preview(skill_id: str, max_tokens: int = 2000):
    """Return full skill content and metadata for the SkillPreview modal."""
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            SELECT id as skill_id, title, tags, tech_stack, confidence,
                   summary, body_markdown, created_at, updated_at
            FROM skills WHERE id = ?
            """,
            (skill_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Skill not found")
        data = dict(row)
        # Build a combined markdown content block for the preview pane
        content_parts = []
        if data.get("summary"):
            content_parts.append(f"## Summary\n{data['summary']}")
        if data.get("body_markdown"):
            content_parts.append(data["body_markdown"])
        full_content = "\n\n".join(content_parts)
        # Rudimentary token budget: ~4 chars per token
        char_budget = max_tokens * 4
        if len(full_content) > char_budget:
            full_content = full_content[:char_budget] + "\n\n*[Content truncated to fit context budget]*"
        return {
            "skill_id": data["skill_id"],
            "title": data["title"],
            "vault_tier": "project_local",   # future: real tier from DB column
            "skill_status": "completed",       # future: real status
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "content": full_content,
        }
    finally:
        conn.close()


@app.get("/skills/{skill_id}/history")
def get_skill_history(skill_id: str):
    """Return commit history for a skill.
    NOTE: No skill_history table exists yet — returns a placeholder payload.
    A future migration will add proper version tracking.
    """
    conn = get_db()
    try:
        cursor = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")
    finally:
        conn.close()

    # Stub: return a single synthetic "created" entry so the UI renders correctly
    return {
        "skill_id": skill_id,
        "history": [
            {
                "sha": "initial",
                "full_sha": "initial",
                "message": "Skill created via distillation",
                "author": "ASCEL Distiller",
                "date": "",   # UI relativeTime() handles empty gracefully
            }
        ],
    }


@app.post("/skills/{skill_id}/rollback/{sha}")
def rollback_skill(skill_id: str, sha: str):
    """Roll a skill back to a prior commit.
    NOTE: Git-backed rollback is not yet implemented — returns simulated success.
    A future implementation will restore body_markdown from the history table.
    """
    conn = get_db()
    try:
        cursor = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")
    finally:
        conn.close()

    logger.info(f"[STUB] Rollback requested for skill {skill_id} to sha={sha}")
    return {
        "status": "ok",
        "message": f"Simulated rollback to {sha}. Full Git-backed rollback coming in a future release.",
    }


@app.delete("/skills/{skill_id}")
def delete_skill(skill_id: str):
    """Permanently delete a skill and its FTS5 index entry."""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")
        conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        conn.commit()
        logger.info(f"Deleted skill {skill_id}")
        return {"status": "deleted", "skill_id": skill_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting skill {skill_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()


@app.post("/log-turn", status_code=status.HTTP_201_CREATED)
def log_turn(req: LogTurnRequest):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO chat_journal (conversation_id, role, content) VALUES (?, ?, ?)",
            (req.conversation_id, req.role, req.content)
        )
        conn.commit()
        return {"message": "Logged successfully"}
    except Exception as e:
        logger.error(f"Error logging turn: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()

@app.post("/chat")
def handle_chat(req: ChatRequest):
    import re
    from healing_engine import HealingEngine
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO chat_journal (conversation_id, role, content) VALUES (?, ?, ?)",
            (req.conversation_id, 'user', req.message)
        )
        conn.commit()
        
        cursor = conn.execute("SELECT role, content FROM chat_journal WHERE conversation_id = ? ORDER BY timestamp ASC", (req.conversation_id,))
        chat_history = [dict(row) for row in cursor.fetchall()]
        
        prompt, used_skill, trust_tier, reason = build_prompt(req.message, chat_history)
        
        try:
            resp = requests.post("http://localhost:11434/api/generate", json={
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "keep_alive": 0
            })
            resp.raise_for_status()
            ai_text = resp.json().get("response", "No response from AI")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            ai_text = f"Error connecting to Ollama: {e}"

        conn.execute(
            "INSERT INTO chat_journal (conversation_id, role, content) VALUES (?, ?, ?)",
            (req.conversation_id, 'assistant', ai_text)
        )
        conn.commit()
        
        healing_result = None
        
        execute_match = re.search(r"<execute>(.*?)</execute>", ai_text, re.DOTALL)
        probe_match = re.search(r"<probe>(.*?)</probe>", ai_text, re.DOTALL)
        
        if execute_match:
            fix_cmd = execute_match.group(1).strip()
            probe_cmd = probe_match.group(1).strip() if probe_match else None
            healer = HealingEngine()
            
            tier_to_use = trust_tier if trust_tier else "Suggest-Only"
            healing_result = healer.run_healing_cycle(fix_cmd, probe_cmd, tier_to_use)

        if reason == "domain_mismatch":
            return {
                "response": ai_text,
                "used_skill": None,
                "reason": "domain_mismatch",
                "healing": healing_result
            }

        return {
            "response": ai_text,
            "used_skill": used_skill,
            "trust_tier": trust_tier,
            "healing": healing_result
        }
    finally:
        conn.close()

@app.get("/chats")
def get_chats():
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT conversation_id, MIN(timestamp) as ts, content FROM chat_journal WHERE role='user' GROUP BY conversation_id ORDER BY ts DESC"
        )
        chats = []
        for row in cursor.fetchall():
            title = row["content"][:30] + "..." if len(row["content"]) > 30 else row["content"]
            chats.append({"conversation_id": row["conversation_id"], "title": title})
        return chats
    finally:
        conn.close()

@app.get("/chat/{chat_id}")
def get_chat(chat_id: str):
    conn = get_db()
    try:
        cursor = conn.execute("SELECT role, content FROM chat_journal WHERE conversation_id = ? ORDER BY timestamp ASC", (chat_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

@app.delete("/chat/{chat_id}")
def delete_chat(chat_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM chat_journal WHERE conversation_id = ?", (chat_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()

@app.get("/distillation-status/{conversation_id}")
def get_distillation_status(conversation_id: str):
    trigger_file = os.path.join(TRIGGERS_DIR, f"{conversation_id}.json")
    completed_file = os.path.join(TRIGGERS_DIR, f"{conversation_id}.completed")
    failed_file = os.path.join(TRIGGERS_DIR, f"{conversation_id}.failed")

    if os.path.exists(completed_file):
        os.remove(completed_file)  # Clean up after reporting
        return {"status": "completed"}
    elif os.path.exists(failed_file):
        os.remove(failed_file)  # Clean up after reporting
        return {"status": "failed"}
    elif os.path.exists(trigger_file):
        return {"status": "processing"}
    else:
        # No trigger file → distillation was never started or already cleaned up.
        # Return "idle" so the frontend can stop polling instead of looping forever.
        return {"status": "idle"}

@app.post("/save-skill", status_code=status.HTTP_202_ACCEPTED)
def save_skill(req: SaveSkillRequest):
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT role, content, timestamp FROM chat_journal WHERE conversation_id = ? ORDER BY timestamp ASC",
            (req.conversation_id,)
        )
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="Conversation not found")

        sequence = [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]
        
        trigger_file = os.path.join(TRIGGERS_DIR, f"{req.conversation_id}.json")
        with open(trigger_file, "w", encoding="utf-8") as f:
            json.dump(sequence, f, indent=2)
            
        return {"message": f"Trigger sequence spawned at {trigger_file}"}
    except Exception as e:
        logger.error(f"Error saving skill: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting up FastAPI Server (SQLite Core)...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)