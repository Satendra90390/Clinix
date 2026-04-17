"""
ClinixAI — AI-Powered Medical Platform
Backend: FastAPI + SQLite/PostgreSQL + OpenFDA Drug Database
"""
import os
import re
import json
import logging
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("clinixai.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///medguide.db")

# Use SQLite for development, PostgreSQL for production
if DATABASE_URL.startswith("postgres"):
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
    user_type = Column(String(20), nullable=False)  # patient, medic, student
    profile_data = Column(JSON, default=dict)  # medical history, blood type, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class Guideline(Base):
    __tablename__ = "guidelines"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(50))
    medicines = Column(JSON, default=list)
    severity = Column(String(20), default="mild")  # mild, moderate, urgent, critical
    steps = Column(JSON, default=list)
    video_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SymptomCondition(Base):
    __tablename__ = "symptom_conditions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    symptoms = Column(JSON, nullable=False)
    triage_level = Column(String(20), nullable=False)  # first_aid, doctor, emergency
    description = Column(Text)
    prevention = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

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

class UserBookmark(Base):
    __tablename__ = "user_bookmarks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guideline_id = Column(Integer, ForeignKey("guidelines.id"))
    drug_name = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auto-enrichment data
MEDICINES_MAP = {
    "cuts": ["Acetaminophen (Tylenol)", "Petroleum Jelly", "Antiseptic Cream"],
    "abrasions": ["Bacitracin Ointment", "Aquaphor", "Antibiotic Ointment"],
    "stings": ["Diphenhydramine (Benadryl)", "Loratadine (Claritin)", "Hydrocortisone Cream"],
    "sprains": ["Ibuprofen (Advil)", "Naproxen Sodium (Aleve)", "Ice Pack"],
    "fever": ["Acetaminophen (Tylenol)", "Ibuprofen (Advil)"],
    "cough": ["Honey", "Dextromethorphan (Robitussin)", "Guaifenesin (Mucinex)"],
    "headache": ["Ibuprofen (Advil)", "Aspirin", "Acetaminophen (Tylenol)"],
    "fracture": ["Ibuprofen (Advil)", "Acetaminophen (Tylenol)"],
}

SEVERITY_MAP = {
    "snake bite": "critical",
    "drowning": "critical",
    "cpr": "critical",
    "choking": "critical",
    "heart attack": "critical",
    "stroke": "critical",
    "fracture": "urgent",
    "animal bite": "urgent",
    "wound": "urgent",
    "burns": "urgent",
    "fever": "moderate",
    "sprains": "moderate",
}

SYMPTOM_TRIAGE = {
    "fever": {"conditions": ["Fever", "Infection", "Heat Stroke"], "triage": "first_aid"},
    "headache": {"conditions": ["Headache", "Migraine", "Dehydration"], "triage": "first_aid"},
    "chest pain": {"conditions": ["Heart Attack", "Angina", "Panic Attack"], "triage": "emergency"},
    "difficulty breathing": {"conditions": ["Asthma Attack", "Allergic Reaction", "COPD"], "triage": "emergency"},
    "bleeding": {"conditions": ["Severe Bleeding", "Wound", "Internal Bleeding"], "triage": "emergency"},
    "confusion": {"conditions": ["Stroke", "Hypoglycemia", "Heat Stroke"], "triage": "emergency"},
    "cough": {"conditions": ["Cold", "Bronchitis", "Pneumonia"], "triage": "doctor"},
    "rash": {"conditions": ["Allergic Reaction", "Skin Infection", "Eczema"], "triage": "doctor"},
    "vomiting": {"conditions": ["Food Poisoning", "Gastroenteritis", "Migraine"], "triage": "doctor"},
    "dizziness": {"conditions": ["Dehydration", "Low Blood Sugar", "Vertigo"], "triage": "first_aid"},
}

# Drug API - OpenFDA
async def fetch_drug_from_fda(drug_name: str):
    """Fetch drug information from OpenFDA API"""
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
                            "interactions": result.get("drug_interactions", ["N/A"])[0][:500] if result.get("drug_interactions") else "No known interactions found",
                            "storage": result.get("storage_and_handling", ["Store at room temperature"])[0] if result.get("storage_and_handling") else "Store at room temperature",
                            "source": "FDA Open Data",
                            "cached_at": datetime.utcnow().isoformat()
                        }
    except Exception as e:
        logger.error(f"FDA API error: {e}")
    return None

# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed initial data
    db = SessionLocal()
    try:
        # Check if guidelines exist
        count = db.query(Guideline).count()
        if count == 0:
            # Import from JSON if exists
            json_path = Path(__file__).parent / "guidelines.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    steps = extract_steps(item.get("summary", ""))
                    guideline = Guideline(
                        id=item.get("id"),
                        title=item.get("title", ""),
                        summary=item.get("summary", ""),
                        category=item.get("category", "First Aid"),
                        medicines=item.get("medicines", []),
                        severity=item.get("severity", "mild"),
                        steps=steps
                    )
                    db.add(guideline)
                db.commit()
                logger.info(f"Seeded {len(data)} guidelines")
    finally:
        db.close()
    yield

# FastAPI app
app = FastAPI(
    title="ClinixAI",
    version="1.0.0",
    description="AI-Powered Medical Platform — Symptom Checker, Drug Database, Emergency Protocols",
    lifespan=lifespan
)

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions
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

def enrich_guideline(title, summary=""):
    title_lower = title.lower()
    medicines = []
    severity = "mild"
    for key, meds in MEDICINES_MAP.items():
        if key in title_lower:
            medicines = meds
            break
    for key, sev in SEVERITY_MAP.items():
        if key in title_lower:
            severity = sev
            break
    steps = extract_steps(summary)
    return medicines, severity, steps

# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    db = SessionLocal()
    try:
        guidelines = db.query(Guideline).order_by(Guideline.id).all()
        guidelines_data = []
        for g in guidelines:
            guideline_dict = {
                'id': g.id,
                'title': g.title,
                'summary': g.summary,
                'category': g.category,
                'severity': g.severity,
                'medicines': json.loads(g.medicines) if isinstance(g.medicines, str) else (g.medicines or []),
                'steps': json.loads(g.steps) if isinstance(g.steps, str) else (g.steps or []),
                'video_url': g.video_url,
            }
            guidelines_data.append(guideline_dict)
        categories = [c[0] for c in db.query(Guideline.category).distinct().all()]
        return templates.TemplateResponse("index.html", {
            "request": request,
            "guidelines": guidelines_data,
            "categories": categories,
            "disclaimer": "For educational purposes only. Not medical advice. Consult a licensed healthcare provider.",
            "app_version": "1.0.0"
        })
    finally:
        db.close()

@app.get("/health")
async def health_check():
    db = SessionLocal()
    try:
        return {
            "status": "healthy",
            "app": "ClinixAI",
            "version": "1.0.0",
            "database": "PostgreSQL" if DATABASE_URL.startswith("postgres") else "SQLite",
            "guidelines": db.query(Guideline).count(),
            "protocols": db.query(EmergencyProtocol).count()
        }
    finally:
        db.close()

# ===================== GUIDELINES API =====================
@app.get("/api/guidelines")
async def get_guidelines(category: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(Guideline)
    if category:
        query = query.filter(Guideline.category == category)
    guidelines = query.order_by(Guideline.id).all()
    for g in guidelines:
        g.medicines = json.loads(g.medicines) if isinstance(g.medicines, str) else (g.medicines or [])
        g.steps = json.loads(g.steps) if isinstance(g.steps, str) else (g.steps or [])
    return {"count": len(guidelines), "data": guidelines}

@app.get("/api/guidelines/{g_id}")
async def get_guideline(g_id: int, db: Session = Depends(get_db)):
    guideline = db.query(Guideline).filter(Guideline.id == g_id).first()
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    guideline.medicines = json.loads(guideline.medicines) if isinstance(guideline.medicines, str) else (guideline.medicines or [])
    guideline.steps = json.loads(guideline.steps) if isinstance(guideline.steps, str) else (guideline.steps or [])
    return {"data": guideline}

@app.post("/api/guidelines", status_code=201)
async def create_guideline(g: dict, db: Session = Depends(get_db)):
    title = g.get("title", "").strip()
    summary = g.get("summary", "").strip()
    category = g.get("category", "First Aid")
    
    existing = db.query(Guideline).filter(Guideline.title.ilike(title)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Guideline with this title already exists")
    
    medicines, severity, steps = enrich_guideline(title, summary)
    
    guideline = Guideline(
        title=title,
        summary=summary,
        category=category,
        medicines=medicines,
        severity=severity,
        steps=steps
    )
    db.add(guideline)
    db.commit()
    db.refresh(guideline)
    logger.info(f"Created guideline: {title}")
    
    return {"message": "Guideline created", "data": guideline, "auto_enriched": {"medicines": medicines, "severity": severity}}

@app.put("/api/guidelines/{g_id}")
async def update_guideline(g_id: int, g: dict, db: Session = Depends(get_db)):
    guideline = db.query(Guideline).filter(Guideline.id == g_id).first()
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    
    if "title" in g: guideline.title = g["title"]
    if "summary" in g:
        guideline.summary = g["summary"]
        guideline.steps = extract_steps(g["summary"])
    if "category" in g: guideline.category = g["category"]
    if "severity" in g: guideline.severity = g["severity"]
    if "medicines" in g: guideline.medicines = json.dumps(g["medicines"])
    if "video_url" in g: guideline.video_url = g["video_url"]
    
    guideline.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(guideline)
    
    return {"message": "Guideline updated", "data": guideline}

@app.delete("/api/guidelines/{g_id}")
async def delete_guideline(g_id: int, db: Session = Depends(get_db)):
    guideline = db.query(Guideline).filter(Guideline.id == g_id).first()
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    db.delete(guideline)
    db.commit()
    return {"message": "Guideline deleted"}

# ===================== DRUG DATABASE API =====================
@app.get("/api/drugs/search")
async def search_drugs(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    """Search drug database with OpenFDA fallback"""
    # Check cache first
    cached = db.query(DrugCache).filter(
        DrugCache.drug_name.ilike(f"%{q}%"),
        DrugCache.cached_at > datetime.utcnow() - timedelta(hours=24)
    ).first()
    
    if cached:
        return {"source": "cache", "data": json.loads(cached.data)}
    
    # Fetch from FDA
    fda_data = await fetch_drug_from_fda(q)
    if fda_data:
        # Cache it
        cache_entry = DrugCache(drug_name=q, data=json.dumps(fda_data))
        db.add(cache_entry)
        db.commit()
        return {"source": "fda", "data": fda_data}
    
    return {"source": "none", "message": "Drug not found in FDA database"}

@app.post("/api/drugs/interactions")
async def check_interactions(drugs: list[str]):
    """Check drug interactions using OpenFDA"""
    if len(drugs) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 drugs to check interactions")
    
    interactions = []
    async with aiohttp.ClientSession() as session:
        for drug in drugs:
            url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug}&limit=1"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("results"):
                            result = data["results"][0]
                            if result.get("drug_interactions"):
                                interactions.append({
                                    "drug": drug,
                                    "interactions": result["drug_interactions"][:5]
                                })
            except:
                pass
    
    return {"drugs_checked": len(drugs), "interactions_found": interactions}

# ===================== SYMPTOM CHECKER =====================
@app.get("/api/symptoms/check")
async def check_symptoms(symptoms: str = Query(...)):
    """Advanced symptom checker with triage levels"""
    symptom_list = [s.strip().lower() for s in symptoms.split(",")]
    results = []
    
    for symptom in symptom_list:
        for key, data in SYMPTOM_TRIAGE.items():
            if symptom in key or key in symptom:
                results.append({
                    "symptom": symptom,
                    "possible_conditions": data["conditions"],
                    "triage_level": data["triage"],
                    "action": get_triage_action(data["triage"])
                })
    
    # Determine highest urgency
    triage_order = {"emergency": 3, "doctor": 2, "first_aid": 1}
    highest_triage = max(results, key=lambda x: triage_order.get(x["triage_level"], 0)) if results else None
    
    return {
        "symptoms": symptom_list,
        "results": results,
        "recommended_action": highest_triage["triage_level"] if highest_triage else "unknown",
        "disclaimer": "This is not a diagnosis. Consult a healthcare professional."
    }

def get_triage_action(level):
    actions = {
        "first_aid": "Apply basic first aid. Monitor symptoms. Seek medical help if condition worsens.",
        "doctor": "Schedule an appointment with a healthcare provider within 24-48 hours.",
        "emergency": "SEEK EMERGENCY MEDICAL ATTENTION IMMEDIATELY. Call emergency services or go to the nearest hospital."
    }
    return actions.get(level, "Monitor and seek medical advice if needed.")

# ===================== EMERGENCY PROTOCOLS =====================
@app.get("/api/emergency-protocols")
async def get_protocols(db: Session = Depends(get_db)):
    protocols = db.query(EmergencyProtocol).order_by(EmergencyProtocol.id).all()
    return {"count": len(protocols), "data": protocols}

@app.post("/api/emergency-protocols", status_code=201)
async def create_protocol(p: dict, db: Session = Depends(get_db)):
    protocol = EmergencyProtocol(
        title=p["title"],
        icon=p.get("icon", "🏥"),
        duration_minutes=p.get("duration", 0),
        steps=p.get("steps", []),
        audio_enabled=p.get("audio_enabled", True)
    )
    db.add(protocol)
    db.commit()
    db.refresh(protocol)
    return {"message": "Protocol created", "data": protocol}

# ===================== DISEASE ENCYCLOPEDIA =====================
@app.get("/api/encyclopedia")
async def get_encyclopedia(letter: str = Query(None), q: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(Guideline)
    if letter:
        query = query.filter(Guideline.title.ilike(f"{letter}%"))
    if q:
        query = query.filter(Guideline.title.ilike(f"%{q}%"))
    results = query.order_by(Guideline.title).all()
    return {"count": len(results), "data": results}

# ===================== USER PROFILES =====================
@app.post("/api/users", status_code=201)
async def create_user(u: dict, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == u["username"]).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    user = User(
        username=u["username"],
        email=u.get("email"),
        user_type=u.get("user_type", "patient"),
        profile_data=u.get("profile_data", {})
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created", "data": user}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": user}

# ===================== EXPORT =====================
@app.get("/api/export")
async def export_data(db: Session = Depends(get_db)):
    guidelines = db.query(Guideline).all()
    for g in guidelines:
        g.medicines = json.loads(g.medicines) if isinstance(g.medicines, str) else (g.medicines or [])
        g.steps = json.loads(g.steps) if isinstance(g.steps, str) else (g.steps or [])
    return {"guidelines": guidelines, "exported_at": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
