import json

db_path = "guidelines.json"

# Medicine suggestions per condition
medicines_map = {
    "Cuts": ["Acetaminophen (Tylenol)", "Petroleum Jelly", "Antiseptic Cream"],
    "Abrasions": ["Bacitracin Ointment", "Aquaphor", "Antibiotic Ointment"],
    "Stings": ["Diphenhydramine (Benadryl)", "Loratadine (Claritin)", "Hydrocortisone Cream", "Acetaminophen (Tylenol)"],
    "Splinter": ["Epsom Salts", "Antiseptic Ointment"],
    "Sprains": ["Ibuprofen (Advil)", "Naproxen Sodium (Aleve)", "Acetaminophen (Tylenol)"],
    "Strains": ["Ibuprofen (Advil)", "Acetaminophen (Tylenol)", "Ice Pack"],
    "Fever": ["Acetaminophen (Tylenol)", "Ibuprofen (Advil, Motrin IB)"],
    "Nasal Congestion": ["Saline Nasal Spray", "Decongestant (Sudafed)", "Humidifier"],
    "Cough": ["Honey", "Dextromethorphan (Robitussin)", "Guaifenesin (Mucinex)"],
    "Sore Throat": ["Strepsils Lozenges", "Ibuprofen", "Honey & Lemon"],
    "Gastrointestinal Problems": ["Antacids (Tums)", "Omeprazole (Prilosec)", "Simethicone (Gas-X)"],
    "Skin Problems": ["Hydrocortisone Cream", "Calamine Lotion", "Antihistamine"],
    "Abdonominal Pain": ["Simethicone (Gas-X)", "Antacids (Tums)", "Oral Rehydration Salts"],
    "Bruises": ["Arnica Gel", "Ibuprofen (Advil)", "Ice Pack"],
    "Broken Toe": ["Ibuprofen (Advil)", "Acetaminophen (Tylenol)", "Ice Pack"],
    "Choking": [],
    "Wound": ["Antiseptic Solution", "Sterile Bandage", "Antibiotic Ointment"],
    "Diarrhea": ["Oral Rehydration Salts (ORS)", "Loperamide (Imodium)", "Probiotics"],
    "Headache": ["Ibuprofen (Advil, Motrin)", "Aspirin", "Acetaminophen (Tylenol)"],
    "Cold": ["Vitamin C Supplements", "Zinc Lozenges", "Decongestant (Sudafed)"],
    "Rash": ["Hydrocortisone Cream", "Calamine Lotion", "Antihistamine (Benadryl)"],
    "Snake Bite": [],
    "Animal Bite": ["Antibacterial Ointment", "Antiseptic Solution", "Rabies Vaccine (seek doctor)"],
    "Drowning": [],
    "Cpr": [],
    "Fracture": ["Ibuprofen (Advil)", "Acetaminophen (Tylenol)", "Calcium Supplements"],
    "Basic First Aid Rest": ["Rest", "Ice Pack", "Compression Bandage"],
    "Cpr Compression Depth": [],
    "Healthy Diet Basics": ["Multivitamins", "Omega-3 Fish Oil", "Vitamin D"],
    "Hydration Guidelines": ["Oral Rehydration Salts (ORS)", "Electrolyte Tablets"],
    "Sleep Hygiene": ["Melatonin", "Magnesium Supplements"],
}

severity_map = {
    "Snake Bite": "critical",
    "Drowning": "critical",
    "Cpr": "critical",
    "Fracture": "urgent",
    "Choking": "critical",
    "Broken Toe": "urgent",
    "Animal Bite": "urgent",
    "Wound": "urgent",
    "Fever": "moderate",
    "Headache": "mild",
    "Cold": "mild",
    "Cough": "mild",
    "Rash": "mild",
    "Sprains": "moderate",
    "Strains": "moderate",
    "Bruises": "mild",
    "Cuts": "mild",
    "Abrasions": "mild",
}

with open(db_path, "r", encoding="utf-8") as f:
    db = json.load(f)

updated = 0
for item in db:
    title = item.get("title", "")
    if "medicines" not in item:
        item["medicines"] = medicines_map.get(title, [])
        updated += 1
    if "severity" not in item:
        item["severity"] = severity_map.get(title, "mild")

with open(db_path, "w", encoding="utf-8") as f:
    json.dump(db, f, indent=4)

print(f"Added medicines and severity to {len(db)} guidelines ({updated} newly updated).")
