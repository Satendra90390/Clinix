// STATE
let allGuidelines = [];
let currentCategory = '';
let currentSeverity = '';
let currentView = 'grid';
let userLat = null;
let userLon = null;
let selectedSymptoms = [];
let bookmarks = JSON.parse(localStorage.getItem('medguide_bookmarks') || '[]');
let currentDetailId = null;
let currentUser = JSON.parse(localStorage.getItem('medguide_user') || 'null');
let timerInterval = null;
let timerSeconds = 0;
let timerRunning = false;
let audioGuide = null;
let currentLanguage = localStorage.getItem('medguide_lang') || 'en';

const translations = {
    en: {
        home: "Home", symptoms: "Symptoms", drugs: "Drugs", emergency: "Emergency", wikipedia: "Wikipedia", profile: "Profile",
        guidelines: "Guidelines", categories: "Categories", critical_urgent: "Critical/Urgent", protocols: "Emergency Protocols",
        search_placeholder: "Search conditions, medicines, symptoms...", showing: "Showing", guidelines_count: "guidelines",
        welcome: "Welcome to ClinixAI", guest_btn: "Continue as Guest", login_sub: "Your AI-Powered Medical Companion"
    },
    hi: {
        home: "होम", symptoms: "लक्षण", drugs: "दवाएं", emergency: "आपातकालीन", wikipedia: "विकिपीडिया", profile: "प्रोफ़ाइल",
        guidelines: "दिशानिर्देश", categories: "श्रेणियाँ", critical_urgent: "गंभीर/तत्काल", protocols: "आपातकालीन प्रोटोकॉल",
        search_placeholder: "स्थितियों, दवाओं, लक्षणों की खोज करें...", showing: "दिखा रहा है", guidelines_count: "दिशानिर्देश",
        welcome: "क्लिनिक्स एआई में आपका स्वागत है", guest_btn: "अतिथि के रूप में जारी रखें", login_sub: "आपका एआई-संचालित चिकित्सा साथी"
    },
    es: {
        home: "Inicio", symptoms: "Síntomas", drugs: "Medicamentos", emergency: "Emergencia", wikipedia: "Wikipedia", profile: "Perfil",
        guidelines: "Pautas", categories: "Categorías", critical_urgent: "Crítico/Urgente", protocols: "Protocolos de Emergencia",
        search_placeholder: "Buscar condiciones, medicamentos, síntomas...", showing: "Mostrando", guidelines_count: "pautas",
        welcome: "Bienvenido a ClinixAI", guest_btn: "Continuar como Invitado", login_sub: "Su compañero médico impulsado por IA"
    },
    fr: {
        home: "Accueil", symptoms: "Symptômes", drugs: "Médicaments", emergency: "Urgence", wikipedia: "Wikipédia", profile: "Profil",
        guidelines: "Directives", categories: "Catégories", critical_urgent: "Critique/Urgent", protocols: "Protocoles d'Urgence",
        search_placeholder: "Rechercher des conditions, médicaments, symptômes...", showing: "Affichage de", guidelines_count: "directives",
        welcome: "Bienvenue sur ClinixAI", guest_btn: "Continuer en tant qu'Invité", login_sub: "Votre compagnon médical propulsé par l'IA"
    }
};

// INIT
document.addEventListener('DOMContentLoaded', () => {
    applyLanguage();
    checkLoginStatus();
    loadGuidelinesFromPage();
    setupFilters();
    setupSearch();
    setupSeverityFilters();
    detectLocation();
    buildLetterBar();
    populateEmergencyProtocols();
    loadUserProfile();

    // Register Service Worker (Step 3)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('SW Registered'))
            .catch(err => console.log('SW Registration Failed', err));
    }
});

function changeLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem('medguide_lang', lang);
    applyLanguage();
    // Re-render components that might have translated text
    renderCards();
    populateEmergencyProtocols();
}

function applyLanguage() {
    const t = translations[currentLanguage] || translations.en;
    
    // Update Nav Tabs
    const navMapping = {
        home: t.home, symptoms: t.symptoms, drugs: t.drugs,
        emergency: t.emergency, encyclopedia: t.wikipedia, profile: t.profile
    };
    
    Object.entries(navMapping).forEach(([page, label]) => {
        const tabs = document.querySelectorAll(`.nav-link[data-page="${page}"], .b-nav-item[data-page="${page}"]`);
        tabs.forEach(tab => {
            const iconEl = tab.querySelector('.nav-icon, .b-nav-icon, .b-nav-fab');
            if (iconEl) {
                const icon = iconEl.textContent;
                const labelEl = tab.querySelector('.b-nav-label');
                if (labelEl) {
                    labelEl.textContent = label;
                } else if (!tab.querySelector('.b-nav-fab')) {
                    tab.innerHTML = `<span class="nav-icon">${icon}</span> ${label}`;
                }
            }
        });
    });

    // Update Hero Stats labels
    const statsMapping = {
        'totalCount': t.guidelines,
        'categoryCount': t.categories,
        'criticalCount': t.critical_urgent,
        'protocolCount': t.protocols
    };
    
    Object.entries(statsMapping).forEach(([id, label]) => {
        const el = document.getElementById(id);
        if (el && el.nextElementSibling) el.nextElementSibling.textContent = label;
    });

    // Update Search Placeholder
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.placeholder = t.search_placeholder;

    // Update Showing text
    const showingText = document.querySelector('.results-count');
    if (showingText) {
        showingText.innerHTML = `${t.showing} <strong id="showingCount">${allGuidelines.length}</strong> ${t.guidelines_count}`;
    }

    // Update Login Modal
    const loginHeader = document.querySelector('.login-header h2');
    if (loginHeader) loginHeader.textContent = t.welcome;
    const loginSub = document.querySelector('.login-header p');
    if (loginSub) loginSub.textContent = t.login_sub;
    const guestBtn = document.querySelector('.btn-guest');
    if (guestBtn) {
        const icon = guestBtn.querySelector('.btn-icon').outerHTML;
        guestBtn.innerHTML = `${icon} ${t.guest_btn}`;
    }

    // Sync language selector
    const langSelect = document.getElementById('languageSelect');
    if (langSelect) langSelect.value = currentLanguage;
}

function loadGuidelinesFromPage() {
    const cards = document.querySelectorAll('#guidelinesGrid .card');
    allGuidelines = Array.from(cards).map(card => ({
        id: parseInt(card.dataset.id),
        title: card.dataset.title,
        summary: card.dataset.summary,
        category: card.dataset.category,
        severity: card.dataset.severity,
        medicines: JSON.parse(card.dataset.medicines.replace(/&quot;/g, '"')),
        steps: JSON.parse(card.dataset.steps.replace(/&quot;/g, '"')) || []
    }));
    updateStats();
    buildCategoryFilters();
    renderCards();
}

function updateStats() {
    document.getElementById('totalCount').textContent = allGuidelines.length;
    const categories = [...new Set(allGuidelines.map(g => g.category))];
    document.getElementById('categoryCount').textContent = categories.length;
    const criticalUrgent = allGuidelines.filter(g => ['critical', 'urgent'].includes(g.severity)).length;
    document.getElementById('criticalCount').textContent = criticalUrgent;
    document.getElementById('showingCount').textContent = allGuidelines.length;
}

function buildCategoryFilters() {
    const categories = [...new Set(allGuidelines.map(g => g.category))].sort();
    const bar = document.getElementById('filtersBar');
    bar.innerHTML = '<button class="filter-pill active" data-category="">All</button>';
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'filter-pill';
        btn.dataset.category = cat;
        btn.textContent = cat;
        btn.onclick = () => {
            document.querySelectorAll('.filter-pill[data-category]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = cat;
            renderCards();
        };
        bar.appendChild(btn);
    });
}

function setupFilters() {
    document.querySelectorAll('.filter-pill[data-category]').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.filter-pill[data-category]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            renderCards();
        };
    });
}

function setupSeverityFilters() {
    document.querySelectorAll('.sev-filter').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.sev-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSeverity = btn.dataset.severity;
            renderCards();
        };
    });
}

function getFilteredGuidelines() {
    let items = allGuidelines;
    if (currentCategory) items = items.filter(g => g.category === currentCategory);
    if (currentSeverity) items = items.filter(g => g.severity === currentSeverity);
    return items;
}

function renderCards(data) {
    const grid = document.getElementById('guidelinesGrid');
    const emptyState = document.getElementById('emptyState');
    const items = data || getFilteredGuidelines();
    grid.innerHTML = '';
    grid.className = currentView === 'grid' ? 'guidelines-grid' : 'guidelines-list';

    if (items.length === 0) {
        emptyState.style.display = 'block';
        document.getElementById('showingCount').textContent = '0';
        return;
    }

    emptyState.style.display = 'none';
    document.getElementById('showingCount').textContent = items.length;

    items.forEach(g => {
        const card = document.createElement('article');
        card.className = 'card';
        const medsPreview = (g.medicines || []).slice(0, 3);
        const extraCount = (g.medicines || []).length - 3;
        const stepsPreview = (g.steps || []).slice(0, 2);

        card.innerHTML = `
            <div class="card-top">
                <div class="card-badges">
                    <span class="badge-category">${g.category}</span>
                    <span class="badge-severity sev-${g.severity}">${g.severity.toUpperCase()}</span>
                </div>
                <div class="card-actions">
                    <button class="icon-btn bookmarked-${bookmarks.includes(g.id)}" onclick="event.stopPropagation(); bookmarkItem(${g.id})" title="Bookmark">&#9734;</button>
                    <button class="icon-btn" onclick="event.stopPropagation(); openEditModal(${g.id})" title="Edit">&#9998;</button>
                    <button class="icon-btn delete" onclick="event.stopPropagation(); deleteGuideline(${g.id})" title="Delete">&#10005;</button>
                </div>
            </div>
            <h2 class="card-title">${g.title}</h2>
            <p class="card-summary">${g.summary}</p>
            ${g.steps && g.steps.length > 0 ? `
            <div class="steps-preview">
                ${stepsPreview.map((s, i) => `<div class="step-chip"><span>${i + 1}</span> ${s.substring(0, 50)}${s.length > 50 ? '...' : ''}</div>`).join('')}
                ${g.steps.length > 2 ? `<div class="step-chip">+${g.steps.length - 2} more steps</div>` : ''}
            </div>` : ''}
            <div class="card-footer">
                <div class="medicines-preview">
                    ${medsPreview.map(m => `<span class="med-chip">${m}</span>`).join('')}
                    ${extraCount > 0 ? `<span class="med-chip">+${extraCount} more</span>` : ''}
                </div>
                <span class="view-details-btn">View &#8594;</span>
            </div>
        `;
        card.onclick = () => openDetailModal(g);
        grid.appendChild(card);
    });
}

function setView(view) {
    currentView = view;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.view-btn[onclick="setView('${view}')"]`).classList.add('active');
    renderCards();
}

// SEARCH
function setupSearch() {
    let debounceTimeout;
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimeout);
        const query = e.target.value.trim();
        debounceTimeout = setTimeout(async () => {
            if (query.length >= 2) {
                const res = await fetch(`/api/guidelines?category=${currentCategory}`);
                const data = await res.json();
                allGuidelines = data;
                const filtered = allGuidelines.filter(g =>
                    g.title.toLowerCase().includes(query.toLowerCase()) ||
                    g.summary.toLowerCase().includes(query.toLowerCase()) ||
                    (g.medicines || []).some(m => m.toLowerCase().includes(query.toLowerCase()))
                );
                renderCards(filtered);
            } else if (query.length === 0) {
                renderCards();
            }
        }, 300);
    });

    const encySearch = document.getElementById('encyclopediaSearch');
    if (encySearch) {
        encySearch.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchWikipedia();
        });
    }

    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch && searchInput) {
        globalSearch.addEventListener('input', (e) => {
            searchInput.value = e.target.value;
            searchInput.dispatchEvent(new Event('input'));
        });
    }
}

// NAVIGATION
function navigateTo(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-link, .b-nav-item').forEach(t => t.classList.remove('active'));
    
    const targetPage = document.getElementById(page + 'Page');
    if (targetPage) targetPage.classList.add('active');
    
    const activeTabs = document.querySelectorAll(`.nav-link[data-page="${page}"], .b-nav-item[data-page="${page}"]`);
    activeTabs.forEach(t => t.classList.add('active'));

    if (page === 'encyclopedia') {
        // Initial letter bar if needed
        if (document.getElementById('letterBar').children.length <= 1) buildLetterBar();
    }
    if (page === 'profile') loadUserProfile();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// DETAIL MODAL
function openDetailModal(guideline) {
    currentDetailId = guideline.id;
    const overlay = document.getElementById('detailOverlay');
    document.getElementById('modalTitle').textContent = guideline.title;
    document.getElementById('modalSummary').textContent = guideline.summary;
    document.getElementById('modalCategory').textContent = guideline.category;

    const sevBadge = document.getElementById('modalSeverity');
    sevBadge.textContent = guideline.severity.toUpperCase();
    const hero = document.getElementById('modalHero');
    const gradients = {
        critical: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        urgent: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
        moderate: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        mild: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)'
    };
    hero.style.background = gradients[guideline.severity] || gradients.mild;

    // Steps
    const stepsList = document.getElementById('modalSteps');
    if (guideline.steps && guideline.steps.length > 0) {
        stepsList.innerHTML = guideline.steps.map((s, i) => `
            <div class="step-item">
                <div class="step-number">${i + 1}</div>
                <div class="step-text">${s}</div>
            </div>
        `).join('');
    } else {
        stepsList.innerHTML = '<p style="color: var(--text-muted); font-style: italic;">No step-by-step instructions available</p>';
    }

    // Medicines
    const medicinesGrid = document.getElementById('modalMedicines');
    const medicinesSection = document.getElementById('medicinesSection');
    if (guideline.medicines && guideline.medicines.length > 0) {
        medicinesSection.style.display = 'block';
        medicinesGrid.innerHTML = guideline.medicines.map(m => `<span class="medicine-tag">&#128138; ${m}</span>`).join('');
    } else {
        medicinesSection.style.display = 'none';
    }

    // Emergency alert
    document.getElementById('emergencySection').style.display =
        ['critical', 'urgent'].includes(guideline.severity) ? 'block' : 'none';

    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeDetailModal() {
    document.getElementById('detailOverlay').classList.remove('active');
    document.body.style.overflow = '';
    currentDetailId = null;
}

// ADD GUIDELINE
function openAddModal() {
    document.getElementById('addOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeAddModal() {
    document.getElementById('addOverlay').classList.remove('active');
    document.body.style.overflow = '';
    document.getElementById('addForm').reset();
}

async function submitNewGuideline(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';

    const data = {
        title: document.getElementById('addTitle').value,
        summary: document.getElementById('addSummary').value,
        category: document.getElementById('addCategory').value
    };

    try {
        const res = await fetch('/api/guidelines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            const result = await res.json();
            allGuidelines.push(result.data);
            renderCards();
            updateStats();
            closeAddModal();
            alert('Guideline added! Medicines and severity assigned automatically.');
        } else {
            const err = await res.json();
            alert('Failed: ' + (err.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Error adding guideline');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add Guideline';
    }
}

// EDIT GUIDELINE
function openEditModal(id) {
    const guideline = allGuidelines.find(g => g.id === id);
    if (!guideline) return;

    document.getElementById('editId').value = id;
    document.getElementById('editTitle').value = guideline.title;
    document.getElementById('editSummary').value = guideline.summary;
    document.getElementById('editCategory').value = guideline.category;
    document.getElementById('editSeverity').value = guideline.severity;

    document.getElementById('editOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeEditModal() {
    document.getElementById('editOverlay').classList.remove('active');
    document.body.style.overflow = '';
}

async function submitEditGuideline(e) {
    e.preventDefault();
    const submitBtn = document.getElementById('editSubmitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    const id = parseInt(document.getElementById('editId').value);
    const data = {
        title: document.getElementById('editTitle').value,
        summary: document.getElementById('editSummary').value,
        category: document.getElementById('editCategory').value,
        severity: document.getElementById('editSeverity').value
    };

    try {
        const res = await fetch(`/api/guidelines/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            const result = await res.json();
            const idx = allGuidelines.findIndex(g => g.id === id);
            if (idx > -1) allGuidelines[idx] = result.data;
            renderCards();
            updateStats();
            closeEditModal();
            alert('Guideline updated!');
        } else {
            const err = await res.json();
            alert('Failed: ' + (err.detail || 'Unknown error'));
        }
    } catch (err) {
        alert('Error updating guideline');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Changes';
    }
}

// DELETE
async function deleteGuideline(id) {
    if (!confirm('Delete this guideline?')) return;
    try {
        const res = await fetch(`/api/guidelines/${id}`, { method: 'DELETE' });
        if (res.ok) {
            allGuidelines = allGuidelines.filter(g => g.id !== id);
            renderCards();
            updateStats();
        } else {
            alert('Failed to delete');
        }
    } catch (err) {
        alert('Error deleting guideline');
    }
}

// BOOKMARKS
function bookmarkItem(id) {
    const idx = bookmarks.indexOf(id);
    if (idx > -1) bookmarks.splice(idx, 1);
    else bookmarks.push(id);
    localStorage.setItem('medguide_bookmarks', JSON.stringify(bookmarks));
    renderCards();
    updateBookmarksList();
}

function updateBookmarksList() {
    const container = document.getElementById('bookmarksList');
    if (!container) return;
    const bookmarked = allGuidelines.filter(g => bookmarks.includes(g.id));
    if (bookmarked.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No bookmarks yet</p>';
        return;
    }
    container.innerHTML = bookmarked.map(g => `
        <div class="bookmark-item" onclick="openDetailModal(allGuidelines.find(x => x.id === ${g.id}))">
            <span>${g.title}</span>
            <span class="badge-severity sev-${g.severity}" style="font-size: 0.65rem;">${g.severity.toUpperCase()}</span>
        </div>
    `).join('');
}

// SYMPTOM CHECKER
function toggleSymptom(symptom) {
    const idx = selectedSymptoms.indexOf(symptom);
    if (idx > -1) selectedSymptoms.splice(idx, 1);
    else selectedSymptoms.push(symptom);
    updateSymptomTags();
}

function updateSymptomTags() {
    const container = document.getElementById('selectedSymptomTags');
    if (!container) return;
    container.innerHTML = selectedSymptoms.map(s =>
        `<span class="symptom-tag">${s} <button onclick="toggleSymptom('${s}')">&times;</button></span>`
    ).join('');

    document.querySelectorAll('.symptom-btn').forEach(btn => {
        const match = btn.getAttribute('onclick').match(/'([^']+)'/);
        if (match) btn.classList.toggle('selected', selectedSymptoms.includes(match[1]));
    });
}

async function checkSymptoms() {
    if (selectedSymptoms.length === 0) {
        alert('Select at least one symptom');
        return;
    }

    try {
        const res = await fetch(`/api/symptoms/check?symptoms=${encodeURIComponent(selectedSymptoms.join(','))}`);
        if (res.ok) {
            const data = await res.json();
            const triageAlert = document.getElementById('triageAlert');
            const conditionResults = document.getElementById('conditionResults');
            const triagePanel = document.getElementById('triagePanel');

            const colors = {
                emergency: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#ff6b6b', icon: '&#9888;' },
                doctor: { bg: 'rgba(245,158,11,0.15)', border: '#f59e0b', text: '#fbbf24', icon: '&#128137;' },
                first_aid: { bg: 'rgba(16,185,129,0.15)', border: '#10b981', text: '#6ee7b7', icon: '&#129757;' }
            };
            const c = colors[data.recommended_action] || colors.first_aid;

            triageAlert.innerHTML = `
                <div style="background: ${c.bg}; border: 1px solid ${c.border}; border-radius: var(--radius-md); padding: 1rem;">
                    <h3 style="color: ${c.text}; margin: 0 0 0.5rem;">${c.icon} Recommended: ${data.recommended_action.toUpperCase().replace('_', ' ')}</h3>
                    <p style="color: var(--text-primary); margin: 0;">${data.results[0]?.action || 'Seek medical advice'}</p>
                </div>
            `;

            conditionResults.innerHTML = data.results.map(r => `
                <div class="condition-item">
                    <div>
                        <strong>${r.symptom}</strong>
                        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.3rem;">
                            Possible: ${r.possible_conditions.join(', ')}
                        </div>
                    </div>
                    <span class="badge-severity sev-${r.triage_level === 'emergency' ? 'critical' : r.triage_level === 'doctor' ? 'moderate' : 'mild'}">
                        ${r.triage_level.toUpperCase()}
                    </span>
                </div>
            `).join('');

            triagePanel.style.display = 'block';
        }
    } catch (err) {
        alert('Failed to check symptoms');
    }
}

// DRUG DATABASE
async function searchDrug() {
    const query = document.getElementById('drugSearchInput').value.trim();
    if (query.length < 2) { alert('Enter at least 2 characters'); return; }

    const resultsDiv = document.getElementById('drugResults');
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = '<p style="color: var(--text-muted);">Searching FDA database...</p>';

    try {
        const res = await fetch(`/api/drugs/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        if (data.data) {
            const d = data.data;
            resultsDiv.innerHTML = `
                <div class="drug-card">
                    <div class="drug-header">
                        <h3>${query}</h3>
                        <span class="badge-category">Source: ${data.source.toUpperCase()}</span>
                    </div>
                    <div class="drug-details">
                        <div class="drug-detail-item">
                            <strong>Purpose:</strong> <p>${d.purpose}</p>
                        </div>
                        <div class="drug-detail-item">
                            <strong>Dosage:</strong> <p>${d.dosage}</p>
                        </div>
                        <div class="drug-detail-item">
                            <strong>Side Effects:</strong> <p>${d.side_effects}</p>
                        </div>
                        <div class="drug-detail-item">
                            <strong>Storage:</strong> <p>${d.storage}</p>
                        </div>
                    </div>
                </div>
            `;
        } else {
            resultsDiv.innerHTML = '<p style="color: var(--text-muted);">Drug not found in FDA database. Try a different name.</p>';
        }
    } catch (err) {
        resultsDiv.innerHTML = '<p style="color: var(--accent-red);">Error fetching drug data</p>';
    }
}

function addDrugInput() {
    const container = document.getElementById('interactionInputs');
    const count = container.querySelectorAll('.drug-input').length + 1;
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control drug-input';
    input.placeholder = `Drug ${count}`;
    container.appendChild(input);
}

async function checkInteractions() {
    const inputs = document.querySelectorAll('.drug-input');
    const drugs = Array.from(inputs).map(i => i.value.trim()).filter(v => v);

    if (drugs.length < 2) { alert('Enter at least 2 drugs'); return; }

    const resultsDiv = document.getElementById('interactionResults');
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = '<p style="color: var(--text-muted);">Checking interactions...</p>';

    try {
        const res = await fetch('/api/drugs/interactions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(drugs)
        });
        const data = await res.json();

        if (data.interactions_found.length === 0) {
            resultsDiv.innerHTML = '<p style="color: var(--accent-green);">No known interactions found in FDA database for these drugs.</p>';
        } else {
            resultsDiv.innerHTML = data.interactions_found.map(i => `
                <div class="interaction-item">
                    <strong>${i.drug}:</strong>
                    <p>${i.interactions.join('; ')}</p>
                </div>
            `).join('');
        }
    } catch (err) {
        resultsDiv.innerHTML = '<p style="color: var(--accent-red);">Error checking interactions</p>';
    }
}

// EMERGENCY PROTOCOLS
const emergencyProtocols = [
    { id: 1, title: "CPR (Adult)", icon: "&#10084;", duration: 10, steps: ["Call 911 immediately", "Place heel of hand on center of chest", "Push down at least 2 inches", "Compress at 100-120 per minute", "Let chest rise completely between pushes", "Continue until help arrives or person breathes"], audio: true },
    { id: 2, title: "Choking (Adult)", icon: "&#128553;", duration: 5, steps: ["Encourage coughing", "Give 5 back blows between shoulder blades", "Give 5 abdominal thrusts (Heimlich)", "Alternate back blows and thrusts", "Call 911 if person becomes unconscious"], audio: true },
    { id: 3, title: "Severe Bleeding", icon: "&#128308;", duration: 5, steps: ["Apply direct pressure with clean cloth", "Do not remove cloth if soaked, add more layers", "Elevate injured area above heart if possible", "Apply pressure bandage", "Call 911 if bleeding doesn't stop"], audio: true },
    { id: 4, title: "Burns Treatment", icon: "&#128293;", duration: 5, steps: ["Cool burn under cool running water for 10-20 minutes", "Remove jewelry or tight items from burned area", "Do not break blisters", "Cover with sterile, non-stick bandage", "Seek medical help for severe burns"], audio: true },
    { id: 5, title: "Stroke (FAST)", icon: "&#129301;", duration: 3, steps: ["Face: Ask person to smile. Does one side droop?", "Arms: Ask person to raise both arms. Does one drift down?", "Speech: Ask person to repeat a phrase. Is speech slurred?", "Time: If you see any sign, call 911 IMMEDIATELY", "Note the time symptoms started"], audio: true },
    { id: 6, title: "Heart Attack", icon: "&#10084;&#65039;", duration: 3, steps: ["Call 911 immediately", "Have person sit down and stay calm", "Loosen tight clothing", "If conscious and not allergic, give aspirin to chew", "Be prepared to perform CPR if person becomes unconscious"], audio: true },
];

function populateEmergencyProtocols() {
    const container = document.getElementById('emergencyProtocols');
    if (!container) return;

    container.innerHTML = emergencyProtocols.map(p => `
        <div class="protocol-card" onclick="openProtocolTimer(${p.id})">
            <div class="protocol-icon">${p.icon}</div>
            <div class="protocol-info">
                <h3>${p.title}</h3>
                <p>${p.steps.length} steps &#8226; ~${p.duration} min</p>
            </div>
            <div class="protocol-arrow">&#8594;</div>
        </div>
    `).join('');

    if (document.getElementById('protocolCount')) {
        document.getElementById('protocolCount').textContent = emergencyProtocols.length;
    }
}

function openProtocolTimer(id) {
    const protocol = emergencyProtocols.find(p => p.id === id);
    if (!protocol) return;

    document.getElementById('protocolTimerTitle').textContent = protocol.title;
    document.getElementById('protocolSteps').innerHTML = protocol.steps.map((s, i) => `
        <div class="protocol-step">
            <div class="protocol-step-num">${i + 1}</div>
            <div class="protocol-step-text">${s}</div>
        </div>
    `).join('');

    resetTimer();
    document.getElementById('protocolTimerOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeProtocolTimer() {
    document.getElementById('protocolTimerOverlay').classList.remove('active');
    document.body.style.overflow = '';
    pauseTimer();
    if (audioGuide) {
        audioGuide.cancel();
        audioGuide = null;
    }
}

function startTimer() {
    if (timerRunning) return;
    timerRunning = true;
    timerInterval = setInterval(() => {
        timerSeconds++;
        updateTimerDisplay();
    }, 1000);
}

function pauseTimer() {
    timerRunning = false;
    clearInterval(timerInterval);
}

function resetTimer() {
    pauseTimer();
    timerSeconds = 0;
    updateTimerDisplay();
}

function updateTimerDisplay() {
    const mins = Math.floor(timerSeconds / 60).toString().padStart(2, '0');
    const secs = (timerSeconds % 60).toString().padStart(2, '0');
    document.getElementById('timerDisplay').textContent = `${mins}:${secs}`;
}

function toggleAudio() {
    if (!('speechSynthesis' in window)) {
        alert('Audio not supported in this browser');
        return;
    }

    if (audioGuide && audioGuide.speaking) {
        window.speechSynthesis.cancel();
        audioGuide = null;
        document.getElementById('audioIcon').textContent = '&#128264;';
        return;
    }

    const steps = document.querySelectorAll('#protocolSteps .protocol-step-text');
    const text = Array.from(steps).map((s, i) => `Step ${i + 1}: ${s.textContent}`).join('. ');

    audioGuide = new SpeechSynthesisUtterance(text);
    audioGuide.rate = 0.9;
    audioGuide.pitch = 1;
    audioGuide.onend = () => {
        audioGuide = null;
        document.getElementById('audioIcon').textContent = '&#128264;';
    };

    window.speechSynthesis.speak(audioGuide);
    document.getElementById('audioIcon').textContent = '&#128263;';
}

function callEmergency() {
    if (confirm('Call Emergency Services (911)?')) {
        window.location.href = 'tel:911';
    }
}

// WIKIPEDIA SEARCH (Replaced Encyclopedia)
async function searchWikipedia() {
    const query = document.getElementById('encyclopediaSearch').value.trim();
    if (!query) return;

    const list = document.getElementById('encyclopediaList');
    list.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon" style="animation: spin 2s linear infinite;">&#127760;</div>
            <h3>Searching Wikipedia...</h3>
            <p>Fetching the latest medical information for "${query}"</p>
        </div>
    `;

    try {
        const response = await fetch(`https://en.wikipedia.org/w/api.php?action=query&format=json&prop=extracts|pageimages&exintro&explaintext&generator=search&gsrsearch=${encodeURIComponent(query)}&gsrlimit=10&origin=*`);
        const data = await response.json();

        if (data.query && data.query.pages) {
            const pages = Object.values(data.query.pages).sort((a, b) => a.index - b.index);
            list.innerHTML = pages.map(page => `
                <div class="encyclopedia-item" onclick="window.open('https://en.wikipedia.org/?curid=${page.pageid}', '_blank')">
                    <h4>${page.title}</h4>
                    <p>${page.extract ? page.extract.substring(0, 350) + (page.extract.length > 350 ? '...' : '') : 'No detailed description available.'}</p>
                    <div class="encyclopedia-badges">
                        <span class="badge-category">Wikipedia Article</span>
                        <span class="badge-severity sev-mild">MEDICAL INFO</span>
                        <span style="margin-left: auto; color: var(--accent-blue); font-size: 0.8rem;">Read More &rarr;</span>
                    </div>
                </div>
            `).join('');
        } else {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">&#9888;</div>
                    <h3>No Results Found</h3>
                    <p>Wikipedia doesn't seem to have a direct match for "${query}". Try a more general term.</p>
                </div>
            `;
        }
    } catch (error) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">&#10060;</div>
                <h3>Search Failed</h3>
                <p>Could not connect to Wikipedia. Please check your internet connection.</p>
            </div>
        `;
    }
}

function buildLetterBar() {
    const bar = document.getElementById('letterBar');
    if (!bar) return;
    bar.innerHTML = '';

    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    letters.forEach(letter => {
        const btn = document.createElement('button');
        btn.className = 'letter-btn';
        btn.textContent = letter;
        btn.onclick = () => {
            document.querySelectorAll('.letter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('encyclopediaSearch').value = letter;
            searchWikipedia();
        };
        bar.appendChild(btn);
    });
}

// PROFILE
function loadUserProfile() {
    if (!currentUser) return;

    document.getElementById('profileUsername').value = currentUser.username || '';
    document.getElementById('profileEmail').value = currentUser.email || '';
    document.getElementById('profileType').value = currentUser.user_type || 'patient';
    document.getElementById('bloodType').value = currentUser.profile_data?.blood_type || '';
    document.getElementById('medicalNotes').value = currentUser.profile_data?.allergies || '';
    updateBookmarksList();
}

async function saveProfile(e) {
    e.preventDefault();

    currentUser = {
        username: document.getElementById('profileUsername').value,
        email: document.getElementById('profileEmail').value,
        user_type: document.getElementById('profileType').value,
        profile_data: {
            blood_type: document.getElementById('bloodType').value,
            allergies: document.getElementById('medicalNotes').value
        }
    };

    localStorage.setItem('medguide_user', JSON.stringify(currentUser));

    try {
        await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUser)
        });
        alert('Profile saved!');
    } catch (err) {
        alert('Saved locally (server not connected)');
    }
}

// LOGIN SYSTEM
function checkLoginStatus() {
    const overlay = document.getElementById('loginOverlay');
    if (!overlay) return;
    
    if (currentUser) {
        overlay.classList.remove('active');
        overlay.style.display = 'none';
        document.body.style.overflow = '';
    } else {
        overlay.classList.add('active');
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        initGoogleSignIn();
    }
}

function initGoogleSignIn() {
    if (typeof google === 'undefined') {
        setTimeout(initGoogleSignIn, 500);
        return;
    }

    const clientId = "7843657345-placeholder.apps.googleusercontent.com";
    
    if (clientId.includes("placeholder")) {
        console.warn("Google Client ID is a placeholder. Google Login will simulate success for demo purposes.");
    }

    google.accounts.id.initialize({
        client_id: clientId,
        callback: handleGoogleLogin,
        auto_select: false,
        cancel_on_tap_outside: true
    });

    const btnContainer = document.getElementById("googleBtn");
    if (btnContainer) {
        google.accounts.id.renderButton(
            btnContainer,
            { theme: "outline", size: "large", width: 300, shape: "pill", text: "continue_with" }
        );
    }
}

function handleGoogleLogin(response) {
    const payload = parseJwt(response.credential);
    currentUser = {
        username: payload.name,
        email: payload.email,
        user_type: 'patient',
        profile_data: {
            picture: payload.picture,
            google_id: payload.sub
        }
    };
    saveUserAndContinue();
}

function loginAsGuest() {
    currentUser = {
        username: 'Guest_' + Math.floor(Math.random() * 1000),
        email: '',
        user_type: 'guest',
        profile_data: {
            guest_mode: true
        }
    };
    saveUserAndContinue();
}

function saveUserAndContinue() {
    localStorage.setItem('medguide_user', JSON.stringify(currentUser));
    checkLoginStatus();
    loadUserProfile();
    fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentUser)
    }).catch(err => console.log('Sync failed, using local storage'));
}

function logout() {
    if (confirm('Are you sure you want to log out?')) {
        localStorage.removeItem('medguide_user');
        currentUser = null;
        location.reload();
    }
}

function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) { return {}; }
}
function detectLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userLat = pos.coords.latitude;
                userLon = pos.coords.longitude;
                const locText = document.getElementById('locationText');
                if (locText) locText.textContent = `Location detected (${userLat.toFixed(4)}, ${userLon.toFixed(4)})`;
                updateMap();
            },
            () => {
                const locText = document.getElementById('locationText');
                if (locText) locText.textContent = 'Location access denied. Showing default.';
                userLat = 40.7128; userLon = -74.0060;
                updateMap();
            }
        );
    }
}

function updateMap() {
    if (!userLat || !userLon) return;
    const frame = document.getElementById('mapFrame');
    if (frame) {
        frame.src = `https://www.openstreetmap.org/export/embed.html?bbox=${userLon - 0.05},${userLat - 0.03},${userLon + 0.05},${userLat + 0.03}&layer=mapnik&marker=${userLat},${userLon}`;
        frame.style.display = 'block';
    }

    const links = { hospitalLink: 'hospital', pharmacyLink: 'pharmacy', clinicLink: 'clinic' };
    Object.entries(links).forEach(([id, type]) => {
        const el = document.getElementById(id);
        if (el) el.href = `https://www.openstreetmap.org/search?query=${type}+near+${userLat},${userLon}`;
    });
}

// KEYBOARD SHORTCUTS
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeDetailModal();
        closeAddModal();
        closeEditModal();
        closeProtocolTimer();
    }
    if (e.key === '/' && !e.ctrlKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.focus();
    }
});

// ================================================================
// AI CHAT (Step 1)
// ================================================================
function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    appendMessage('user', text);
    input.value = '';
    
    // Simulate AI thinking
    const chatMessages = document.getElementById('chatMessages');
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message ai typing';
    typingIndicator.innerHTML = '<div class="message-content">ClinixAI is thinking...</div>';
    chatMessages.appendChild(typingIndicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Call actual API
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const result = await res.json();
        chatMessages.removeChild(typingIndicator);
        appendMessage('ai', result.response);
    } catch (err) {
        chatMessages.removeChild(typingIndicator);
        appendMessage('ai', "I'm sorry, I'm having trouble connecting to the medical brain right now.");
    }
}

function appendMessage(type, text) {
    const chatMessages = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;
    msgDiv.innerHTML = `<div class="message-content">${text}</div>`;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Enter to send in chat
document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && document.activeElement.id === 'chatInput') {
        e.preventDefault();
        sendMessage();
    }
});

// ================================================================
// HEALTH TRACKER (Step 2)
// ================================================================
async function saveVital(e) {
    e.preventDefault();
    if (!currentUser) return alert('Please login to save vitals');

    const data = {
        username: currentUser.username || currentUser.email,
        type: document.getElementById('vitalType').value,
        value: document.getElementById('vitalValue').value
    };

    try {
        const res = await fetch('/api/vitals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            document.getElementById('vitalForm').reset();
            loadVitals();
        }
    } catch (err) {
        console.error('Error saving vital:', err);
    }
}

async function loadVitals() {
    if (!currentUser) return;
    const username = currentUser.username || currentUser.email;
    try {
        const res = await fetch(`/api/vitals?username=${username}`);
        const result = await res.json();
        renderVitals(result.data);
    } catch (err) {
        console.error('Error loading vitals:', err);
    }
}

function renderVitals(vitals) {
    const list = document.getElementById('vitalsHistory');
    if (!vitals || vitals.length === 0) {
        list.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No records found. Log your first vital!</p>';
        return;
    }

    list.innerHTML = vitals.map(v => `
        <div class="vital-history-item">
            <div class="vital-info">
                <span class="vital-label">${v.type.replace('_', ' ')}</span>
                <span class="vital-val">${v.value}</span>
            </div>
            <div class="vital-date">${new Date(v.recorded_at).toLocaleDateString()}</div>
        </div>
    `).join('');
}

// Hook into navigation
const originalNavigateTo = navigateTo;
window.navigateTo = function(page) {
    originalNavigateTo(page);
    if (page === 'vitals') loadVitals();
};

// ================================================================
// DARK MODE (Step 4)
// ================================================================
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('medguide_theme', newTheme);
    
    updateThemeUI(newTheme);
}

function updateThemeUI(theme) {
    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
}

// Init theme
(function() {
    const savedTheme = localStorage.getItem('medguide_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeUI(savedTheme);
})();
