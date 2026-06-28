import os
import time
import json
import uuid
import sqlite3
import hashlib
import logging
import requests
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")
TRIGGERS_DIR = os.path.join(os.path.dirname(__file__), "triggers")
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

class ExtractedSkill(BaseModel):
    title: str = Field(description="A short, descriptive title for the skill")
    tags: str = Field(description="Comma-separated list of relevant tags")
    tech_stack: str = Field(description="Comma-separated list of technologies involved")
    summary: str = Field(description="A concise summary of the issue and solution")
    body_markdown: str = Field(description="Step-by-step causal chain: Error -> Diagnosis -> Fix -> Verification in Markdown")

schema_str = ExtractedSkill.schema_json()

SYSTEM_PROMPT = f"""You are an expert AI distillation engine.
Your task is to analyze the provided chat logs and extract the core knowledge into a reusable skill.
You MUST return a JSON object that strictly adheres to the following JSON schema:
{schema_str}

Extract the causal chain (Error -> Diagnosis -> Fix -> Verification) from the chat logs and populate the fields accordingly.
"""

def process_trigger(filepath):
    logger.info(f"Processing trigger file: {filepath}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            chat_logs = json.load(f)
        
        chat_logs_str = json.dumps(chat_logs, indent=2)
        
        # 1. Ollama Execution
        logger.info(f"Sending prompt to Ollama ({MODEL_NAME})...")
        payload = {
            "model": MODEL_NAME,
            "prompt": f"{SYSTEM_PROMPT}\n\nChat Logs:\n{chat_logs_str}",
            "format": "json",
            "stream": False
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        result_json = response.json().get("response", "{}")
        
        # 2. VRAM Safety: Evict Model
        logger.info(f"Evicting model {MODEL_NAME} from VRAM...")
        evict_payload = {
            "model": MODEL_NAME,
            "keep_alive": 0
        }
        requests.post(OLLAMA_API_URL, json=evict_payload)
        
        # 3. Database Storage
        extracted_data = json.loads(result_json)
        skill = ExtractedSkill(**extracted_data)
        
        skill_id = str(uuid.uuid4())
        conversation_hash = hashlib.sha256(chat_logs_str.encode('utf-8')).hexdigest()
        confidence = 0.5
        now_iso = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Saving extracted skill to database (ID: {skill_id})...")
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                """INSERT INTO skills 
                   (id, title, tags, tech_stack, summary, body_markdown, conversation_hash, confidence, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (skill_id, skill.title, skill.tags, skill.tech_stack, skill.summary, skill.body_markdown, 
                 conversation_hash, confidence, now_iso, now_iso)
            )
            conn.commit()
            logger.info("Skill successfully saved.")
        finally:
            conn.close()
            
        # 4. Cleanup
        logger.info(f"Marking trigger file as completed: {filepath}")
        os.rename(filepath, filepath.replace('.json', '.completed'))
        
    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}")
        try:
            os.rename(filepath, filepath.replace('.json', '.failed'))
        except:
            pass

class TriggerHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f"Detected new trigger file: {event.src_path}")
            # Slight delay to ensure file is fully written before reading
            time.sleep(1)
            process_trigger(event.src_path)

def process_existing_files():
    if not os.path.exists(TRIGGERS_DIR):
        os.makedirs(TRIGGERS_DIR)
    
    for filename in os.listdir(TRIGGERS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(TRIGGERS_DIR, filename)
            logger.info(f"Found existing trigger file on startup: {filepath}")
            process_trigger(filepath)

if __name__ == '__main__':
    logger.info("Starting Event-Driven Distillation Engine...")
    
    # Process any pre-existing triggers before starting the observer
    process_existing_files()
    
    event_handler = TriggerHandler()
    observer = Observer()
    observer.schedule(event_handler, TRIGGERS_DIR, recursive=False)
    observer.start()
    
    logger.info(f"Monitoring directory: {TRIGGERS_DIR} for new triggers.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
