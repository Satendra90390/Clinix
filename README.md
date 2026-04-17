# MedGuides API

A comprehensive web application for browsing, managing, and searching educational health and medical first-aid guidelines.

## Features

### User Interface
- **Beautiful Dark Theme UI** - Modern glassmorphism design with gradient accents
- **Dynamic Statistics Dashboard** - Real-time counts of guidelines, categories, and medicines
- **Category Filtering** - Filter guidelines by category (First Aid, Emergency, Mental Health, Nutrition, Lifestyle, Chronic Conditions)
- **Search Functionality** - Debounced search across titles, summaries, categories, and medicines
- **Detail Modal** - View full guideline information with severity badges and medicine recommendations
- **Add New Guidelines** - Floating Action Button (FAB) to add new guidelines via form modal
- **Delete Guidelines** - Remove guidelines with confirmation dialog
- **Nearby Medical Facilities** - Location-based map showing hospitals, pharmacies, and clinics using OpenStreetMap
- **Keyboard Shortcuts** - Press `/` to focus search, `Escape` to close modals
- **Emergency Alerts** - Visual warnings for critical/urgent conditions
- **Responsive Design** - Works on desktop, tablet, and mobile devices

### Backend API
- **GET /** - Main web interface
- **GET /health** - Health check endpoint
- **GET /guidelines** - List all guidelines (optional category filter)
- **GET /guidelines/{id}** - Get single guideline by ID
- **GET /search?q=** - Search guidelines by keyword
- **POST /guidelines** - Create new guideline (with validation)
- **DELETE /guidelines/{id}** - Delete guideline by ID

### Data Enrichment
- **68 Guidelines** covering:
  - First Aid (cuts, sprains, fractures, CPR, choking, etc.)
  - Mental Health facts and resources
  - Nutrition and lifestyle recommendations
- **Medicine Recommendations** - 30+ conditions mapped to recommended treatments
- **Severity Classifications** - mild, moderate, urgent, critical

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Import additional guidelines from external dataset:
```bash
python import_dataset.py
```

3. (Optional) Enrich existing data with medicines and severity:
```bash
python enrich_data.py
```

## Running the Application

Start the FastAPI server:
```bash
python main.py
```

The application will be available at: **http://127.0.0.1:8000**

## API Documentation

FastAPI provides automatic Swagger UI documentation at: **http://127.0.0.1:8000/docs**

## Project Structure

```
civic/
├── main.py              # FastAPI application with all endpoints
├── enrich_data.py       # Script to add medicines and severity to guidelines
├── import_dataset.py    # Script to import guidelines from external dataset
├── guidelines.json      # JSON database of medical guidelines
├── requirements.txt     # Python dependencies
├── static/
│   ├── style.css        # Dark theme CSS with glassmorphism effects
│   └── app.js           # Frontend JavaScript for all interactive features
└── templates/
    └── index.html       # Main HTML template with Jinja2 rendering
```

## Technologies Used

- **Backend**: FastAPI, Uvicorn, Pydantic
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Templating**: Jinja2
- **Data**: JSON file-based storage
- **Maps**: OpenStreetMap integration

## Data Validation

All POST requests are validated with Pydantic models:
- Title: 2-100 characters
- Summary: 5-1000 characters
- Category: Must be one of the predefined categories
- Duplicate title prevention

## Disclaimer

**For educational purposes only. Not medical advice. Consult a licensed healthcare provider.**

## License

Educational project - 2026
