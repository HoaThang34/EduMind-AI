# Career UI Restore & Data Recovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khoi phuc data nganh bi mat va viet lai 3 template Bootstrap thanh Tailwind theo style f4cc1be.

**Architecture:** Backup DB, seed lai data nganh, viet lai 3 template (browse, compare, map) tu base f4cc1be voi tinh nang moi ghep len, sua rebuild_db.py de tu dong seed.

**Tech Stack:** Flask, Tailwind CSS (CDN), Chart.js 4.x, D3.js v7, SQLite, Be Vietnam Pro font

---

## Task 1: Backup database va seed lai data nganh

**Files:**
- Modify: `rebuild_db.py:13-14` (add imports), `rebuild_db.py:161-164` (add seed calls)

- [ ] **Step 1: Backup database**

```bash
cp database.db "database.db.backup-$(date +%Y%m%d-%H%M%S)"
```

Verify backup:
```bash
ls -la database.db.backup-*
```

- [ ] **Step 2: Run migrate.py to ensure schema is complete**

```bash
python migrate.py
```

Expected: "Migration complete" message, no errors. This adds missing columns (admission_block, entry_score) without deleting data.

- [ ] **Step 3: Run seed_majors.py to restore major data**

```bash
python seed_majors.py
```

Expected: "Done: ~150 majors added, 0 skipped" (or similar count). This inserts from `data/majors_seed.json`.

- [ ] **Step 4: Run seed_entry_scores.py to restore historical scores**

```bash
python seed_entry_scores.py
```

Expected: "Seeded ~150 majors with admission_block + entry scores."

- [ ] **Step 5: Verify data is restored**

```bash
python -c "
from app import app
from models import db, UniversityMajor, MajorSubjectWeight, MajorEntryScore
with app.app_context():
    m = UniversityMajor.query.count()
    w = MajorSubjectWeight.query.count()
    e = MajorEntryScore.query.count()
    print(f'Majors: {m}, Weights: {w}, EntryScores: {e}')
    assert m > 0, 'No majors!'
    assert w > 0, 'No weights!'
    assert e > 0, 'No entry scores!'
    print('All OK')
"
```

Expected: Majors > 100, Weights > 300, EntryScores > 300.

- [ ] **Step 6: Update rebuild_db.py to auto-seed majors after rebuild**

Add imports after line 13:

```python
from seed_majors import seed as seed_majors
from seed_entry_scores import seed as seed_entry_scores
```

Add seed calls after the existing `db.session.commit()` on line 163, before the final print statements:

```python
        # 5. Seed university majors + entry scores
        print("Seeding university majors...")
        seed_majors()
        print("Seeding entry scores...")
        seed_entry_scores()
```

The final lines 164-165 (`print("Da khoi tao...")`) stay as-is after the new code.

- [ ] **Step 7: Commit**

```bash
git add rebuild_db.py
git commit -m "fix: restore major data + auto-seed in rebuild_db.py"
```

---

## Task 2: Rewrite browse page from f4cc1be base

**Files:**
- Rewrite: `templates/student_career_browse.html`

**Reference:** `git show f4cc1be:templates/student_career_browse.html` for base template.

The browse page is written from scratch using the f4cc1be base (Tailwind, CSS Grid, mini radar, pin/target buttons) with new features added on top.

- [ ] **Step 1: Write the new browse template**

Rewrite `templates/student_career_browse.html` with this complete content:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Duyệt ngành – EduMind AI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>tailwind.config={theme:{extend:{fontFamily:{sans:['"Be Vietnam Pro"','system-ui','sans-serif']}}}}</script>
  <style>
    body { background:#f5f5f5; font-family:'Be Vietnam Pro',system-ui,sans-serif; }
    .card { background:#fff; border:1px solid #e5e5e5; border-radius:8px; }
    .major-card { transition:box-shadow .15s ease; }
    .major-card:hover { box-shadow:0 4px 16px rgba(0,0,0,.08); }
    .tag-ok   { background:#dcfce7; color:#166534; }
    .tag-warn { background:#fef9c3; color:#854d0e; }
    .tag-fail { background:#fee2e2; color:#991b1b; }
    #grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }
    .btn-action { font-size:11px; padding:3px 9px; border-radius:5px; border:1px solid #e5e5e5; background:#fff; cursor:pointer; font-weight:500; transition:background .1s; }
    .btn-action:hover { background:#f0f0f0; }
    .btn-action.active { background:#0070f3; color:#fff; border-color:#0070f3; }
    .btn-action.active-target { background:#7c3aed; color:#fff; border-color:#7c3aed; }
    .sort-pill { font-size:10px; padding:2px 8px; border-radius:4px; cursor:pointer; font-weight:500; transition:background .1s; }
    .sort-pill.active { background:#0070f3; color:#fff; }
    .sort-pill:not(.active) { background:#f0f0f0; color:#6b7280; }
    .filter-chip { font-size:10px; padding:2px 8px; border-radius:4px; background:#0070f3; color:#fff; cursor:pointer; }
    .spinner { width:32px; height:32px; border:3px solid #e5e5e5; border-top-color:#0070f3; border-radius:50%; animation:spin .6s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
    input[type=range] { -webkit-appearance:none; height:4px; background:#e5e5e5; border-radius:2px; outline:none; }
    input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:14px; height:14px; border-radius:50%; background:#0070f3; cursor:pointer; }
  </style>
</head>
<body class="min-h-screen">

<!-- Nav -->
<nav class="bg-white border-b border-[#e5e5e5] px-6 py-3 flex items-center gap-4">
  <a href="{{ url_for('career.career_main') }}" class="text-sm text-gray-500 hover:text-gray-800 flex items-center gap-1.5">
    <i class="fas fa-arrow-left text-xs"></i> Phan tich nang luc
  </a>
  <span class="text-[#e5e5e5]">/</span>
  <span class="text-sm font-semibold text-gray-800">Duyet tat ca nganh</span>
  <div class="ml-auto flex items-center gap-3">
    <span class="text-sm text-gray-500">{{ student.name }}</span>
  </div>
</nav>

<!-- Filter bar -->
<div class="bg-white border-b border-[#e5e5e5] px-4 py-3">
  <div class="max-w-7xl mx-auto flex flex-wrap gap-2 items-center">
    <div class="relative flex-1 min-w-[200px] max-w-xs">
      <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
      <input type="text" id="searchInput" placeholder="Tim nganh hoac truong..."
        class="w-full pl-8 pr-3 py-1.5 text-sm border border-[#e5e5e5] rounded-md focus:outline-none focus:border-blue-400">
    </div>
    <select id="universityFilter" class="text-sm border border-[#e5e5e5] rounded-md px-2.5 py-1.5 bg-white focus:outline-none">
      <option value="">Tat ca truong</option>
    </select>
    <select id="blockFilter" class="text-sm border border-[#e5e5e5] rounded-md px-2.5 py-1.5 bg-white focus:outline-none">
      <option value="">Tat ca khoi</option>
      <option>A1</option><option>A00</option><option>B00</option><option>D01</option><option>C00</option>
    </select>
    <select id="groupFilter" class="text-sm border border-[#e5e5e5] rounded-md px-2.5 py-1.5 bg-white focus:outline-none">
      <option value="">Tat ca nhom nganh</option>
      {% for g in groups %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
    </select>
    <div class="flex items-center gap-1.5">
      <span class="text-[10px] text-gray-400 whitespace-nowrap">Phu hop</span>
      <input type="range" id="fitRange" min="0" max="100" value="0" class="w-20">
      <span id="fitRangeLabel" class="text-[10px] font-bold text-gray-600">0%</span>
    </div>
  </div>
  <!-- Sort + chips -->
  <div class="max-w-7xl mx-auto flex flex-wrap gap-2 items-center mt-2">
    <span class="text-[10px] text-gray-400">Sap xep:</span>
    <span class="sort-pill active" data-sort="fit">Phu hop nhat</span>
    <span class="sort-pill" data-sort="score_desc">DC cao → thap</span>
    <span class="sort-pill" data-sort="score_asc">DC thap → cao</span>
    <span class="sort-pill" data-sort="name">Ten A-Z</span>
    <div id="activeChips" class="flex gap-1 flex-wrap ml-2"></div>
  </div>
</div>

<!-- Top bar -->
<div class="max-w-7xl mx-auto px-4 pt-4 flex justify-between items-center">
  <span id="countBadge" class="text-xs text-gray-400"></span>
  <div class="flex gap-2">
    <button onclick="openSimulator()" class="text-xs px-3 py-1.5 border border-[#e5e5e5] rounded-md bg-white hover:bg-[#f0f0f0] font-medium text-gray-700">
      <i class="fas fa-crosshairs mr-1"></i>Mo phong diem
    </button>
    <button id="compareBtn" class="hidden text-xs px-3 py-1.5 bg-[#0070f3] text-white rounded-md font-medium" onclick="goCompare()">
      So sanh (<span id="compareCount">0</span>)
    </button>
  </div>
</div>

<div class="max-w-7xl mx-auto px-4 py-4">
  <div id="loadingState" class="flex justify-center py-20"><div class="spinner"></div></div>
  <div id="grid" class="hidden"></div>
  <div id="emptyState" class="hidden text-center py-20 text-gray-400 text-sm">Khong co nganh nao phu hop voi bo loc hien tai.</div>
</div>

<!-- Simulator Modal -->
<div id="simulatorModal" class="fixed inset-0 bg-black/40 z-50 hidden flex items-center justify-center p-4">
  <div class="card w-full max-w-2xl p-6 max-h-[80vh] overflow-y-auto">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-bold text-gray-900"><i class="fas fa-crosshairs mr-1.5 text-[#0070f3]"></i>Neu diem cua ban la...</h3>
      <button onclick="closeSimulator()" class="text-gray-400 hover:text-gray-700"><i class="fas fa-times"></i></button>
    </div>
    <p class="text-xs text-gray-400 mb-3">Dieu chinh diem du kien — danh sach nganh se cap nhat ngay</p>
    <div id="simSliders" class="grid grid-cols-2 md:grid-cols-3 gap-3"></div>
    <div class="flex justify-end gap-2 mt-4 pt-3 border-t border-[#f0f0f0]">
      <button onclick="resetSimulator()" class="text-xs px-3 py-1.5 border border-[#e5e5e5] rounded-md bg-white hover:bg-[#f0f0f0]">Reset ve diem that</button>
      <button onclick="closeSimulator()" class="text-xs px-3 py-1.5 bg-gray-800 text-white rounded-md">Dong</button>
    </div>
  </div>
</div>

<!-- Toast -->
<div id="toast" class="fixed bottom-5 right-5 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg hidden z-50"></div>

<script>
let allMajors = [], simScores = {}, realScores = {};
let compareIds = new Set(JSON.parse(sessionStorage.getItem('compare_major_ids') || '[]'));
let currentSort = 'fit', simTimer = null, searchTimer = null;
const miniCharts = {}, sparkCharts = {};

// ── Fetch & Filters ────────────────────────────────────────────────
async function fetchMajors() {
  const params = new URLSearchParams();
  const q = document.getElementById('searchInput').value.trim();
  const university = document.getElementById('universityFilter').value;
  const block = document.getElementById('blockFilter').value;
  const group = document.getElementById('groupFilter').value;
  const minFit = parseInt(document.getElementById('fitRange').value) || 0;
  if (q) params.set('q', q);
  if (university) params.set('university', university);
  if (block) params.set('admission_block', block);
  if (group) params.set('group', group);
  if (minFit > 0) params.set('min_fit', minFit);
  const res = await fetch('/api/student/career/browse?' + params);
  const d = await res.json();
  allMajors = d.majors || [];
  document.getElementById('loadingState').classList.add('hidden');
  renderGrid();
  updateChips();
}

function renderGrid() {
  const sorted = [...allMajors].sort((a, b) => {
    if (currentSort === 'fit') return b.fit_pct - a.fit_pct;
    if (currentSort === 'score_desc') return (b.entry_score||0) - (a.entry_score||0);
    if (currentSort === 'score_asc') return (a.entry_score||0) - (b.entry_score||0);
    return a.name.localeCompare(b.name);
  });
  Object.values(miniCharts).forEach(c => c.destroy()); Object.keys(miniCharts).forEach(k => delete miniCharts[k]);
  Object.values(sparkCharts).forEach(c => c.destroy()); Object.keys(sparkCharts).forEach(k => delete sparkCharts[k]);
  const grid = document.getElementById('grid');
  const empty = document.getElementById('emptyState');
  document.getElementById('countBadge').textContent = sorted.length + ' nganh';
  if (sorted.length === 0) { grid.classList.add('hidden'); empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden'); grid.classList.remove('hidden');
  grid.innerHTML = sorted.map(m => majorCard(m)).join('');
  sorted.forEach(m => { initMiniRadar(m); initSparkline(m); });
}

// ── Card ────────────────────────────────────────────────────────────
function fitClass(p) { return p>=80?'text-green-600':p>=60?'text-amber-600':'text-red-500'; }
function fitBarClass(p) { return p>=80?'bg-green-500':p>=60?'bg-amber-400':'bg-red-400'; }
function fitTagClass(p) { return p>=80?'tag-ok':p>=60?'tag-warn':'tag-fail'; }
function getTrend(scores) {
  if (!scores || scores.length < 2) return {label:'—',cls:'text-gray-400'};
  const diff = (scores[scores.length-1].score - scores[0].score).toFixed(1);
  if (diff > 0) return {label:'↑ +'+diff,cls:'text-red-500'};
  if (diff < 0) return {label:'↓ '+diff,cls:'text-green-600'};
  return {label:'→ 0',cls:'text-gray-400'};
}

function majorCard(m) {
  const checked = compareIds.has(m.id) ? 'checked' : '';
  const pinBtn = m.is_pinned
    ? `<button onclick="unpin(${m.id},this)" class="btn-action active"><i class="fas fa-thumbtack mr-1"></i>Da ghim</button>`
    : `<button onclick="pin(${m.id},this)" class="btn-action"><i class="far fa-thumbtack mr-1"></i>Ghim</button>`;
  const targetBtn = m.is_target
    ? `<button class="btn-action active-target" disabled><i class="fas fa-star mr-1"></i>Muc tieu</button>`
    : `<button onclick="setTarget(${m.id},this)" class="btn-action"><i class="far fa-star mr-1"></i>Muc tieu</button>`;
  const trend = getTrend(m.entry_scores);

  return `<div class="card major-card p-4 flex flex-col gap-2.5" id="card-${m.id}">
    <div>
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-gray-900 text-sm leading-tight truncate">${m.name}</div>
          <div class="text-[11px] text-gray-400 truncate mt-0.5">${m.university}</div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <span class="text-xs font-bold tabular-nums ${fitClass(m.fit_pct)}">${m.fit_pct.toFixed(0)}%</span>
          <input type="checkbox" ${checked} onchange="toggleCompare(${m.id},this.checked)"
            class="w-3.5 h-3.5 rounded border-gray-300 text-[#0070f3] cursor-pointer">
        </div>
      </div>
      <div class="text-[10px] text-gray-400 mt-0.5">${m.admission_block||''} ${m.admission_block&&m.entry_score?'|':''} ${m.entry_score?'DC: '+m.entry_score:''}</div>
      ${m.major_group?`<span class="inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded bg-[#f0f0f0] text-gray-500">${m.major_group}</span>`:''}
    </div>
    <div class="flex items-center gap-2">
      <div class="flex-1 bg-[#f5f5f5] rounded-full h-1.5">
        <div class="h-1.5 rounded-full ${fitBarClass(m.fit_pct)}" style="width:${Math.min(m.fit_pct,100).toFixed(0)}%"></div>
      </div>
      <span class="text-[10px] ${fitTagClass(m.fit_pct)} px-1.5 py-0.5 rounded font-medium">${m.fit_pct.toFixed(0)}%</span>
    </div>
    <div class="flex justify-center" style="height:120px">
      <canvas id="mini-${m.id}" width="120" height="120"></canvas>
    </div>
    <div class="flex items-center justify-between px-1">
      <span class="text-[10px] text-gray-400">Xu huong:</span>
      <canvas id="spark-${m.id}" width="80" height="28"></canvas>
      <span class="text-[10px] font-bold ${trend.cls}">${trend.label}</span>
    </div>
    <div class="flex gap-2 pt-1.5 border-t border-[#f0f0f0]">
      ${pinBtn}
      ${targetBtn}
    </div>
  </div>`;
}

// ── Mini radar ──────────────────────────────────────────────────────
function initMiniRadar(m) {
  const canvas = document.getElementById('mini-'+m.id);
  if (!canvas || !m.radar || m.radar.labels.length===0) return;
  miniCharts[m.id] = new Chart(canvas.getContext('2d'), {
    type:'radar',
    data:{
      labels:m.radar.labels,
      datasets:[
        {data:m.radar.student_scores,backgroundColor:'rgba(0,112,243,.12)',borderColor:'#0070f3',borderWidth:1.5,pointRadius:2,pointBackgroundColor:'#0070f3'},
        {data:m.radar.major_scores,backgroundColor:'rgba(249,115,22,.08)',borderColor:'#f97316',borderWidth:1.5,borderDash:[4,3],pointRadius:2,pointBackgroundColor:'#f97316'},
      ]
    },
    options:{responsive:false,scales:{r:{min:0,max:10,ticks:{display:false},grid:{color:'#eee'},pointLabels:{font:{size:8},color:'#9ca3af'}}},plugins:{legend:{display:false},tooltip:{enabled:false}}}
  });
}

// ── Sparkline ───────────────────────────────────────────────────────
function initSparkline(m) {
  const canvas = document.getElementById('spark-'+m.id);
  if (!canvas || !m.entry_scores || !m.entry_scores.length) return;
  sparkCharts[m.id] = new Chart(canvas.getContext('2d'), {
    type:'line',
    data:{labels:m.entry_scores.map(s=>s.year),datasets:[{data:m.entry_scores.map(s=>s.score),borderColor:'#3b82f6',borderWidth:1.5,pointRadius:1.5,fill:false,tension:0.3}]},
    options:{plugins:{legend:{display:false}},scales:{x:{display:false},y:{display:false}},animation:false,responsive:false}
  });
}

// ── Pin / Target / Compare ──────────────────────────────────────────
function showToast(msg) {
  const t=document.getElementById('toast'); t.textContent=msg; t.classList.remove('hidden');
  setTimeout(()=>t.classList.add('hidden'),2000);
}

async function pin(id,btn) {
  const r=await fetch('/api/student/career/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({major_id:id})});
  if(r.ok){btn.className='btn-action active';btn.innerHTML='<i class="fas fa-thumbtack mr-1"></i>Da ghim';btn.onclick=function(){unpin(id,btn)};const m=allMajors.find(x=>x.id===id);if(m)m.is_pinned=true;showToast('Da ghim nganh');}
}
async function unpin(id,btn) {
  const r=await fetch('/api/student/career/pin/'+id,{method:'DELETE'});
  if(r.ok){btn.className='btn-action';btn.innerHTML='<i class="far fa-thumbtack mr-1"></i>Ghim';btn.onclick=function(){pin(id,btn)};const m=allMajors.find(x=>x.id===id);if(m)m.is_pinned=false;showToast('Da bo ghim');}
}
async function setTarget(id,btn) {
  const r=await fetch('/api/student/career/target',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({major_id:id})});
  if(r.ok){document.querySelectorAll('.btn-action.active-target').forEach(b=>{b.className='btn-action';b.innerHTML='<i class="far fa-star mr-1"></i>Muc tieu';b.disabled=false;});btn.className='btn-action active-target';btn.innerHTML='<i class="fas fa-star mr-1"></i>Muc tieu';btn.disabled=true;allMajors.forEach(m=>m.is_target=(m.id===id));showToast('Da dat lam nganh muc tieu');}
}

function toggleCompare(id,checked) {
  if(checked){if(compareIds.size>=4){alert('Toi da 4 nganh');return;}compareIds.add(id);}else{compareIds.delete(id);}
  sessionStorage.setItem('compare_major_ids',JSON.stringify([...compareIds]));
  document.getElementById('compareCount').textContent=compareIds.size;
  document.getElementById('compareBtn').classList.toggle('hidden',compareIds.size<2);
}
function goCompare() { window.location.href='/student/career/compare?major_ids='+[...compareIds].join(','); }

// ── Sort pills ──────────────────────────────────────────────────────
document.querySelectorAll('.sort-pill').forEach(pill=>{
  pill.addEventListener('click',function(){
    document.querySelectorAll('.sort-pill').forEach(p=>p.classList.remove('active'));
    this.classList.add('active');
    currentSort=this.dataset.sort;
    renderGrid();
  });
});

// ── Filter chips ────────────────────────────────────────────────────
function updateChips() {
  const c=document.getElementById('activeChips'); c.innerHTML='';
  const add=(label,clearFn)=>{const s=document.createElement('span');s.className='filter-chip';s.textContent=label+' ×';s.onclick=clearFn;c.appendChild(s);};
  const q=document.getElementById('searchInput').value.trim();
  const uni=document.getElementById('universityFilter').value;
  const blk=document.getElementById('blockFilter').value;
  const grp=document.getElementById('groupFilter').value;
  const fit=parseInt(document.getElementById('fitRange').value)||0;
  if(q) add('"'+q+'"',()=>{document.getElementById('searchInput').value='';fetchMajors();});
  if(uni) add(uni,()=>{document.getElementById('universityFilter').value='';fetchMajors();});
  if(blk) add('Khoi: '+blk,()=>{document.getElementById('blockFilter').value='';fetchMajors();});
  if(grp) add(grp,()=>{document.getElementById('groupFilter').value='';fetchMajors();});
  if(fit>0) add('>='+fit+'%',()=>{document.getElementById('fitRange').value=0;document.getElementById('fitRangeLabel').textContent='0%';fetchMajors();});
}

// ── Filter listeners ────────────────────────────────────────────────
document.getElementById('searchInput').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(fetchMajors,400);});
['universityFilter','blockFilter','groupFilter'].forEach(id=>document.getElementById(id).addEventListener('change',fetchMajors));
document.getElementById('fitRange').addEventListener('input',function(){document.getElementById('fitRangeLabel').textContent=this.value+'%';clearTimeout(searchTimer);searchTimer=setTimeout(fetchMajors,400);});

// ── Populate university dropdown ────────────────────────────────────
async function populateUniversities() {
  const r=await fetch('/api/student/career/browse');
  const d=await r.json();
  const unis=[...new Set((d.majors||[]).map(m=>m.university))].sort();
  const sel=document.getElementById('universityFilter');
  unis.forEach(u=>sel.add(new Option(u,u)));
}

// ── Simulator ───────────────────────────────────────────────────────
function openSimulator() {
  document.getElementById('simulatorModal').classList.remove('hidden');
  fetch('/api/student/career/map-data').then(r=>r.json()).then(data=>{
    const subjects=new Set();
    data.majors.forEach(m=>Object.keys(m.weight_vector).forEach(s=>subjects.add(s)));
    const container=document.getElementById('simSliders');container.innerHTML='';
    subjects.forEach(subj=>{
      const current=realScores[subj]||5.0; simScores[subj]=current;
      const id='sim-'+subj.replace(/\s/g,'_');
      const div=document.createElement('div');
      div.innerHTML=`<label class="text-[10px] font-semibold text-gray-600">${subj}</label>
        <div class="flex items-center gap-2"><input type="range" min="0" max="10" step="0.1" value="${current}" data-subj="${subj}" oninput="onSimSlider(this)" class="flex-1"><span class="text-xs font-bold tabular-nums w-8 text-right" id="${id}">${current}</span></div>`;
      container.appendChild(div);
    });
  });
}
function closeSimulator() { document.getElementById('simulatorModal').classList.add('hidden'); }
document.getElementById('simulatorModal').addEventListener('click',function(e){if(e.target===this)closeSimulator();});

function onSimSlider(el) {
  simScores[el.dataset.subj]=parseFloat(el.value);
  document.getElementById('sim-'+el.dataset.subj.replace(/\s/g,'_')).textContent=el.value;
  clearTimeout(simTimer);simTimer=setTimeout(runSimulate,300);
}
async function runSimulate() {
  const r=await fetch('/api/student/career/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scores:simScores})});
  const d=await r.json();
  const fitMap={};d.majors.forEach(m=>{fitMap[m.id]=m.fit_pct;});
  allMajors.forEach(m=>{if(fitMap[m.id]!==undefined)m.fit_pct=fitMap[m.id];});
  renderGrid();
}
function resetSimulator() {
  simScores={...realScores};
  document.querySelectorAll('[data-subj]').forEach(el=>{
    el.value=realScores[el.dataset.subj]||5.0;
    document.getElementById('sim-'+el.dataset.subj.replace(/\s/g,'_')).textContent=el.value;
  });
  runSimulate();
}

// ── Init ────────────────────────────────────────────────────────────
document.getElementById('compareCount').textContent=compareIds.size;
if(compareIds.size>=2) document.getElementById('compareBtn').classList.remove('hidden');
populateUniversities();
fetchMajors();
</script>
</body>
</html>
```

- [ ] **Step 2: Test browse page loads**

```bash
# Start dev server (if not running)
python app.py &
# Open in browser: http://localhost:5000/student/career/browse
# Verify: Tailwind styling, grid layout, mini radar charts visible, pin/target buttons present, sparklines, filters work
```

- [ ] **Step 3: Commit**

```bash
git add templates/student_career_browse.html
git commit -m "feat: rewrite browse page from f4cc1be base with new features (Tailwind)"
```

---

## Task 3: Rewrite compare page in Tailwind

**Files:**
- Rewrite: `templates/student_career_compare.html`

- [ ] **Step 1: Write the new compare template**

Rewrite `templates/student_career_compare.html` with this content:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>So sanh nganh – EduMind AI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>tailwind.config={theme:{extend:{fontFamily:{sans:['"Be Vietnam Pro"','system-ui','sans-serif']}}}}</script>
  <style>
    body { background:#f5f5f5; font-family:'Be Vietnam Pro',system-ui,sans-serif; }
    .card { background:#fff; border:1px solid #e5e5e5; border-radius:8px; }
  </style>
</head>
<body class="min-h-screen">

<nav class="bg-white border-b border-[#e5e5e5] px-6 py-3 flex items-center gap-4">
  <a href="{{ url_for('career.career_browse') }}" class="text-sm text-gray-500 hover:text-gray-800 flex items-center gap-1.5">
    <i class="fas fa-arrow-left text-xs"></i> Duyet nganh
  </a>
  <span class="text-[#e5e5e5]">/</span>
  <span class="text-sm font-semibold text-gray-800">So sanh nganh</span>
  <div class="ml-auto flex items-center gap-3">
    <span class="text-sm text-gray-500">{{ student.name }}</span>
  </div>
</nav>

<div class="max-w-7xl mx-auto px-4 py-6">
  <div class="flex items-center justify-between mb-5">
    <h1 class="text-lg font-bold text-gray-900">So sanh nganh</h1>
    <a href="{{ url_for('career.career_browse') }}" class="text-sm text-gray-500 hover:text-gray-800">
      <i class="fas fa-arrow-left mr-1"></i>Quay lai
    </a>
  </div>

  <!-- Selected majors + add -->
  <div class="card p-4 mb-4">
    <div id="selectedChips" class="flex flex-wrap gap-2 items-center"></div>
    <div class="mt-2 relative max-w-xs">
      <input type="text" id="addSearch" placeholder="+ Them nganh (go de tim)..."
        class="w-full text-sm border border-[#e5e5e5] rounded-md px-3 py-1.5 focus:outline-none focus:border-blue-400">
      <div id="addDropdown" class="hidden absolute top-full left-0 w-full bg-white border border-[#e5e5e5] rounded-md mt-1 max-h-48 overflow-y-auto z-50 shadow-lg"></div>
    </div>
  </div>

  <!-- Radar chart -->
  <div class="card p-5 mb-4">
    <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Radar so sanh mon hoc</div>
    <div class="flex justify-center">
      <canvas id="radarChart" style="max-width:500px;max-height:400px"></canvas>
    </div>
  </div>

  <!-- Line chart -->
  <div class="card p-5 mb-4">
    <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Xu huong diem chuan (2023–2025)</div>
    <canvas id="lineChart" height="120"></canvas>
  </div>

  <!-- Versus table -->
  <div class="card overflow-hidden">
    <div class="px-5 py-3 border-b border-[#e5e5e5]">
      <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">So sanh chi tiet</span>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead id="vsThead" class="bg-[#fafafa] text-[11px] text-gray-400 uppercase"></thead>
        <tbody id="vsTbody" class="divide-y divide-[#f0f0f0]"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
const COLORS=['#0070f3','#f59e0b','#10b981','#a78bfa'];
let compareIds=new Set(JSON.parse(sessionStorage.getItem('compare_major_ids')||'[]'));
let currentData=null, radarChart=null, lineChart=null, allMajorsCache=null;

const urlIds=new URLSearchParams(location.search).get('major_ids')||'';
if(urlIds){urlIds.split(',').filter(Boolean).forEach(id=>compareIds.add(parseInt(id)));sessionStorage.setItem('compare_major_ids',JSON.stringify([...compareIds]));}

async function loadAndRender(){
  if(!compareIds.size){clearAll();return;}
  const r=await fetch('/api/student/career/compare?major_ids='+[...compareIds].join(','));
  currentData=await r.json();
  renderChips();renderRadar();renderLine();renderTable();
}

function renderChips(){
  const c=document.getElementById('selectedChips');c.innerHTML='';
  if(!currentData)return;
  currentData.majors.forEach((m,i)=>{
    const s=document.createElement('span');
    s.className='inline-flex items-center gap-1.5 text-xs text-white px-2.5 py-1 rounded-md font-medium';
    s.style.background=COLORS[i];
    s.innerHTML=`${m.name} — ${m.university}<button onclick="removeMajor(${m.id})" class="ml-1 opacity-70 hover:opacity-100"><i class="fas fa-times text-[10px]"></i></button>`;
    c.appendChild(s);
  });
}

function removeMajor(id){compareIds.delete(id);sessionStorage.setItem('compare_major_ids',JSON.stringify([...compareIds]));loadAndRender();}

function renderRadar(){
  if(radarChart)radarChart.destroy();
  if(!currentData||!currentData.majors.length)return;
  const allLabels=[...new Set(currentData.majors.flatMap(m=>m.radar.labels))];
  const datasets=currentData.majors.map((m,i)=>({
    label:m.name+' ('+m.university+')',
    data:allLabels.map(l=>{const idx=m.radar.labels.indexOf(l);return idx>=0?m.radar.major_scores[idx]:0;}),
    borderColor:COLORS[i],backgroundColor:COLORS[i]+'33',borderWidth:2
  }));
  if(currentData.student_scores&&Object.keys(currentData.student_scores).length){
    datasets.push({label:'Diem cua ban',data:allLabels.map(l=>currentData.student_scores[l]||0),borderColor:'#94a3b8',backgroundColor:'#94a3b822',borderWidth:2,borderDash:[5,3]});
  }
  radarChart=new Chart(document.getElementById('radarChart'),{
    type:'radar',data:{labels:allLabels,datasets},
    options:{scales:{r:{min:0,max:10,ticks:{stepSize:2,font:{size:10},color:'#9ca3af'},grid:{color:'#e5e5e5'},pointLabels:{font:{size:11},color:'#374151'}}},plugins:{legend:{position:'bottom',labels:{font:{size:10}}}}}
  });
}

function renderLine(){
  if(lineChart)lineChart.destroy();
  if(!currentData||!currentData.majors.length)return;
  const datasets=currentData.majors.map((m,i)=>({
    label:m.name,data:m.entry_scores.map(s=>({x:s.year,y:s.score})),
    borderColor:COLORS[i],borderWidth:2,pointRadius:4,tension:0.3,fill:false
  }));
  lineChart=new Chart(document.getElementById('lineChart'),{
    type:'line',data:{datasets},
    options:{scales:{x:{type:'linear',min:2022,max:2026,ticks:{stepSize:1,callback:v=>Number.isInteger(v)?v:'',font:{size:10}}},y:{title:{display:true,text:'Diem chuan',font:{size:10}},ticks:{font:{size:10}}}},plugins:{legend:{position:'bottom',labels:{font:{size:10}}}}}
  });
}

function renderTable(){
  const thead=document.getElementById('vsThead'),tbody=document.getElementById('vsTbody');
  thead.innerHTML=tbody.innerHTML='';
  if(!currentData||!currentData.majors.length)return;
  const hr=document.createElement('tr');
  hr.innerHTML='<th class="px-4 py-2.5 text-left" style="width:160px">Tieu chi</th>';
  currentData.majors.forEach((m,i)=>{hr.innerHTML+=`<th class="px-4 py-2.5 text-left" style="color:${COLORS[i]}">${m.name}<br><span class="font-normal text-gray-400">${m.university}</span></th>`;});
  thead.appendChild(hr);
  const allSubjects=[...new Set(currentData.majors.flatMap(m=>m.weights.map(w=>w.subject_name)))];
  const rows=[
    {label:'% Phu hop',fn:m=>`<strong class="${m.fit_pct>=70?'text-green-600':m.fit_pct>=50?'text-amber-600':'text-red-500'}">${Math.round(m.fit_pct)}%</strong>`,num:m=>m.fit_pct,higher:true},
    {label:'DC 2025',fn:m=>m.entry_score||'—',num:m=>m.entry_score||0,higher:false},
    {label:'Khoi xet tuyen',fn:m=>m.admission_block||'—',num:null},
    {label:'Xu huong DC',fn:m=>{const s=m.entry_scores;if(!s||s.length<2)return'—';const d=(s[s.length-1].score-s[0].score).toFixed(1);return d>0?`<span class="text-red-500">↑ +${d}</span>`:d<0?`<span class="text-green-600">↓ ${d}</span>`:'→ 0';},num:null},
    ...allSubjects.map(subj=>({label:'Yeu cau '+subj,fn:(m,ss)=>{const w=m.weights.find(x=>x.subject_name===subj);if(!w)return'—';const stu=ss[subj];return stu!==undefined?`<span class="${stu>=w.min_score?'text-green-600':'text-red-500'}">${w.min_score} ${stu>=w.min_score?'✓':'✗'}</span>`:w.min_score+'';},num:m=>{const w=m.weights.find(x=>x.subject_name===subj);return w?w.min_score:0;},higher:null}))
  ];
  rows.forEach(rd=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td class="px-4 py-2.5 font-medium text-gray-500 text-xs">${rd.label}</td>`;
    const vals=rd.num?currentData.majors.map(m=>rd.num(m)):null;
    const best=vals&&rd.higher!==null?(rd.higher===false?Math.min(...vals):Math.max(...vals)):null;
    currentData.majors.forEach((m,i)=>{
      const cell=rd.fn(m,currentData.student_scores||{});
      const isBest=vals!==null&&best!==null&&vals[i]===best;
      tr.innerHTML+=`<td class="px-4 py-2.5 ${isBest?'bg-green-50':''}">${cell}</td>`;
    });
    tbody.appendChild(tr);
  });
}

function clearAll(){if(radarChart)radarChart.destroy();if(lineChart)lineChart.destroy();document.getElementById('vsThead').innerHTML='';document.getElementById('vsTbody').innerHTML='';document.getElementById('selectedChips').innerHTML='';}

// ── Add search ──────────────────────────────────────────────────────
let addTimer;
document.getElementById('addSearch').addEventListener('input',async function(){
  clearTimeout(addTimer);
  addTimer=setTimeout(async()=>{
    const q=this.value.trim();
    if(!q){document.getElementById('addDropdown').classList.add('hidden');return;}
    if(!allMajorsCache){const r=await fetch('/api/student/career/browse');allMajorsCache=(await r.json()).majors;}
    const filtered=allMajorsCache.filter(m=>(m.name+m.university).toLowerCase().includes(q.toLowerCase())&&!compareIds.has(m.id)).slice(0,8);
    const dd=document.getElementById('addDropdown');dd.innerHTML='';
    filtered.forEach(m=>{
      const item=document.createElement('div');
      item.className='px-3 py-2 text-xs hover:bg-[#f5f5f5] cursor-pointer';
      item.textContent=m.name+' — '+m.university;
      item.onclick=()=>{if(compareIds.size>=4){alert('Toi da 4 nganh');return;}compareIds.add(m.id);sessionStorage.setItem('compare_major_ids',JSON.stringify([...compareIds]));document.getElementById('addSearch').value='';dd.classList.add('hidden');loadAndRender();};
      dd.appendChild(item);
    });
    dd.classList.toggle('hidden',filtered.length===0);
  },300);
});
document.addEventListener('click',e=>{if(!e.target.closest('#addSearch'))document.getElementById('addDropdown').classList.add('hidden');});

loadAndRender();
</script>
</body>
</html>
```

- [ ] **Step 2: Test compare page**

Open `http://localhost:5000/student/career/compare?major_ids=1,2` in browser.
Verify: radar chart, line chart, versus table, add/remove chips, Tailwind styling.

- [ ] **Step 3: Commit**

```bash
git add templates/student_career_compare.html
git commit -m "feat: rewrite compare page in Tailwind (from Bootstrap)"
```

---

## Task 4: Rewrite map page in Tailwind

**Files:**
- Rewrite: `templates/student_career_map.html`

- [ ] **Step 1: Write the new map template**

Rewrite `templates/student_career_map.html` with this content:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ban do nganh – EduMind AI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { margin:0; font-family:'Be Vietnam Pro',system-ui,sans-serif; overflow:hidden; background:#0f172a; }
    .ctrl-btn { font-size:12px; padding:4px 10px; border-radius:6px; background:#1e293b; color:#e2e8f0; border:1px solid #334155; cursor:pointer; }
    .ctrl-btn:hover { background:#334155; }
    .ctrl-input { font-size:12px; padding:4px 10px; border-radius:6px; background:#1e293b; color:#e2e8f0; border:1px solid #334155; outline:none; width:100%; }
    .ctrl-input::placeholder { color:#64748b; }
    .ctrl-input:focus { border-color:#3b82f6; }
    .group-tag { font-size:10px; padding:2px 8px; border-radius:4px; cursor:pointer; transition:opacity .15s; }
    .group-tag[data-active="0"] { opacity:0.35; }
  </style>
</head>
<body>

<div style="position:relative;height:100vh;overflow:hidden" id="mapApp">

  <!-- Controls (left) -->
  <div style="position:absolute;top:12px;left:12px;z-index:100;display:flex;flex-direction:column;gap:8px;width:220px">
    <div class="flex gap-2 items-center">
      <a href="{{ url_for('career.career_browse') }}" class="ctrl-btn"><i class="fas fa-arrow-left mr-1"></i>Nganh</a>
      <span class="text-white text-xs font-bold truncate">{{ student.name }}</span>
    </div>
    <input type="text" id="mapSearch" class="ctrl-input" placeholder="Tim nganh...">
    <div id="groupFilters" class="flex flex-wrap gap-1"></div>
    <label class="flex items-center gap-2 cursor-pointer">
      <input type="checkbox" id="filterFitOnly" class="w-3.5 h-3.5 rounded border-gray-600 bg-[#1e293b]">
      <span class="text-xs text-gray-300">Chi nganh phu hop (>50%)</span>
    </label>
    <div class="flex gap-1">
      <button class="ctrl-btn" onclick="zoomIn()">+</button>
      <button class="ctrl-btn" onclick="zoomOut()">-</button>
      <button class="ctrl-btn" onclick="resetZoom()"><i class="fas fa-undo text-[10px]"></i></button>
    </div>
  </div>

  <!-- Detail panel (right) -->
  <div id="detailPanel" style="position:absolute;right:0;top:0;bottom:0;width:280px;background:rgba(15,23,42,0.95);border-left:1px solid #334155;padding:16px;z-index:100;display:none;overflow-y:auto">
    <button onclick="closePanel()" class="absolute top-3 right-3 text-gray-400 hover:text-white"><i class="fas fa-times"></i></button>
    <h3 id="dpName" class="font-bold text-blue-400 text-sm mb-0.5"></h3>
    <div id="dpUniversity" class="text-[11px] text-gray-400 mb-2"></div>
    <div class="flex gap-1.5 mb-3">
      <span id="dpBlock" class="text-[10px] px-2 py-0.5 rounded bg-[#334155] text-gray-300"></span>
      <span id="dpGroup" class="text-[10px] px-2 py-0.5 rounded bg-[#1e293b] text-gray-400"></span>
    </div>
    <div class="mb-2">
      <span id="dpFit" class="text-xl font-bold text-green-400"></span>
      <span class="text-xs text-gray-500 ml-1">phu hop</span>
    </div>
    <div class="text-xs text-gray-400 mb-3">DC 2025: <strong id="dpScore" class="text-white"></strong></div>
    <div class="border-t border-[#334155] pt-2 mb-3">
      <div class="text-[10px] text-gray-500 uppercase tracking-wide mb-1.5">Top mon yeu cau</div>
      <div id="dpSubjects"></div>
    </div>
    <div class="flex flex-col gap-2">
      <button onclick="addToCompare()" class="ctrl-btn text-center"><i class="fas fa-plus mr-1"></i>So sanh</button>
      <a href="{{ url_for('career.career_browse') }}" class="ctrl-btn text-center"><i class="fas fa-list mr-1"></i>Xem tat ca</a>
    </div>
  </div>

  <svg id="mapSvg" width="100%" height="100%" style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%)">
    <g id="mapG"></g>
  </svg>
</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
const GROUP_COLORS={'Ky thuat':'#3b82f6','Cong nghe':'#60a5fa','Kinh te':'#f59e0b','Y duoc':'#10b981','Xa hoi':'#a78bfa','Nghe thuat':'#f43f5e','Khoa hoc':'#06b6d4','Nong lam':'#84cc16'};
const DEFAULT_COLOR='#94a3b8';
let simulation,svgEl,gEl,zoomBehavior,currentNode=null,allData=[];
let compareIds=new Set(JSON.parse(sessionStorage.getItem('compare_major_ids')||'[]'));

function cosineSim(a,b,subjects){
  let dot=0,nA=0,nB=0;
  subjects.forEach(k=>{dot+=(a[k]||0)*(b[k]||0);nA+=(a[k]||0)**2;nB+=(b[k]||0)**2;});
  return nA&&nB?dot/(Math.sqrt(nA)*Math.sqrt(nB)):0;
}

async function init(){
  const r=await fetch('/api/student/career/map-data');
  const data=await r.json();
  allData=data.majors;
  renderMap(allData);
  buildGroupFilters(allData);
}

function renderMap(majors){
  const subjects=[...new Set(majors.flatMap(m=>Object.keys(m.weight_vector)))];
  const nodesData=majors.map(m=>({...m}));
  const linksData=[];
  for(let i=0;i<nodesData.length;i++)
    for(let j=i+1;j<nodesData.length;j++){
      const sim=cosineSim(nodesData[i].weight_vector,nodesData[j].weight_vector,subjects);
      if(sim>0.7)linksData.push({source:nodesData[i].id,target:nodesData[j].id,strength:sim});
    }
  const width=document.getElementById('mapSvg').clientWidth;
  const height=document.getElementById('mapSvg').clientHeight;
  svgEl=d3.select('#mapSvg');gEl=d3.select('#mapG');gEl.selectAll('*').remove();
  zoomBehavior=d3.zoom().scaleExtent([0.2,4]).on('zoom',e=>gEl.attr('transform',e.transform));
  svgEl.call(zoomBehavior);
  const rScale=d3.scaleLinear().domain([15,30]).range([8,22]).clamp(true);
  simulation=d3.forceSimulation(nodesData)
    .force('link',d3.forceLink(linksData).id(d=>d.id).distance(80).strength(d=>d.strength*0.5))
    .force('charge',d3.forceManyBody().strength(-200))
    .force('center',d3.forceCenter(width/2,height/2))
    .force('collision',d3.forceCollide(d=>rScale(d.entry_score||20)+10));
  const link=gEl.append('g').selectAll('line').data(linksData).enter().append('line')
    .attr('stroke','#475569').attr('stroke-opacity',d=>d.strength*0.5).attr('stroke-width',d=>d.strength*2);
  const node=gEl.append('g').selectAll('g').data(nodesData).enter().append('g')
    .style('cursor','pointer')
    .call(d3.drag()
      .on('start',(e,d)=>{if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;})
      .on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y;})
      .on('end',(e,d)=>{if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null;}))
    .on('click',(e,d)=>showDetail(d));
  node.append('circle')
    .attr('r',d=>rScale(d.entry_score||20))
    .attr('fill',d=>GROUP_COLORS[d.major_group]||DEFAULT_COLOR)
    .attr('fill-opacity',0.85)
    .attr('stroke','#1e293b').attr('stroke-width',1.5);
  node.append('text')
    .text(d=>d.name.length>12?d.name.slice(0,12)+'…':d.name)
    .attr('text-anchor','middle').attr('dy','0.35em')
    .attr('font-size','8px').attr('fill','white').attr('pointer-events','none');
  simulation.on('tick',()=>{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform',d=>`translate(${d.x},${d.y})`);
  });
}

function showDetail(d){
  currentNode=d;
  document.getElementById('dpName').textContent=d.name;
  document.getElementById('dpUniversity').textContent=d.university;
  document.getElementById('dpBlock').textContent=d.admission_block||'—';
  document.getElementById('dpGroup').textContent=d.major_group||'—';
  document.getElementById('dpFit').textContent=Math.round(d.fit_pct)+'%';
  document.getElementById('dpScore').textContent=d.entry_score||'—';
  const subjDiv=document.getElementById('dpSubjects');subjDiv.innerHTML='';
  Object.entries(d.weight_vector).sort((a,b)=>b[1]-a[1]).slice(0,3).forEach(([s,w])=>{
    const el=document.createElement('div');el.className='text-xs text-gray-300 mb-1';
    el.innerHTML=`<span class="text-gray-500">${s}:</span> trong so ${(w*100).toFixed(0)}%`;
    subjDiv.appendChild(el);
  });
  document.getElementById('detailPanel').style.display='block';
}
function closePanel(){document.getElementById('detailPanel').style.display='none';currentNode=null;}

function addToCompare(){
  if(!currentNode)return;
  if(compareIds.size>=4){alert('Toi da 4 nganh');return;}
  compareIds.add(currentNode.id);
  sessionStorage.setItem('compare_major_ids',JSON.stringify([...compareIds]));
  alert('Da them "'+currentNode.name+'" vao danh sach so sanh ('+compareIds.size+'/4)');
}

function buildGroupFilters(majors){
  const groups=[...new Set(majors.map(m=>m.major_group).filter(Boolean))];
  const c=document.getElementById('groupFilters');c.innerHTML='';
  groups.forEach(g=>{
    const tag=document.createElement('span');
    tag.className='group-tag';tag.style.background=GROUP_COLORS[g]||DEFAULT_COLOR;tag.style.color='#fff';
    tag.textContent=g;tag.dataset.active='1';
    tag.onclick=()=>{tag.dataset.active=tag.dataset.active==='1'?'0':'1';applyFilters();};
    c.appendChild(tag);
  });
}

function applyFilters(){
  const hidden=new Set([...document.getElementById('groupFilters').querySelectorAll('[data-active="0"]')].map(b=>b.textContent));
  let filtered=allData;
  const q=document.getElementById('mapSearch').value.toLowerCase();
  if(q)filtered=filtered.filter(m=>(m.name+m.university).toLowerCase().includes(q));
  if(document.getElementById('filterFitOnly').checked)filtered=filtered.filter(m=>m.fit_pct>50);
  if(hidden.size>0)filtered=filtered.filter(m=>!hidden.has(m.major_group));
  if(simulation)simulation.stop();
  renderMap(filtered);
}

let searchTimer;
document.getElementById('mapSearch').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(applyFilters,400);});
document.getElementById('filterFitOnly').addEventListener('change',applyFilters);

function zoomIn(){svgEl.transition().duration(300).call(zoomBehavior.scaleBy,1.3);}
function zoomOut(){svgEl.transition().duration(300).call(zoomBehavior.scaleBy,0.7);}
function resetZoom(){svgEl.transition().duration(300).call(zoomBehavior.transform,d3.zoomIdentity);}

init();
</script>
</body>
</html>
```

- [ ] **Step 2: Test map page**

Open `http://localhost:5000/student/career/map` in browser.
Verify: D3 force graph renders, nodes draggable, click shows detail panel, group filters work, zoom controls work, Tailwind styling.

- [ ] **Step 3: Commit**

```bash
git add templates/student_career_map.html
git commit -m "feat: rewrite map page in Tailwind (from Bootstrap)"
```

---

## Task 5: Fix Vietnamese text encoding in templates

All templates above use ASCII-safe text (no diacritics) for reliability. This task adds back proper Vietnamese text.

**Files:**
- Modify: `templates/student_career_browse.html`
- Modify: `templates/student_career_compare.html`
- Modify: `templates/student_career_map.html`

- [ ] **Step 1: Fix Vietnamese in browse page**

Replace all ASCII-safe Vietnamese text with proper diacritics in `student_career_browse.html`:

Key replacements:
- "Phan tich nang luc" → "Phân tích năng lực"
- "Duyet tat ca nganh" → "Duyệt tất cả ngành"
- "Tim nganh hoac truong..." → "Tìm ngành hoặc trường..."
- "Tat ca truong" → "Tất cả trường"
- "Tat ca khoi" → "Tất cả khối"
- "Tat ca nhom nganh" → "Tất cả nhóm ngành"
- "Phu hop" → "Phù hợp"
- "Sap xep:" → "Sắp xếp:"
- "Phu hop nhat" → "Phù hợp nhất"
- "DC cao → thap" → "ĐC cao → thấp"
- "DC thap → cao" → "ĐC thấp → cao"
- "Ten A-Z" → "Tên A-Z"
- "Mo phong diem" → "Mô phỏng điểm"
- "So sanh" → "So sánh"
- "Khong co nganh nao phu hop voi bo loc hien tai." → "Không có ngành nào phù hợp với bộ lọc hiện tại."
- "Neu diem cua ban la..." → "Nếu điểm của bạn là..."
- "Dieu chinh diem du kien — danh sach nganh se cap nhat ngay" → "Điều chỉnh điểm dự kiến — danh sách ngành sẽ cập nhật ngay"
- "Reset ve diem that" → "Reset về điểm thật"
- "Dong" → "Đóng"
- "Da ghim" → "Đã ghim"
- "Ghim" → "Ghim"
- "Da ghim nganh" → "Đã ghim ngành"
- "Da bo ghim" → "Đã bỏ ghim"
- "Muc tieu" → "Mục tiêu"
- "Da dat lam nganh muc tieu" → "Đã đặt làm ngành mục tiêu"
- "Toi da 4 nganh" → "Tối đa 4 ngành"
- "Xu huong:" → "Xu hướng:"
- "Khoi:" → "Khối:"
- JS strings: "nganh" → "ngành"

- [ ] **Step 2: Fix Vietnamese in compare page**

Replace all ASCII-safe text in `student_career_compare.html`:
- "Duyet nganh" → "Duyệt ngành"
- "So sanh nganh" → "So sánh ngành"
- "Quay lai" → "Quay lại"
- "Them nganh (go de tim)..." → "Thêm ngành (gõ để tìm)..."
- "Radar so sanh mon hoc" → "Radar so sánh môn học"
- "Xu huong diem chuan" → "Xu hướng điểm chuẩn"
- "So sanh chi tiet" → "So sánh chi tiết"
- "Tieu chi" → "Tiêu chí"
- "% Phu hop" → "% Phù hợp"
- "DC 2025" → "ĐC 2025"
- "Khoi xet tuyen" → "Khối xét tuyển"
- "Xu huong DC" → "Xu hướng ĐC"
- "Yeu cau" → "Yêu cầu"
- "Diem cua ban" → "Điểm của bạn"
- "Diem chuan" → "Điểm chuẩn"
- "Toi da 4 nganh" → "Tối đa 4 ngành"

- [ ] **Step 3: Fix Vietnamese in map page**

Replace all ASCII-safe text in `student_career_map.html`:
- "Tim nganh..." → "Tìm ngành..."
- "Chi nganh phu hop (>50%)" → "Chỉ ngành phù hợp (>50%)"
- "phu hop" → "phù hợp"
- "DC 2025" → "ĐC 2025"
- "Top mon yeu cau" → "Top môn yêu cầu"
- "So sanh" → "So sánh"
- "Xem tat ca" → "Xem tất cả"
- "trong so" → "trọng số"
- "Da them" → "Đã thêm"
- "vao danh sach so sanh" → "vào danh sách so sánh"
- "Toi da 4 nganh" → "Tối đa 4 ngành"
- "Nganh" → "Ngành"
- GROUP_COLORS keys: `'Ky thuat'` → `'Kỹ thuật'`, `'Cong nghe'` → `'Công nghệ'`, `'Kinh te'` → `'Kinh tế'`, `'Y duoc'` → `'Y dược'`, `'Xa hoi'` → `'Xã hội'`, `'Nghe thuat'` → `'Nghệ thuật'`, `'Khoa hoc'` → `'Khoa học'`, `'Nong lam'` → `'Nông lâm'`

- [ ] **Step 4: Commit**

```bash
git add templates/student_career_browse.html templates/student_career_compare.html templates/student_career_map.html
git commit -m "fix: restore Vietnamese diacritics in all career templates"
```

---

## Task 6: Final verification

- [ ] **Step 1: Verify all pages load and function correctly**

Start the dev server and test each page:

```bash
python app.py
```

Test checklist:
1. `http://localhost:5000/student/career` — main page, navigation cards visible
2. `http://localhost:5000/student/career/browse` — grid layout, mini radar, pin/target, sparklines, all filters, sort pills, simulator modal, compare flow
3. `http://localhost:5000/student/career/compare?major_ids=1,2` — radar overlay, line chart, versus table, add/remove majors
4. `http://localhost:5000/student/career/map` — D3 force graph, node interaction, detail panel, group filters, zoom
5. `http://localhost:5000/admin/majors` — admin table (should still work, was already Tailwind)

- [ ] **Step 2: Verify data integrity**

```bash
python -c "
from app import app
from models import db, UniversityMajor, MajorSubjectWeight, MajorEntryScore
with app.app_context():
    m = UniversityMajor.query.count()
    w = MajorSubjectWeight.query.count()
    e = MajorEntryScore.query.count()
    print(f'Majors: {m}, Weights: {w}, EntryScores: {e}')
    assert m > 100
    assert w > 300
    assert e > 300
    print('Data OK')
"
```

- [ ] **Step 3: Verify no Bootstrap references remain**

```bash
grep -r "bootstrap" templates/student_career_browse.html templates/student_career_compare.html templates/student_career_map.html || echo "No Bootstrap references - OK"
```

Expected: "No Bootstrap references - OK"
