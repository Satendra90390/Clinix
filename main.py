"""
ClinixAI — AI-Powered Medical Platform
Backend: FastAPI + SQLite/PostgreSQL + OpenFDA Drug Database
Optimized for Vercel Deployment
"""
import os
import re
import json
import logging
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Logging configuration (Vercel-safe)
IS_VERCEL = os.getenv("VERCEL") or os.getenv("NOW_REGION")
log_handlers = [logging.StreamHandler()]
if not IS_VERCEL:
    try:
        log_handlers.append(logging.FileHandler("clinixai.log"))
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Database setup (Vercel-safe with SSL)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "neon.tech" in DATABASE_URL and "sslmode" not in DATABASE_URL:
        separator = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL += f"{separator}sslmode=require"
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine("sqlite:///medguide.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    user_type = Column(String(20), nullable=False)
    profile_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class Guideline(Base):
    __tablename__ = "guidelines"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    medicines = Column(JSON, default=list)
    severity = Column(String(20), default="mild")
    steps = Column(JSON, default=list)
    video_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmergencyProtocol(Base):
    __tablename__ = "emergency_protocols"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    icon = Column(String(50))
    duration_minutes = Column(Integer, default=0)
    steps = Column(JSON, nullable=False)
    audio_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DrugCache(Base):
    __tablename__ = "drug_cache"
    id = Column(Integer, primary_key=True, index=True)
    drug_name = Column(String(200), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    cached_at = Column(DateTime, default=datetime.utcnow)

# Database Tables Creation
Base.metadata.create_all(bind=engine)

# Helper functions
def safe_json_loads(data):
    if data is None: return []
    if isinstance(data, (list, dict)): return data
    try:
        if isinstance(data, str) and data.strip():
            return json.loads(data)
    except: pass
    return []

def extract_steps(summary):
    steps = []
    pattern = r'(\d+)[\.\)]\s*([^1-9]+?)(?=\d+[\.\)]|$)'
    matches = re.findall(pattern, summary, re.DOTALL)
    if matches:
        steps = [step_text.strip() for _, step_text in matches]
    else:
        sentences = re.split(r'(?<=[.!?])\s+', summary)
        steps = [s.strip() for s in sentences if len(s.strip()) > 10]
    return steps

MEDICINES_MAP = {
    "cuts": ["Acetaminophen", "Antiseptic Cream"],
    "abrasions": ["Antibiotic Ointment", "Aquaphor"],
    "stings": ["Benadryl", "Hydrocortisone Cream"],
    "sprains": ["Ibuprofen", "Ice Pack"],
    "fever": ["Acetaminophen", "Ibuprofen"],
    "cough": ["Honey", "Guaifenesin"],
    "headache": ["Aspirin", "Acetaminophen"],
}

SEVERITY_MAP = {
    "snake bite": "critical", "drowning": "critical", "cpr": "critical",
    "heart attack": "critical", "stroke": "critical", "choking": "critical",
    "fracture": "urgent", "wound": "urgent", "burns": "urgent",
    "fever": "moderate", "sprains": "moderate"
}

SYMPTOM_TRIAGE = {
    "fever": {"conditions": ["Infection", "Heat Stroke"], "triage": "first_aid"},
    "chest pain": {"conditions": ["Heart Attack", "Angina"], "triage": "emergency"},
    "breathing": {"conditions": ["Asthma", "Allergic Reaction"], "triage": "emergency"},
}

def enrich_guideline(title, summary=""):
    title_lower = title.lower()
    medicines = []
    severity = "mild"
    for key, meds in MEDICINES_MAP.items():
        if key in title_lower: medicines = meds; break
    for key, sev in SEVERITY_MAP.items():
        if key in title_lower: severity = sev; break
    return medicines, severity, extract_steps(summary)

# FDA API interaction
async def fetch_drug_from_fda(drug_name: str):
    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name}+OR+openfda.generic_name:{drug_name}&limit=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("results"):
                        result = data["results"][0]
                        return {
                            "drug_name": drug_name,
                            "purpose": result.get("purpose", ["N/A"])[0] if result.get("purpose") else "N/A",
                            "dosage": result.get("dosage_and_administration", ["N/A"])[0][:500] if result.get("dosage_and_administration") else "N/A",
                            "side_effects": result.get("warnings", ["N/A"])[0][:500] if result.get("warnings") else "N/A",
                            "interactions": result.get("drug_interactions", ["N/A"])[0][:500] if result.get("drug_interactions") else "None found",
                            "source": "FDA Open Data"
                        }
    except Exception as e:
        logger.error(f"FDA API error: {e}")
    return None

# Dependency
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Lifespan for Seeding
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if db.query(Guideline).count() == 0:
            json_path = os.path.join(os.path.dirname(__file__), "guidelines.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    db.add(Guideline(
                        title=item.get("title", ""),
                        summary=item.get("summary", ""),
                        category=item.get("category", "First Aid"),
                        medicines=item.get("medicines", []),
                        severity=item.get("severity", "mild"),
                        steps=extract_steps(item.get("summary", ""))
                    ))
                db.commit()
    finally: db.close()
    yield

# App Init
app = FastAPI(title="ClinixAI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Static & Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    try:
        guidelines = db.query(Guideline).order_by(Guideline.id).all()
        processed = []
        for g in guidelines:
            processed.append({
                "id": g.id, "title": g.title, "summary": g.summary, "category": g.category,
                "severity": g.severity or "mild", "medicines": safe_json_loads(g.medicines),
                "steps": safe_json_loads(g.steps), "video_url": g.video_url
            })
        
        categories = ["First Aid", "Emergency", "Mental Health", "Nutrition", "Lifestyle", "Chronic Conditions"]
        try:
            db_cats = [c[0] for c in db.query(Guideline.category).distinct().all() if c[0]]
            if db_cats: categories = list(set(categories + db_cats))
        except: pass

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "guidelines": processed,
                "categories": categories,
                "disclaimer": "For educational purposes only. Not medical advice.",
                "app_version": "1.1.0"
            }
        )
    except Exception as e:
        logger.error(f"Root error: {e}")
        return HTMLResponse(content=f"<h1>System error</h1><p>{str(e)}</p>", status_code=500)

@app.get("/health")
async def health(db: Session = Depends(get_db)):
    return {
        "status": "healthy",
        "guidelines": db.query(Guideline).count(),
        "time": datetime.utcnow().isoformat()
    }

# --- APIs ---

@app.get("/api/guidelines")
async def get_guidelines_api(category: str = None, db: Session = Depends(get_db)):
    query = db.query(Guideline)
    if category: query = query.filter(Guideline.category == category)
    results = query.all()
    for g in results:
        g.medicines = safe_json_loads(g.medicines)
        g.steps = safe_json_loads(g.steps)
    return results

@app.get("/api/drugs/search")
async def search_drugs(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    cached = db.query(DrugCache).filter(DrugCache.drug_name.ilike(f"%{q}%")).first()
    if cached and cached.cached_at > datetime.utcnow() - timedelta(hours=24):
        return {"source": "cache", "data": safe_json_loads(cached.data)}
    
    fda_data = await fetch_drug_from_fda(q)
    if fda_data:
        db.add(DrugCache(drug_name=q, data=json.dumps(fda_data)))
        db.commit()
        return {"source": "fda", "data": fda_data}
    return {"error": "Not found"}

@app.get("/api/symptoms/check")
async def check_symptoms(symptoms: str):
    s_list = [s.strip().lower() for s in symptoms.split(",")]
    results = []
    for s in s_list:
        for k, v in SYMPTOM_TRIAGE.items():
            if k in s or s in k:
                results.append({"symptom": s, "triage": v["triage"], "conditions": v["conditions"]})
    return results

@app.get("/api/emergency-protocols")
async def get_protocols_api(db: Session = Depends(get_db)):
    return db.query(EmergencyProtocol).all()

@app.post("/api/guidelines")
async def create_guideline(g: dict, db: Session = Depends(get_db)):
    meds, sev, stps = enrich_guideline(g["title"], g.get("summary", ""))
    new_g = Guideline(
        title=g["title"], summary=g.get("summary", ""), category=g.get("category", "First Aid"),
        medicines=meds, severity=sev, steps=stps
    )
    db.add(new_g)
    db.commit()
    db.refresh(new_g)
    return new_g

# Export app for Vercel
app = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
