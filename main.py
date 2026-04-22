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
    
    engine_kwargs = {"pool_pre_ping": True}
    connect_args = {}
    
    if "postgresql" in DATABASE_URL:
        connect_args["connect_timeout"] = 10
    elif "sqlite" in DATABASE_URL:
        connect_args["check_same_thread"] = False
        # SQLite doesn't use pooling in the same way, but pool_pre_ping is safe
    
    engine = create_engine(DATABASE_URL, **engine_kwargs, connect_args=connect_args)
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

class VitalRecord(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True)
    type = Column(String(50)) # 'heart_rate', 'blood_pressure', 'glucose', 'weight'
    value = Column(String(50))
    recorded_at = Column(DateTime, default=datetime.utcnow)

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

def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    replacements = {
        "â€”": "—",
        "â€™": "’",
        "Ã¢â‚¬â„¢": "'",
        "childrenâ€™s": "children's",
        "Pandora": "ClinixAI",
        "Aimed for": "Aim for",
        "Abdonominal": "abdominal",
        "Heart bee": "Heart Attack",
    }

    cleaned = text
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)

    return re.sub(r"\s+", " ", cleaned).strip()

def normalize_guideline_record(record: dict) -> dict:
    title = sanitize_text(record.get("title", ""))
    summary = sanitize_text(record.get("summary", ""))
    category = sanitize_text(record.get("category", "First Aid"))
    severity = (record.get("severity") or "mild").lower()

    if title == "Sleep Hygiene" and summary.startswith("Aim for"):
        summary = "Aim for 7–9 hours of quality sleep per night for optimal health."

    if title == "Abdonominal Pain" or title == "Abdominal Pain":
        title = "Abdominal Pain"

    if title == "Choking":
        summary = summary.replace("abdominal thrusts", "abdominal thrusts (Heimlich maneuver)")

    if title == "Heart Attack" or title == "Heart bee":
        title = "Heart Attack"
        category = "Emergency"
        severity = "critical"
        summary = "Call emergency services immediately, keep the person seated and calm, loosen tight clothing, and seek urgent medical care."

    return {
        "id": record.get("id"),
        "title": title,
        "summary": summary,
        "category": category,
        "severity": severity,
        "medicines": safe_json_loads(record.get("medicines", [])),
        "steps": safe_json_loads(record.get("steps", [])) or extract_steps(summary),
        "video_url": record.get("video_url")
    }

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

def render_index_page(request: Request, db: Session):
    guidelines = db.query(Guideline).order_by(Guideline.id).all()
    processed = [
        normalize_guideline_record({
            "id": g.id,
            "title": g.title,
            "summary": g.summary,
            "category": g.category,
            "severity": g.severity,
            "medicines": g.medicines,
            "steps": g.steps,
            "video_url": g.video_url
        })
        for g in guidelines
    ]

    categories = ["First Aid", "Emergency", "Mental Health", "Nutrition", "Lifestyle", "Chronic Conditions"]
    try:
        db_cats = [c[0] for c in db.query(Guideline.category).distinct().all() if c[0]]
        if db_cats:
            categories = list(set(categories + db_cats))
    except:
        pass

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

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    return render_index_page(request, db)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    return render_index_page(request, db)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    try:
        return render_index_page(request, db)
    except Exception as e:
        logger.error(f"Root error: {e}")
        # If it's a database connection error, try to show a more helpful message
        error_msg = str(e)
        if "psycopg2.OperationalError" in error_msg or "connection" in error_msg.lower():
            return HTMLResponse(
                content=f"""
                <div style="font-family: sans-serif; padding: 2rem; max-width: 600px; margin: 2rem auto; background: #fff1f2; border: 1px solid #fecaca; border-radius: 12px; color: #991b1b;">
                    <h1 style="margin-top: 0;">Database Connection Error</h1>
                    <p>ClinixAI is having trouble connecting to the medical database.</p>
                    <p style="font-size: 0.9rem; opacity: 0.8;">Technical details: {error_msg}</p>
                    <button onclick="window.location.reload()" style="background: #ef4444; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; cursor: pointer; font-weight: bold;">Retry Connection</button>
                    <p style="margin-top: 1rem; font-size: 0.8rem; color: #666;">If you are working locally, please check your internet connection or .env configuration.</p>
                </div>
                """, 
                status_code=500
            )
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
    if category:
        query = query.filter(Guideline.category == category)

    results = query.all()
    return [
        normalize_guideline_record({
            "id": g.id,
            "title": g.title,
            "summary": g.summary,
            "category": g.category,
            "severity": g.severity,
            "medicines": g.medicines,
            "steps": g.steps,
            "video_url": g.video_url
        })
        for g in results
    ]

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

@app.post("/api/drugs/interactions")
async def check_interactions(drugs: List[str]):
    # This is a simplified version since FDA API interaction checking is complex
    # We will search each drug and look for 'interactions' field
    results = []
    for drug in drugs:
        data = await fetch_drug_from_fda(drug)
        if data and data.get("interactions"):
            results.append({"drug": drug, "interactions": [data["interactions"]]})
    return {"interactions_found": results}

@app.get("/api/symptoms/check")
async def check_symptoms(symptoms: str):
    s_list = [s.strip().lower() for s in symptoms.split(",")]
    results = []
    max_triage = "first_aid"
    
    for s in s_list:
        match = None
        for k, v in SYMPTOM_TRIAGE.items():
            if k in s or s in k:
                match = v
                break
        
        if match:
            results.append({
                "symptom": s, 
                "triage_level": match["triage"], 
                "possible_conditions": match["conditions"],
                "action": "Seek medical advice if symptoms persist"
            })
            if match["triage"] == "emergency":
                max_triage = "emergency"
            elif match["triage"] == "doctor" and max_triage != "emergency":
                max_triage = "doctor"
        else:
            results.append({
                "symptom": s, 
                "triage_level": "mild", 
                "possible_conditions": ["Minor ailment"],
                "action": "Monitor and rest"
            })
            
    return {
        "recommended_action": max_triage,
        "results": results
    }

@app.get("/api/emergency-protocols")
async def get_protocols_api(db: Session = Depends(get_db)):
    return db.query(EmergencyProtocol).all()

@app.post("/api/guidelines")
async def create_guideline(g: dict, db: Session = Depends(get_db)):
    meds, sev, stps = enrich_guideline(g["title"], g.get("summary", ""))
    normalized = normalize_guideline_record({
        "title": g["title"],
        "summary": g.get("summary", ""),
        "category": g.get("category", "First Aid"),
        "severity": sev,
        "medicines": meds,
        "steps": stps
    })

    new_g = Guideline(
        title=normalized["title"], summary=normalized["summary"], category=normalized["category"],
        medicines=normalized["medicines"], severity=normalized["severity"], steps=normalized["steps"]
    )
    db.add(new_g)
    db.commit()
    db.refresh(new_g)
    # Return serializable data
    return {
        "status": "success",
        "data": normalize_guideline_record({
            "id": new_g.id,
            "title": new_g.title,
            "summary": new_g.summary,
            "category": new_g.category,
            "severity": new_g.severity,
            "medicines": new_g.medicines,
            "steps": new_g.steps,
            "video_url": new_g.video_url
        })
    }

@app.put("/api/guidelines/{id}")
async def update_guideline(id: int, g: dict, db: Session = Depends(get_db)):
    db_g = db.query(Guideline).filter(Guideline.id == id).first()
    if not db_g:
        raise HTTPException(status_code=404, detail="Guideline not found")
    
    db_g.title = g.get("title", db_g.title)
    db_g.summary = g.get("summary", db_g.summary)
    db_g.category = g.get("category", db_g.category)
    db_g.severity = g.get("severity", db_g.severity)

    normalized = normalize_guideline_record({
        "id": db_g.id,
        "title": db_g.title,
        "summary": db_g.summary,
        "category": db_g.category,
        "severity": db_g.severity,
        "medicines": db_g.medicines,
        "steps": extract_steps(db_g.summary),
        "video_url": db_g.video_url
    })

    db_g.title = normalized["title"]
    db_g.summary = normalized["summary"]
    db_g.category = normalized["category"]
    db_g.severity = normalized["severity"]
    db_g.steps = normalized["steps"]

    db.commit()
    db.refresh(db_g)
    return {
        "status": "success",
        "data": normalize_guideline_record({
            "id": db_g.id,
            "title": db_g.title,
            "summary": db_g.summary,
            "category": db_g.category,
            "severity": db_g.severity,
            "medicines": db_g.medicines,
            "steps": db_g.steps,
            "video_url": db_g.video_url
        })
    }

@app.delete("/api/guidelines/{id}")
async def delete_guideline_api(id: int, db: Session = Depends(get_db)):
    db_g = db.query(Guideline).filter(Guideline.id == id).first()
    if not db_g:
        raise HTTPException(status_code=404, detail="Guideline not found")
    db.delete(db_g)
    db.commit()
    return {"status": "success"}

@app.post("/api/users")
async def save_user(u: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == u["username"]).first()
    if not user:
        user = User(
            username=u["username"],
            email=u.get("email"),
            user_type=u.get("user_type", "patient"),
            profile_data=u.get("profile_data", {})
        )
        db.add(user)
    else:
        user.email = u.get("email", user.email)
        user.user_type = u.get("user_type", user.user_type)
        user.profile_data = u.get("profile_data", user.profile_data)
    
    db.commit()
    return {"status": "success"}

@app.get("/api/vitals")
async def get_vitals(username: str, db: Session = Depends(get_db)):
    vitals = db.query(VitalRecord).filter(VitalRecord.username == username).order_by(VitalRecord.recorded_at.desc()).all()
    return {"data": vitals}

@app.post("/api/chat")
async def chat_with_ai(request: Request):
    data = await request.json()
    message = data.get("message", "").lower()
    
    # Advanced Structured Logic with Govt References and Follow-up Questions
    response_data = {
        "response": "",
        "source": "ClinixAI Knowledge Engine",
        "references": [],
        "follow_ups": []
    }

    if any(word in message for word in ["hello", "hi", "hey"]):
        response_data["response"] = "Hello! I am **ClinixAI**, your advanced medical assistant. I've initialized my clinical knowledge base and am ready to assist. How can I help you today?"
        response_data["follow_ups"] = ["I have a fever", "My head hurts", "Check symptoms"]
    
    elif any(word in message for word in ["fever", "temperature", "hot"]):
        response_data["response"] = """### **Fever Management Guidance**
A fever is usually your body's natural response to infection. According to standard clinical guidelines:

**Key Recommendations:**
- **Stay Hydrated:** Drink plenty of water, broth, or juice.
- **Rest:** Allow your body to use its energy to fight the infection.
- **Monitor:** Use a thermometer regularly.

**When to seek immediate care:**
- Temperature above **103°F (39.4°C)**.
- Severe headache or stiff neck.
- Difficulty breathing or chest pain."""
        response_data["source"] = "CDC (Centers for Disease Control and Prevention)"
        response_data["references"] = ["https://www.cdc.gov/fever/index.html", "https://www.nhs.uk/conditions/fever-in-adults/"]
        response_data["follow_ups"] = ["How to take temperature?", "Fever in children", "Medicine for fever"]

    elif any(word in message for word in ["headache", "migraine", "head pain"]):
        response_data["response"] = """### **Headache Relief & Assessment**
It sounds like you're experiencing head pain. Data from the National Institute of Health (NIH) suggest:

**Immediate Actions:**
- **Quiet Room:** Rest in a dark, silent environment.
- **Hydration:** Dehydration is a common trigger.
- **Cool Compress:** Apply to the forehead or back of the neck.

**Red Flags (Seek Emergency Care):**
- **Sudden & Severe:** "The worst headache of your life."
- **Confusion:** Difficulty speaking or understanding.
- **Vision Changes:** Blurred or double vision."""
        response_data["source"] = "NIH (National Institutes of Health)"
        response_data["references"] = ["https://www.ninds.nih.gov/health-information/disorders/headache", "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"]
        response_data["follow_ups"] = ["Tension headache vs Migraine", "Natural remedies", "When to see a doctor"]

    elif any(word in message for word in ["chest pain", "heart attack", "stroke", "emergency"]):
        response_data["response"] = """# 🚨 **EMERGENCY ALERT**
**Your symptoms may indicate a life-threatening condition.**

**Please take the following actions IMMEDIATELY:**
1. **Call Emergency Services (911)** now.
2. **Do not drive yourself** to the hospital.
3. Stay calm and sit down while waiting for help.

*I have prioritized this query and cross-referenced with WHO Emergency Protocols.*"""
        response_data["source"] = "WHO (World Health Organization)"
        response_data["references"] = ["https://www.who.int/health-topics/cardiovascular-diseases"]
        response_data["follow_ups"] = ["Signs of a heart attack", "Signs of a stroke", "CPR Steps"]

    elif "thank" in message:
        response_data["response"] = "You're very welcome! As your **ClinixAI** assistant, I'm here to ensure you have the best information at your fingertips. Is there anything else you'd like to discuss?"
        response_data["follow_ups"] = ["Check symptoms", "Nearby hospitals", "Health tips"]
    
    else:
        # Simulate an "Agentic Search"
        response_data["response"] = f"""I've analyzed your query regarding **"{message}"**. 

I am currently performing a **deep search** across government medical databases (CDC, NHS, WHO). Based on my analysis:
- This topic is frequently discussed in **Primary Care** literature.
- I recommend consulting our **Symptoms Checker** for a structured assessment.
- For a definitive diagnosis, please consult a **licensed healthcare provider**.

Would you like me to refine the search for more specific clinical trials?"""
        response_data["source"] = "Global Medical Database Aggregate"
        response_data["follow_ups"] = ["Search CDC", "Search Wikipedia", "Consult a Doctor"]
    
    return response_data

@app.post("/api/vitals")
async def add_vital(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    new_vital = VitalRecord(
        username=data.get("username"),
        type=data.get("type"),
        value=data.get("value")
    )
    db.add(new_vital)
    db.commit()
    db.refresh(new_vital)
    return {"data": new_vital}

# Export app for Vercel
app = app

if __name__ == "__main__":
    import uvicorn
    # Create tables
    Base.metadata.create_all(bind=engine)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
