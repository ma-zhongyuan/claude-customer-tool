from __future__ import annotations

import os
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "app.db"
STATIC_DIR = BASE_DIR / "static"

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "12000"))
DEFAULT_INITIAL_CREDITS = int(os.getenv("DEFAULT_INITIAL_CREDITS", "20"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")

SYSTEM_PROMPT = """
你是一个面向中文用户的代码助手。
目标：帮助用户理解报错、修复代码、解释逻辑、补充测试、重构小段代码。
规则：
1. 先直接给结论，再给原因。
2. 如果用户贴了报错，优先定位最可能原因。
3. 修改代码时，尽量给出可直接复制的版本。
4. 回答保持简洁，除非用户要求详细讲解。
5. 不输出与编程无关的闲聊。
""".strip()

app = FastAPI(title="Claude Code Assistant - Customer Edition")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            access_code TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_code TEXT NOT NULL,
            prompt TEXT NOT NULL,
            code TEXT,
            language TEXT,
            model TEXT NOT NULL,
            credits_used INTEGER NOT NULL,
            answer TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(access_code) REFERENCES users(access_code)
        )
        """
    )
    conn.commit()
    conn.close()


def estimate_credit_cost(prompt: str, code: Optional[str]) -> int:
    total_chars = len(prompt) + len(code or "")
    if total_chars <= 800:
        return 1
    if total_chars <= 2500:
        return 2
    if total_chars <= 6000:
        return 3
    return 5


def extract_text(response) -> str:
    parts = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


class LoginRequest(BaseModel):
    access_code: str = Field(min_length=4, max_length=64)


class ChatRequest(BaseModel):
    access_code: str = Field(min_length=4, max_length=64)
    prompt: str = Field(min_length=2, max_length=MAX_INPUT_CHARS)
    code: Optional[str] = Field(default="", max_length=MAX_INPUT_CHARS)
    language: Optional[str] = Field(default="")


class AdminCreateRequest(BaseModel):
    admin_password: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=40)
    initial_credits: int = Field(default=DEFAULT_INITIAL_CREDITS, ge=1, le=100000)
    access_code: Optional[str] = Field(default=None, max_length=64)


class AdminRechargeRequest(BaseModel):
    admin_password: str = Field(min_length=1, max_length=100)
    access_code: str = Field(min_length=4, max_length=64)
    add_credits: int = Field(ge=1, le=100000)


class AdminListRequest(BaseModel):
    admin_password: str = Field(min_length=1, max_length=100)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "customer.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


def require_admin(password: str) -> None:
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="管理员密码错误")


def generate_code() -> str:
    return secrets.token_hex(4).upper()


@app.post("/api/login")
def login(data: LoginRequest):
    code = data.access_code.strip().upper()
    conn = get_conn()
    row = conn.execute(
        "SELECT access_code, display_name, credits, is_active FROM users WHERE access_code = ?",
        (code,),
    ).fetchone()
    conn.close()
    if not row or row["is_active"] != 1:
        raise HTTPException(status_code=404, detail="访问码不存在或已停用")
    return {
        "ok": True,
        "access_code": row["access_code"],
        "display_name": row["display_name"],
        "credits": row["credits"],
    }


@app.post("/api/chat")
def chat(data: ChatRequest):
    if Anthropic is None:
        raise HTTPException(status_code=500, detail="anthropic SDK 未安装")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="服务端未配置 ANTHROPIC_API_KEY")

    code_key = data.access_code.strip().upper()
    prompt = data.prompt.strip()
    code = (data.code or "").strip()
    language = (data.language or "").strip()

    total_chars = len(prompt) + len(code)
    if total_chars > MAX_INPUT_CHARS:
        raise HTTPException(status_code=400, detail=f"输入太长，当前上限为 {MAX_INPUT_CHARS} 个字符")

    credits_needed = estimate_credit_cost(prompt, code)

    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT access_code, display_name, credits, is_active FROM users WHERE access_code = ?",
        (code_key,),
    ).fetchone()
    if not row or row["is_active"] != 1:
        conn.close()
        raise HTTPException(status_code=404, detail="访问码不存在或已停用")
    if row["credits"] < credits_needed:
        conn.close()
        raise HTTPException(status_code=402, detail=f"额度不足，本次需要 {credits_needed} 点，请联系客服充值")

    user_content = f"问题：\n{prompt}\n\n"
    if language:
        user_content += f"语言/技术栈：{language}\n\n"
    if code:
        user_content += f"代码或报错：\n```\n{code}\n```"

    try:
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        answer = extract_text(resp)
        if not answer:
            raise RuntimeError("模型未返回文本")
    except Exception as exc:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Claude 调用失败：{exc}")

    cur.execute("UPDATE users SET credits = credits - ? WHERE access_code = ?", (credits_needed, code_key))
    cur.execute(
        """
        INSERT INTO chat_logs(access_code, prompt, code, language, model, credits_used, answer)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (code_key, prompt, code, language, DEFAULT_MODEL, credits_needed, answer),
    )
    conn.commit()
    updated = cur.execute("SELECT credits, display_name FROM users WHERE access_code = ?", (code_key,)).fetchone()
    conn.close()

    return {
        "ok": True,
        "answer": answer,
        "credits_used": credits_needed,
        "credits_left": updated["credits"],
        "display_name": updated["display_name"],
        "model": DEFAULT_MODEL,
    }


@app.post("/api/admin/create_user")
def create_user(data: AdminCreateRequest):
    require_admin(data.admin_password)
    access_code = (data.access_code.strip().upper() if data.access_code else generate_code())
    conn = get_conn()
    cur = conn.cursor()
    existing = cur.execute("SELECT access_code FROM users WHERE access_code = ?", (access_code,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="访问码已存在，请换一个")

    cur.execute(
        "INSERT INTO users(access_code, display_name, credits) VALUES(?, ?, ?)",
        (access_code, data.display_name.strip(), data.initial_credits),
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "access_code": access_code,
        "display_name": data.display_name.strip(),
        "credits": data.initial_credits,
    }


@app.post("/api/admin/recharge")
def recharge_user(data: AdminRechargeRequest):
    require_admin(data.admin_password)
    code = data.access_code.strip().upper()
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT access_code, credits FROM users WHERE access_code = ?", (code,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="访问码不存在")
    cur.execute("UPDATE users SET credits = credits + ? WHERE access_code = ?", (data.add_credits, code))
    conn.commit()
    updated = cur.execute("SELECT credits FROM users WHERE access_code = ?", (code,)).fetchone()
    conn.close()
    return {"ok": True, "access_code": code, "credits": updated["credits"]}


@app.post("/api/admin/list_users")
def list_users(data: AdminListRequest):
    require_admin(data.admin_password)
    conn = get_conn()
    rows = conn.execute(
        "SELECT access_code, display_name, credits, is_active, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return {
        "ok": True,
        "users": [
            {
                "access_code": r["access_code"],
                "display_name": r["display_name"],
                "credits": r["credits"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }
