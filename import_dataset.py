import json
import urllib.request
import os

url = "https://raw.githubusercontent.com/saali96/medicalChatbot/master/data.json"
db_path = "guidelines.json"

blacklist = [
    "greeting", "morning", "afternoon", "evening", "night", "goodbye", "thanks", 
    "no-response", "neutral-response", "about", "skill", "creation", "name", "help",
    "sad", "happy", "casual", "not-talking", "scared", "death", "understand", "done", 
    "hate-you", "hate-me", "default", "jokes", "repeat", "wrong", "stupid", "location", 
    "something-else", "friends", "ask", "problem", "no-approach", "learn-more", 
    "user-agree", "meditation", "user-meditation", "pandora-useful", "user-advice", 
    "learn-mental-health", "mental-health-fact", "suicide"
]

print("Downloading dataset...")
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    raw_data = json.loads(response.read())

print("Loading local database...")
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
else:
    db = []

start_id = max([g.get("id", 0) for g in db], default=0) + 1

added_count = 0
for intent in raw_data.get("intents", []):
    tag = intent.get("tag", "").strip()
    if tag in blacklist:
        continue
    
    # Filter empty responses
    if not intent.get("responses") or intent["responses"][0].strip() == "":
        continue
        
    title_val = tag
    summary_val = intent["responses"][0]
    category_val = "First Aid"
    
    if tag.startswith("fact-"):
        title_val = f"Fact {tag.split('-')[1]}: Mental Health Insight"
        category_val = "Mental Health"
    else:
        title_val = title_val.title()
        
    # Check for duplicates based on title
    if any(g.get("title", "").lower() == title_val.lower() for g in db):
        continue
        
    new_entry = {
        "id": start_id,
        "title": title_val,
        "summary": summary_val,
        "category": category_val
    }
    
    db.append(new_entry)
    start_id += 1
    added_count += 1

with open(db_path, "w", encoding="utf-8") as f:
    json.dump(db, f, indent=4)

print(f"Success! Imported {added_count} new medical guidelines.")
