let allGuidelines = [];
let currentCategory = '';

document.addEventListener('DOMContentLoaded', () => {
    loadGuidelines();
    setupFilters();
    setupSearch();
});

async function loadGuidelines() {
    const res = await fetch('/api/guidelines');
    allGuidelines = await res.json();
    updateStats();
    renderCards();
}

function updateStats() {
    document.getElementById('totalCount').textContent = allGuidelines.length;
    const categories = [...new Set(allGuidelines.map(g => g.category))];
    document.getElementById('categoryCount').textContent = categories.length;
    const critical = allGuidelines.filter(g => ['critical', 'urgent'].includes(g.severity)).length;
    document.getElementById('criticalCount').textContent = critical;
}

function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            renderCards();
        };
    });
}

function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        renderCards(e.target.value.toLowerCase());
    });
}

function renderCards(searchTerm = '') {
    const grid = document.getElementById('guidelinesGrid');
    const emptyState = document.getElementById('emptyState');
    
    let items = allGuidelines;
    if (currentCategory) items = items.filter(g => g.category === currentCategory);
    if (searchTerm) {
        items = items.filter(g => 
            g.title.toLowerCase().includes(searchTerm) ||
            g.summary.toLowerCase().includes(searchTerm)
        );
    }
    
    grid.innerHTML = '';
    
    if (items.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    items.forEach(g => {
        const card = document.createElement('div');
        card.className = 'card';
        card.onclick = () => openModal(g);
        
        card.innerHTML = `
            <div class="card-badges">
                <span class="badge badge-category">${g.category}</span>
                <span class="badge badge-severity ${g.severity}">${g.severity}</span>
            </div>
            <h3 class="card-title">${g.title}</h3>
            <p class="card-summary">${g.summary}</p>
            ${g.medicines && g.medicines.length > 0 ? `
                <div class="card-medicines">
                    ${g.medicines.slice(0, 3).map(m => `<span class="med-tag">💊 ${m}</span>`).join('')}
                </div>
            ` : ''}
            <div class="card-footer">
                <span class="view-btn">View Details →</span>
            </div>
        `;
        
        grid.appendChild(card);
    });
}

function openModal(g) {
    document.getElementById('modalTitle').textContent = g.title;
    document.getElementById('modalSummary').textContent = g.summary;
    document.getElementById('modalBadges').innerHTML = `
        <span class="badge badge-category">${g.category}</span>
        <span class="badge badge-severity ${g.severity}">${g.severity}</span>
    `;
    
    const medsDiv = document.getElementById('modalMedicines');
    if (g.medicines && g.medicines.length > 0) {
        medsDiv.innerHTML = '<strong>Medicines:</strong><br>' + 
            g.medicines.map(m => `<span class="med-tag" style="display:inline-block;margin:0.25rem;">💊 ${m}</span>`).join('');
    } else {
        medsDiv.innerHTML = '';
    }
    
    document.getElementById('detailOverlay').classList.add('active');
}

function closeModal() {
    document.getElementById('detailOverlay').classList.remove('active');
}

document.getElementById('detailOverlay').addEventListener('click', (e) => {
    if (e.target.id === 'detailOverlay') closeModal();
});
