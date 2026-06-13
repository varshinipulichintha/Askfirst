from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

from database import init_db, get_db, Thread, Message, GlobalMemory

load_dotenv()
init_db()

app = FastAPI(title="AskFirst Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama3-8b-8192"


# ── Pydantic schemas ──────────────────────────────────────────────
class ThreadCreate(BaseModel):
    name: str
    thread_type: str = "general"  # "reader" | "writer" | "memory"


class ThreadOut(BaseModel):
    id: int
    name: str
    thread_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    thread_id: int
    user_message: str


class ChatResponse(BaseModel):
    reply: str
    thread_id: int


# ── Helpers ───────────────────────────────────────────────────────
def get_global_memory(db: Session) -> str:
    mem = db.query(GlobalMemory).order_by(GlobalMemory.updated_at.desc()).first()
    return mem.summary if mem else ""


def update_global_memory(db: Session, new_info: str):
    existing = db.query(GlobalMemory).first()
    if existing:
        existing.summary = new_info
        existing.updated_at = datetime.utcnow()
    else:
        db.add(GlobalMemory(summary=new_info))
    db.commit()


def build_memory_summary(db: Session) -> str:
    """Summarise ALL messages across all threads into a compact memory blob."""
    threads = db.query(Thread).all()
    if not threads:
        return ""

    parts = []
    for t in threads:
        msgs = (
            db.query(Message)
            .filter(Message.thread_id == t.id)
            .order_by(Message.created_at)
            .all()
        )
        if msgs:
            convo = "\n".join(f"  [{m.role}]: {m.content[:200]}" for m in msgs)
            parts.append(f"Thread '{t.name}' ({t.thread_type}):\n{convo}")

    if not parts:
        return ""

    full_text = "\n\n".join(parts)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a memory manager. "
                        "Summarise the following conversation history into a concise "
                        "memory block (≤300 words) that another AI can use as context."
                    ),
                },
                {"role": "user", "content": full_text},
            ],
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return full_text[:1000]


# ── Thread endpoints ──────────────────────────────────────────────
@app.get("/threads", response_model=List[ThreadOut])
def list_threads(db: Session = Depends(get_db)):
    return db.query(Thread).order_by(Thread.created_at).all()


@app.post("/threads", response_model=ThreadOut)
def create_thread(payload: ThreadCreate, db: Session = Depends(get_db)):
    thread = Thread(name=payload.name, thread_type=payload.thread_type)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@app.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete(thread)
    db.commit()
    return {"detail": "deleted"}


# ── Message endpoints ─────────────────────────────────────────────
@app.get("/threads/{thread_id}/messages", response_model=List[MessageOut])
def get_messages(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at)
        .all()
    )


# ── Chat endpoint ─────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == payload.thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Build per-thread history
    history = (
        db.query(Message)
        .filter(Message.thread_id == payload.thread_id)
        .order_by(Message.created_at)
        .all()
    )

    # Universal memory context
    global_mem = get_global_memory(db)

    # Thread-type-specific system prompts
    if thread.thread_type == "reader":
        sys_prompt = (
            "You are a DATA READER assistant. Your job is to read, retrieve, "
            "and display data from the conversation history. "
            "When asked, summarise or fetch information from past messages. "
        )
    elif thread.thread_type == "writer":
        sys_prompt = (
            "You are a DATA WRITER assistant. Your job is to help users create, "
            "structure, and store new information. Guide users in writing well-formed "
            "data entries, notes, or records. "
        )
    elif thread.thread_type == "memory":
        sys_prompt = (
            "You are a MEMORY CONSOLIDATOR assistant. Your job is to surface, "
            "connect, and synthesise information from ALL previous threads. "
            "Help users recall past conversations and find patterns across threads. "
        )
    else:
        sys_prompt = "You are a helpful AI assistant."

    if global_mem:
        sys_prompt += f"\n\n[Universal Memory from past threads]\n{global_mem}"

    messages = [{"role": "system", "content": sys_prompt}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": payload.user_message})

    # Call LLM
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=800,
    )
    reply = resp.choices[0].message.content.strip()

    # Persist user + assistant messages
    db.add(Message(thread_id=thread.id, role="user", content=payload.user_message))
    db.add(Message(thread_id=thread.id, role="assistant", content=reply))
    db.commit()

    # Refresh global memory after every exchange
    summary = build_memory_summary(db)
    if summary:
        update_global_memory(db, summary)

    return ChatResponse(reply=reply, thread_id=thread.id)


# ── Memory endpoints ──────────────────────────────────────────────
@app.get("/memory")
def get_memory(db: Session = Depends(get_db)):
    mem = get_global_memory(db)
    return {"memory": mem}


@app.post("/memory/refresh")
def refresh_memory(db: Session = Depends(get_db)):
    summary = build_memory_summary(db)
    if summary:
        update_global_memory(db, summary)
    return {"memory": summary, "detail": "Memory refreshed"}
