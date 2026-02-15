/* HayDay 🍀 Image Generator (MVP)
   - Supports qty math and k/m or x multiplier pricing
   - Pulls items from /api/wiki-products when available
*/
;(async () => {
  // ---------- Config ----------
  const ITEM_IMAGE_BASE = window.HD_ITEM_IMAGE_BASE || "/static/img/hd";
  const PLACEHOLDER = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
       <rect width="100%" height="100%" rx="16" ry="16" fill="#0d1713"/>
       <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
             fill="#78f0a7" font-size="18" font-family="Verdana">No Image</text>
     </svg>`
  );

  // ---------- Data (filled from wiki/endpoint) ----------
  const IMG_URL = new Map();   // name -> absolute image URL
  const MAX_PRICE = new Map(); // name -> max price

  // Abbreviations (optional)
  const ABBR = new Map([
    ['tnt','tnt barrel'],
    ['dyn','dynamite'],
    ['vice','vanilla ice cream'],
    ['gbar','gold bar'],
    ['sbar','silver bar'],
    ['pbar','platinum bar']
  ]);

  const state = {
    items: new Map(), // name => { qty, porm }
    cols: 6,
    search: ''
  };

  // ---------- Helpers ----------
  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));

  function toTitleSnakeCase(s){
    s = String(s || '').trim().replaceAll('_',' ');
    return s.split(/\s+/).map(w => w[0]?.toUpperCase() + w.slice(1).toLowerCase()).join('_');
  }
  function fromAbbr(s){
    const key = String(s || '').trim().toLowerCase();
    return ABBR.get(key) ?? s;
  }
  function parseQty(expr){
    if(!expr || !String(expr).trim()) return 0;
    try { return Math.floor(math.evaluate(String(expr))); }
    catch { return NaN; }
  }
  function imageFor(name){
    if (IMG_URL.has(name)) return IMG_URL.get(name);
    return `${ITEM_IMAGE_BASE}/${name}.png`;
  }
  function computeItemTotal(name, qty, porm){
    const human = name.replaceAll('_',' ');
    const max = MAX_PRICE.get(name) ?? null;
    porm = (porm ?? '').trim();

    let priceExpr;
    if(!porm){
      if(!max) return { total: NaN, eq: 'NaN', err: `${human} has no max price.` };
      priceExpr = `${qty}*(${max}*(1))`;
    } else if (porm.endsWith('x')){
      if(!max) return { total: NaN, eq: 'NaN', err: `${human} has no max price.` };
      const mult = porm.slice(0,-1) || '1';
      priceExpr = `${qty}*(${max}*(${mult}))`;
    } else if (/k$/i.test(porm)){
      priceExpr = `${qty}*((${porm.slice(0,-1)})*10^3)`;
    } else if (/m$/i.test(porm)){
      priceExpr = `${qty}*((${porm.slice(0,-1)})*10^6)`;
    } else {
      priceExpr = `${qty}*(${porm})`;
    }
    try { return { total: math.evaluate(priceExpr), eq: priceExpr }; }
    catch (e){ return { total: NaN, eq: priceExpr, err: `${human} has invalid price/multiplier.` }; }
  }

  function save(){
    localStorage.setItem('hd_builder_v1', JSON.stringify({
      cols: state.cols,
      items: Array.from(state.items.entries())
    }));
  }
  function load(){
    const raw = localStorage.getItem('hd_builder_v1');
    if(!raw) return;
    try{
      const data = JSON.parse(raw);
      state.cols = data.cols ?? 6;
      state.items = new Map(data.items ?? []);
    }catch{}
  }

  // ---------- UI nodes ----------
  const grid = $('#grid');
  const cols = $('#cols');
  const colsVal = $('#colsVal');
  const search = $('#search');
  const name = $('#name');
  const qty = $('#qty');
  const price = $('#price');
  const submit = $('#submit');
  const removeBtn = $('#remove');
  const totalEl = $('#totalVal');
  const bottomNote = $('#bottomNote');

  // ---------- Render ----------
  function render(){
    $('#shot').style.setProperty('--cols', String(state.cols));
    colsVal.textContent = String(state.cols);

    const q = state.search.toLowerCase();
    const items = Array.from(state.items.entries())
      .filter(([n]) => n.replaceAll('_',' ').toLowerCase().includes(q));

    grid.innerHTML = '';
    let grand = 0;

    for (const [n, item] of items){
      const card = document.querySelector('#card-tpl').content.firstElementChild.cloneNode(true);
      const img = card.querySelector('img');
      const nm = card.querySelector('.name');
      const qIn = card.querySelector('.qty');
      const pIn = card.querySelector('.porm');
      const sum = card.querySelector('.sum');

      img.src = imageFor(n);
      img.onerror = () => { img.src = PLACEHOLDER; };
      img.alt = n.replaceAll('_',' ');
      nm.textContent = n.replaceAll('_',' ');
      qIn.value = item.qty;
      pIn.value = item.porm ?? '';

      function recalc(){
        const { total, err } = computeItemTotal(n, Number(qIn.value||0), pIn.value);
        if(Number.isFinite(total)){
          sum.textContent = Number(total).toLocaleString();
          sum.title = 'Item total';
          sum.classList.remove('error');
          // recompute grand:
          const arr = Array.from(state.items.entries());
          const newTotal = arr.reduce((acc, [name, it]) => {
            const r = computeItemTotal(name, (name===n? Number(qIn.value||0):it.qty), (name===n? pIn.value:it.porm));
            return acc + (Number.isFinite(r.total) ? Number(r.total) : 0);
          }, 0);
          totalEl.textContent = newTotal.toLocaleString();
        }else{
          sum.textContent = '—';
          sum.title = err || 'Invalid';
          sum.classList.add('error');
        }
        // persist live
        const current = state.items.get(n);
        current.qty = Number(qIn.value||0);
        current.porm = pIn.value;
        state.items.set(n, current);
        save();
      }

      qIn.addEventListener('input', recalc);
      pIn.addEventListener('input', recalc);

      // initial calc
      const c = computeItemTotal(n, item.qty, item.porm);
      if(Number.isFinite(c.total)){
        sum.textContent = Number(c.total).toLocaleString();
        grand += Number(c.total);
      } else {
        sum.textContent = '—';
        sum.title = c.err || 'Invalid';
        sum.classList.add('error');
      }

      grid.appendChild(card);
    }
    totalEl.textContent = Number(grand).toLocaleString();
  }

  function suggest(){
    const list = $('#suggestions');
    const q = (name.value || '').trim().toLowerCase();
    const pool = new Set([...MAX_PRICE.keys()]);
    for (const k of state.items.keys()) pool.add(k);

    const arr = [...pool]
      .map(n => n.replaceAll('_',' '))
      .filter(n => n.toLowerCase().includes(q))
      .slice(0, 20);

    list.innerHTML = '';
    for (const n of arr){
      const opt = document.createElement('option');
      opt.value = n;
      list.appendChild(opt);
    }
  }

  // ---------- Events ----------
  cols.addEventListener('input', (e)=>{ state.cols = Number(e.target.value); save(); render(); });
  search.addEventListener('input', (e)=>{ state.search = e.target.value; render(); });
  name.addEventListener('input', suggest);

  submit.addEventListener('click', ()=>{
    const raw = fromAbbr(name.value);
    const formatted = toTitleSnakeCase(raw);
    if(!formatted) return;

    const q = parseQty(qty.value);
    if(!Number.isFinite(q) || q <= 0) return;

    const p = price.value.trim();
    state.items.set(formatted, { qty: q, porm: p || '' });
    name.value = ''; qty.value = '1'; price.value = '';
    save(); render(); suggest();
  });

  removeBtn.addEventListener('click', ()=>{
    const raw = fromAbbr(name.value);
    const formatted = toTitleSnakeCase(raw);
    if(!formatted) return;
    state.items.delete(formatted);
    name.value=''; save(); render(); suggest();
  });

  $('#copyImg').addEventListener('click', async ()=>{
    try{
      const dataUrl = await htmlToImage.toPng($('#shot'), { cacheBust: true, pixelRatio: 2 });
      const blob = await (await fetch(dataUrl)).blob();
      await navigator.clipboard.write([ new ClipboardItem({ [blob.type]: blob }) ]);
      alert('✅ Copied image to clipboard.');
    }catch{
      try{
        const link = document.createElement('a');
        link.download = 'hayday.png';
        link.href = await htmlToImage.toPng($('#shot'), { cacheBust: true, pixelRatio: 2 });
        link.click();
      }catch{ alert('Copy failed.'); }
    }
  });

  $('#copyText').addEventListener('click', ()=>{
    const parts = [];
    for (const [n, item] of state.items){
      const r = computeItemTotal(n, item.qty, item.porm);
      const price = Number.isFinite(r.total) ? Number(r.total).toLocaleString() : '—';
      parts.push(`${item.qty} ${n.replaceAll('_',' ')} (${price})`);
    }
    navigator.clipboard.writeText(parts.join(', '));
    alert('✅ Copied text list.');
  });

  bottomNote.addEventListener('input', ()=>{
    localStorage.setItem('hd_builder_note', bottomNote.innerText);
  });

  // ---------- Data load ----------
  async function fetchItems(){
    const url = window.HD_ITEMS_ENDPOINT || "/api/wiki-products";
    try{
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return; // 202 while building is fine
      const data = await res.json();
      for (const it of (data.items || data)){
        const key = it.key || toTitleSnakeCase(it.name);
        if (it.max_price != null) MAX_PRICE.set(key, Number(it.max_price));
        if (it.thumb) IMG_URL.set(key, it.thumb);
      }
    }catch(e){ console.warn("Wiki items fetch failed:", e); }
  }

  // ---------- Init ----------
  load();
  const savedNote = localStorage.getItem('hd_builder_note');
  if (savedNote) bottomNote.innerText = savedNote;

  await fetchItems();
  $('#cols').value = state.cols; colsVal.textContent = String(state.cols);
  render();
  suggest();
})();
