import os
import json
import logging
from typing import Set, Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.database import get_db_pool, close_db_pool, init_db
from backend.seed_synthetic_data import seed_synthetic_data
from agent.main import VoiceAgentPipeline

load_dotenv()
logger = logging.getLogger("aaa_setu.api")
logging.basicConfig(level=logging.INFO)

# Active WebSocket Connections Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: dict):
        if not self.active_connections:
            return
        payload = json.dumps({"event": event_type, "data": data}, default=str)
        dead = set()
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead.add(conn)
        for d in dead:
            self.active_connections.discard(d)

manager = ConnectionManager()
pipeline = VoiceAgentPipeline()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing AAA-Setu FastAPI backend...")
    await init_db()
    yield
    logger.info("Shutting down AAA-Setu FastAPI backend...")
    await close_db_pool()

app = FastAPI(
    title="AAA-Setu (ANMOL-Sahayak) API",
    description="Real-time, noise-resilient voice AI bridge built on Gnani Artha Sovereign Stack with Neon PostgreSQL",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class VoiceProcessTextRequest(BaseModel):
    spoken_text: str
    source_role: str = "ASHA_RELAY"
    language_code: str = "hi-IN"
    offline_poshan: bool = False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and accept client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.get("/api/health")
async def health_check():
    pool = await get_db_pool()
    db_connected = False
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT 1")
        db_connected = (val == 1)

    has_gnani_key = bool(os.environ.get("GNANI_API_KEY"))
    return {
        "status": "healthy",
        "database_connected": db_connected,
        "gnani_key_configured": has_gnani_key,
        "active_ws_clients": len(manager.active_connections)
    }

@app.post("/api/voice/process")
async def process_voice(
    spoken_text: Optional[str] = Form(None),
    source_role: str = Form("ASHA_RELAY"),
    language_code: str = Form("hi-IN"),
    offline_poshan: bool = Form(False),
    audio_file: Optional[UploadFile] = File(None)
):
    """
    Main voice processing endpoint:
    Runs Prisma STT (if audio file), Evon v3.3 extraction, triage calculation,
    and Timbre TTS synthesis. Broadcasts results to frontend over WebSocket.
    """
    try:
        audio_bytes = None
        if audio_file:
            audio_bytes = await audio_file.read()

        if not audio_bytes and not spoken_text:
            raise HTTPException(status_code=400, detail="Must provide either audio_file or spoken_text.")

        result = await pipeline.process_frontline_relay(
            audio_bytes=audio_bytes,
            spoken_text=spoken_text,
            source_role=source_role,
            language_code=language_code,
            offline_poshan=offline_poshan
        )

        # Broadcast live events across triad dashboard (<50ms target)
        await manager.broadcast("voice_processed", result)
        await manager.broadcast("anmol_queue_updated", {"action": "new_entry", "queue_id": result.get("queue_id")})
        if result.get("poshan"):
            await manager.broadcast("poshan_synced", result["poshan"])
        if result.get("paper_register"):
            await manager.broadcast("register_row_added", result["paper_register"])

        return result
    except Exception as e:
        logger.exception("Error processing voice session")
        # Surface exact error directly
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice/process-json")
async def process_voice_json(req: VoiceProcessTextRequest):
    """
    Convenience JSON endpoint for test suites and simulator presets.
    """
    try:
        result = await pipeline.process_frontline_relay(
            spoken_text=req.spoken_text,
            source_role=req.source_role,
            language_code=req.language_code,
            offline_poshan=req.offline_poshan
        )

        await manager.broadcast("voice_processed", result)
        await manager.broadcast("anmol_queue_updated", {"action": "new_entry", "queue_id": result.get("queue_id")})
        if result.get("poshan"):
            await manager.broadcast("poshan_synced", result["poshan"])
        if result.get("paper_register"):
            await manager.broadcast("register_row_added", result["paper_register"])

        return result
    except Exception as e:
        logger.exception("Error processing voice json")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/anmol/queue")
async def get_anmol_queue(asha_worker_name: Optional[str] = None):
    """
    Skill 1 / ANM Tablet View:
    Returns the ASHA-wise pre-filled verification queue for the ANM.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if asha_worker_name and asha_worker_name != "ALL":
            rows = await conn.fetch(
                """
                SELECT q.*, c.mother_name, c.village
                FROM anmol_verification_queue q
                LEFT JOIN synthetic_mcp_cards c ON q.rch_id = c.rch_id
                WHERE q.asha_worker_name ILIKE $1
                ORDER BY q.created_at DESC;
                """,
                f"%{asha_worker_name}%"
            )
        else:
            rows = await conn.fetch(
                """
                SELECT q.*, c.mother_name, c.village
                FROM anmol_verification_queue q
                LEFT JOIN synthetic_mcp_cards c ON q.rch_id = c.rch_id
                ORDER BY q.created_at DESC;
                """
            )
        return [dict(r) for r in rows]

@app.post("/api/anmol/approve/{queue_id}")
async def approve_anmol_queue_item(queue_id: int):
    """
    Skill 1 / Step 7:
    One-Tap Approval by ANM: Syncs the pre-filled verification card to the RCH Portal.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE anmol_verification_queue
            SET anm_approval_status = 'SYNCED_TO_RCH'
            WHERE queue_id = $1
            RETURNING *;
            """,
            queue_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Queue item not found.")

        result = dict(row)
        await manager.broadcast("anmol_queue_updated", {"action": "approved", "queue_id": queue_id, "data": result})
        return result

@app.get("/api/poshan/visits")
async def get_poshan_visits():
    """
    Skill 4 / AWW View:
    Returns MWCD Poshan Tracker joint visits with offline cache and sync status.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM poshan_joint_visits ORDER BY created_at DESC;"
        )
        return [dict(r) for r in rows]

@app.post("/api/poshan/sync/{visit_id}")
async def sync_poshan_visit(visit_id: int):
    """
    Step 8: Sync an offline cached Poshan visit to MWCD server.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE poshan_joint_visits
            SET sync_status = 'SYNCED_MWCD'
            WHERE visit_id = $1
            RETURNING *;
            """,
            visit_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Poshan visit record not found.")

        result = dict(row)
        await manager.broadcast("poshan_synced", result)
        return result

@app.get("/api/paper-register")
async def get_paper_register():
    """
    Skill 5 / Physical Audit View:
    Returns physical audit register rows.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM paper_register_records ORDER BY created_at DESC;"
        )
        return [dict(r) for r in rows]

@app.get("/api/beneficiaries")
async def get_beneficiaries():
    """
    Returns baseline synthetic MCP Cards.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM synthetic_mcp_cards ORDER BY rch_id ASC;"
        )
        return [dict(r) for r in rows]

@app.post("/api/reset")
async def reset_demo_database():
    """
    Resets the database back to initial seed data for demo presentations.
    """
    await seed_synthetic_data(reset=True)
    await manager.broadcast("database_reset", {"message": "Demo state reset to baseline seed data."})
    return {"status": "success", "message": "Demo state reset successfully."}

