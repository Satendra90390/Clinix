import os
import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Environment & Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 2. Database Setup (Robust URL)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "neon.tech" in DATABASE_URL and "sslmode" not in DATABASE_URL:
        DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///medguide.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Models
class Guideline(Base):
    __tablename__ = "guidelines"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    medicines = Column(JSON, default=list)
    severity = Column(String(20), default="mild")
    steps = Column(JSON, default=list)
    video_url = Column(String(500))

# 4. App Initialization
app = FastAPI(title="ClinixAI")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Paths & Templates (Vercel Robust)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 6. Helpers
def safe_data(val):
    if val is None: return []
    if isinstance(val, (list, dict)): return val
    try: return json.loads(val)
    except: return []

# 7. Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    try:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "guidelines": [],
                "categories": [],
                "disclaimer": "Debug mode",
                "app_version": "1.0.5"
            }
        )
    except Exception as e:
        return HTMLResponse(content=f"<h1>Setup Error</h1><p>{str(e)}</p>", status_code=200)

@app.get("/health")
async def health():
    return {"status": "ok", "time": str(datetime.now())}

# Export for Vercel
app = app
