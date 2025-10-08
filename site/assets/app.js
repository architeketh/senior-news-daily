/* Minimal enhancer to:
   - Build category chips like SND
   - Filter cards by chip
   - Build a compact horizontal bar chart of category counts (tight spacing)
   - Update summary line + last updated
*/

const $ = (q, el=document) => el.querySelector(q);
const $$ = (q, el=document) => Array.from(el.querySelectorAll(q));

const cardsEl = $('#cards');
const chipRow = $('#chips');
const chartEl = $('#categoryChart');
const summaryLine = $('#summaryLine');
const updatedLine = $('#lastUpdated');

function getCards(){
  return $$('.card', cardsEl).map(c => ({
    el: c,
    category: (c.getAttribute('data-category')||'General').trim(),
    date: c.getAttribute('data-date')||'',
    source: c.getAttribute('data-source')||'',
  }));
}

function countsByCategory(cards){
  const map = new Map();
  cards.forEach(c => map.set(c.category, (map.get(c.category)||0)+1));
  // sort desc count
  return [...map.entries()].sort((a,b)=>b[1]-a[1]);
}

function renderChips(counts){
  chipRow.innerHTML = '';
  const total = counts.reduce((s, [,n])=>s+n, 0);
  const mk = (label, count, key) => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.dataset.key = key;
    b.textContent = key==='ALL' ? `All ${total}` : `${label} ${count}`;
    b.onclick = () => {
      // toggle single-select like SND
      $$('.chip', chipRow).forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      applyFilter(key==='ALL'?null:key);
    };
    return b;
  };
  chipRow.appendChild(mk('All', total, 'ALL'));
  counts.forEach(([k,n]) => chipRow.appendChild(mk(k, n, k)));
  // default to All
  $('.chip', chipRow)?.classList.add('active');
}

let chart;
function renderChart(counts){
  if(!chartEl) return;
  const labels = counts.map(([k])=>k);
  const data = counts.map(([,n])=>n);
  if(chart){ chart.destroy(); }
  chart = new Chart(chartEl.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: 'Articles', data }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display:false },
        tooltip: { mode:'nearest', intersect:false }
      },
      scales: {
        x: { beginAtZero:true, ticks:{ precision:0 }, grid:{ display:false }},
        y: {
          grid:{ display:false },
          ticks: { autoSkip:false, maxTicksLimit: 20 }
        }
      },
      elements: { bar: { borderRadius: 6, borderSkipped: false } },
      layout: { padding: { top: 0, bottom: 0 } }, // tight, like SND
    }
  });
}

function applyFilter(category){
  const cards = getCards();
  cards.forEach(c => {
    const show = !category || c.category === category;
    c.el.style.display = show ? '' : 'none';
  });
}

function updateSummary(cards){
  const counts = countsByCategory(cards);
  const parts = counts.slice(0,5).map(([k,n])=>`${k} (${n})`);
  summaryLine.textContent = parts.length
    ? `Today’s highlights by category — ${parts.join(', ')}.`
    : `No articles found.`;
  const now = new Date();
  updatedLine.textContent = now.toLocaleString(undefined, {
    month:'short', day:'2-digit', year:'numeric',
    hour:'2-digit', minute:'2-digit'
  });
}

function init(){
  // If you also have data/articles.json, you can fetch and render cards here.
  // For now, we scan what's already in DOM (builder output or sample).
  const cards = getCards();
  const counts = countsByCategory(cards);
  renderChips(counts);
  renderChart(counts);
  updateSummary(cards);

  // Save/unsave UX (like SND’s star)
  $$('.save').forEach(btn=>{
    btn.addEventListener('click', e=>{
      e.preventDefault();
      btn.classList.toggle('active');
    });
  });
}

document.addEventListener('DOMContentLoaded', init);
