/* SurveySleuth search page, layout B ("Briefing first"): a start page, then the Search results on the
   left and the map on the right. The address and distance stay in the page link. */
(() => {
  const root = document.getElementById('app');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ft = n => n >= 5280 ? (n / 5280).toFixed(2) + ' mi' : Math.round(n).toLocaleString('en-US') + ' ft';
  const mi = r => ({ 0.25: '¼ mi', 0.5: '½ mi', 1: '1 mi', 2: '2 mi' })[r];
  const KINDS = { 'Elevation Certificate': 'k-cert', 'Survey': 'k-sv', 'Metes-and-Bounds Description': 'k-mb',
    'Floor Plan': 'k-fp', 'Field Notes': 'k-fn', 'Natural Ground Letter': 'k-ng' };
  const CERT_LIKE = ['Elevation Certificate', 'Natural Ground Letter'];
  const kindTag = k => `<span class="kind ${KINDS[k] || ''}">${esc(k)}</span>`;
  // Pins and ranks are colored by Record kind: certificate (or Natural Ground Letter), Survey folder Records, or both
  const mix = kinds => {
    const cert = kinds.some(k => CERT_LIKE.includes(k)), other = kinds.some(k => !CERT_LIKE.includes(k));
    return cert && other ? 'mix-both' : cert ? 'mix-cert' : 'mix-sv';
  };
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  let start, state, map, layer, fit, streetsFile;  // fit: the distance circle's bounds; streetsFile: the offline streets tiles

  // ------------------------------------------------------------ the page link
  function fromURL() {
    const p = new URLSearchParams(location.search);
    return { id: p.get('id'), q: p.get('q'), r: parseFloat(p.get('r')) || 0.5 };
  }
  function toURL(s) {
    const p = new URLSearchParams();
    if (s.id) p.set('id', s.id); else if (s.q) p.set('q', s.q);
    p.set('r', s.r);
    history.pushState(null, '', '?' + p);
  }

  // One line of the checked Facts on the nearest Record
  function factLine(rec) {
    const ok = {};
    rec.facts.forEach(f => { if (f.ok) ok[f.label] = f.value; });
    return [
      ok['Flood zone'] && `Zone ${ok['Flood zone']}`,
      ok['BFE'] && `BFE ${ok['BFE']} ft`,
      ok['Top of bottom floor'] && `floor ${ok['Top of bottom floor']} ft`,
      ok['Lowest adjacent grade'] && `ground ${ok['Lowest adjacent grade']} ft`,
      ok['Basis'],
      rec.kind !== 'Elevation Certificate' && ok['Lot and block'],
      ok['Flood note'],
      ok['Natural ground'] && `natural ground ${ok['Natural ground']} ft`,
      rec.date && new Date(rec.date + 'T12:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' }),
    ].filter(Boolean).join(' · ');
  }

  const distanceOptions = r => [0.25, 0.5, 1, 2].map(x => `<option value="${x}" ${x === r ? 'selected' : ''}>within ${mi(x)}</option>`).join('');
  const form = cls => `
    <form class="${cls}" autocomplete="off">
      <input name="q" list="ss-addresses" placeholder="Address or Parcel ID in Galveston County" aria-label="Address or Parcel ID">
      <select name="r" aria-label="Distance">${distanceOptions(state.r)}</select>
      <button type="submit">Search</button>
    </form>`;

  // ------------------------------------------------------------ start page
  function home() {
    if (map) { map.remove(); map = layer = fit = null; }
    const c = start.counts;
    const kinds = Object.entries(c.kinds).map(([k, n]) => plural(n, k)).join(', ');
    root.innerHTML = `
      <section class="home"><div class="hero">
        <div class="brand big">Survey<b>Sleuth</b></div>
        <h1>What has the Firm already done near this property?</h1>
        ${form('hero-form')}
        <p class="stats">${plural(c.jobs, 'Job')} · ${plural(c.records, 'Record')} (${esc(kinds)})</p>
        ${start.addresses.length ? `<div class="try"><span>Try a test address:</span>
          ${start.addresses.map(a => `<button data-id="${esc(a.id)}">${esc(a.address.split(',')[0])}</button>`).join('')}</div>` : ''}
      </div></section>`;
    wireForm(root.querySelector('form'));
    root.querySelectorAll('[data-id]').forEach(b => b.onclick = () => go({ id: b.dataset.id, r: state.r }));
    root.querySelector('input').focus();
  }

  function wireForm(f) {
    f.onsubmit = e => {
      e.preventDefault();
      const text = f.q.value.trim();
      if (!text) return;
      const a = start.addresses.find(a => a.address.toLowerCase() === text.toLowerCase());
      go(a ? { id: a.id, r: +f.r.value } : { q: text, r: +f.r.value });
    };
  }

  function go(s) { state = s; toURL(s); run(); }

  // ------------------------------------------------------------ after a search
  async function run() {
    if (!map) {
      root.innerHTML = `
        <div class="vb">
          <header class="top"><div class="brand">Survey<b>Sleuth</b></div>${form('search')}</header>
          <div class="body"><article class="doc"></article><aside class="side">
            <div class="split" role="separator" aria-orientation="vertical" aria-label="Width of the side panel" tabindex="0"></div>
            <nav class="tabs"><button data-tab="map" class="on">Map</button><button data-tab="record" disabled>Record</button></nav>
            <div class="pane pane-map"><div class="map"></div><div class="legend"><span><i class="mix-cert"></i>Certificate</span><span><i class="mix-sv"></i>Survey</span><span><i class="mix-both"></i>Both</span></div><div class="sources"></div></div>
            <div class="pane pane-record" hidden></div>
          </aside></div>
        </div>`;
      root.querySelector('.brand').onclick = () => { history.pushState(null, '', location.pathname); state = fromURL(); home(); };
      wireForm(root.querySelector('form'));
      root.querySelectorAll('.tabs button').forEach(b => b.onclick = () => showTab(b.dataset.tab));
      // The divider before the side panel: drag it, or Tab to it and use the arrow keys. The CSS keeps both columns
      // at least at their minimum widths. A drag or a key keeps the width shown in this browser; a click keeps nothing.
      const body = root.querySelector('.body'), side = root.querySelector('.side'), split = root.querySelector('.split');
      const share = () => split.setAttribute('aria-valuenow', Math.round(100 * side.offsetWidth / body.clientWidth));
      const sizeSide = w => { body.style.setProperty('--side', Math.round(w) + 'px'); share(); };
      const keep = () => { try { localStorage.setItem('surveysleuth.side', side.offsetWidth); } catch {} };
      try { const w = parseInt(localStorage.getItem('surveysleuth.side')); if (w > 0) sizeSide(w); } catch {}
      split.onfocus = share;
      split.onpointerdown = e => { e.preventDefault(); split.setPointerCapture(e.pointerId); };
      split.onpointermove = e => {
        if (split.hasPointerCapture(e.pointerId)) { sizeSide(body.getBoundingClientRect().right - e.clientX); keep(); }
      };
      split.onkeydown = e => {
        const d = { ArrowLeft: 20, ArrowRight: -20 }[e.key];
        if (d) { e.preventDefault(); sizeSide(side.offsetWidth + d); keep(); }
      };
      // The map stays in the tiles' box, Galveston County. From zoom 11 up the box fills the map: no blank edges.
      map = L.map(root.querySelector('.map'), { minZoom: 11, maxZoom: 18, maxBounds: start.map.box, maxBoundsViscosity: 1 })
        .setView([29.35, -94.9], 11);  // a view first: Leaflet skips invalidateSize until it has one
      // A page loaded in a hidden or minimized window lays out late, and the divider moves: refit when the map's box changes size
      // (and skip a hidden map, as when the Record tab is open: an empty box would zoom it all the way in)
      const box = root.querySelector('.map');
      new ResizeObserver(() => {
        if (!map || !box.clientWidth || !box.clientHeight) return;
        map.invalidateSize();
        if (fit) map.fitBounds(fit, { padding: [20, 20], animate: false });
      }).observe(box);
      const base = baseLayers();
      base.Streets.addTo(map);
      if (base.Aerial) L.control.layers(base).addTo(map);
      L.control.scale({ imperial: true, metric: false }).addTo(map);
    }
    const doc = root.querySelector('.doc');
    showTab('map');
    doc.innerHTML = '<p class="muted">Searching…</p>';
    const r = await fetch('/api/search?' + new URLSearchParams(state.id ? { id: state.id, r: state.r } : { q: state.q, r: state.r }));
    const res = await r.json();
    if (!r.ok) { doc.innerHTML = `<p class="error">${esc(res.error)}</p>`; return; }
    render(res);
  }

  // Streets and aerial: the offline tiles the app serves, or live tiles from the internet (the app's --live-map setting)
  function baseLayers() {
    const live = start.map.live;
    const layers = { Streets: live
      ? L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' })
      : protomapsL.leafletLayer({ url: streetsFile, flavor: 'light', lang: 'en' }) };  // drawn from zoom 15 data above 15
    if (start.map.aerial) layers.Aerial = L.tileLayer(live
      ? 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}'
      : '/tiles/USGSImageryOnly/{z}/{y}/{x}', { maxNativeZoom: 16, attribution: 'Imagery: USDA, USGS The National Map: Orthoimagery' });
    return layers;
  }

  // The Search summary's [n] citations, as links to Source n
  const cited = text => esc(text).replace(/\[(\d+)\]/g, (_, n) => `<a href="#" class="cite" data-n="${n}">${n}</a>`);

  function render(res) {
    const q = res.query, s = res.summary, doc = root.querySelector('.doc'), f = root.querySelector('form');
    f.q.value = q.label;
    f.r.value = String(q.distance_mi);
    doc.innerHTML = `
      <p class="kicker">Search summary · within ${mi(q.distance_mi)}</p>
      <h1>${esc(q.label)}</h1>
      <p class="meta">${esc([plural(res.counts.jobs, 'Job'), plural(res.counts.records, 'Record'),
        res.parcel && `Parcel ${res.parcel.id}`,
        res.fema.zone && `FEMA today: Zone ${res.fema.zone}`,
      ].filter(Boolean).join(' · '))}</p>
      <div class="advice"><h3>Before you quote</h3><p>${cited(s.advice)}</p></div>
      ${s.findings.map(x => `<section class="finding"><h3>${esc(x.heading)}</h3><p>${cited(x.text)}</p></section>`).join('')}
      ${res.plats.length ? `<h2>Recorded Plats <small>holding this address, newest first</small></h2><table>
        <thead><tr><th>Volume, page</th><th>Subdivision</th><th>Recorded</th></tr></thead>
        <tbody>${res.plats.map(p => `
          <tr data-plat="${esc(p.id)}"><td><b>Vol. ${esc(p.volume)}, p. ${esc(p.page)}</b></td>
            <td>${esc(p.name || 'Name not read')}${p.kind === 'replat' ? ' <span class="muted small">(replat)</span>' : ''}</td><td>${esc(recorded(p.date))}</td></tr>`).join('')}</tbody></table>` : ''}
      <h2>Search results <small>${res.jobs.length ? 'nearest first' : ''}</small></h2>
      ${res.jobs.length ? `<table>
        <thead><tr><th></th><th>Job</th><th>Distance</th><th>Address</th><th>Records</th><th>On our Record</th></tr></thead>
        <tbody>${res.jobs.map(j => `
          <tr data-job="${esc(j.job)}">
            <td><span class="rank ${mix(j.kinds)}">${j.rank}</span></td>
            <td><b>${esc(j.job)}</b></td>
            <td class="num">${ft(j.distance_ft)}</td>
            <td>${esc(j.address || '')}${j.flags.map(f => `<div class="flag">⚑ ${esc(f)}</div>`).join('')}</td>
            <td>${j.kinds.map(kindTag).join(' ')}<div class="muted small">${plural(j.records.length, 'Record')}</div>
              ${j.records.map(r => `<div class="muted small">${j.records.length > 1 ? esc(fileName(r)) + ': ' : ''}${esc(r.location ? r.location.found_by : 'not located')}</div>`).join('')}</td>
            <td class="small">${esc(factLine(j.records[0]))}</td>
          </tr>
          <tr class="detail" data-for="${esc(j.job)}" hidden><td></td><td colspan="5"><div class="recs">${j.records.map(recordButton).join('')}</div></td></tr>`).join('')}</tbody></table>`
        : noJobs(res)}`;
    const widen = doc.querySelector('.widen');
    if (widen) widen.onclick = () => go({ ...state, r: 2 });
    const records = Object.fromEntries(res.jobs.flatMap(j => j.records.map(rec => [rec.id, rec])));
    const tab = root.querySelector('.tabs [data-tab="record"]');  // a new search closes the last search's Record
    tab.disabled = true;
    tab.textContent = 'Record';
    root.querySelector('.pane-record').innerHTML = '';
    doc.querySelectorAll('tr[data-job]').forEach(tr => tr.onclick = () => toggleRow(tr.dataset.job));
    doc.querySelectorAll('.rec').forEach(b => b.onclick = () => openRecord(records[b.dataset.rec]));
    const plats = Object.fromEntries(res.plats.map(p => [p.id, p]));
    doc.querySelectorAll('tr[data-plat]').forEach(tr => tr.onclick = () => openPlat(plats[tr.dataset.plat]));
    const list = root.querySelector('.sources');
    list.innerHTML = `<h3>Sources</h3><ol>${s.sources.map(x => `
      <li data-n="${x.n}"><span class="n">${x.n}</span><div>${x.record
        ? `${kindTag(x.kind)} <b>${esc(fileName({ id: x.record }))}</b><span>Job ${esc(x.job)} · ${esc(when(x.date))}</span>`
        : `<span class="kind k-auth">${esc(x.source)}</span> <b>${esc(x.label)}</b>${x.parcels ? `<span>${esc(x.parcels.join(', '))}</span>` : ''}`}</div></li>`).join('')}</ol>`;
    // A citation lights up its finding and its Source, then opens the Record, or a popup on the map
    const openSource = (n, finding) => {
      const x = s.sources.find(x => x.n === n);
      doc.querySelectorAll('.advice, .finding').forEach(el => el.classList.toggle('active', el === finding));
      list.querySelectorAll('li').forEach(li => li.classList.toggle('on', +li.dataset.n === n));
      if (x.record) return openRecord(records[x.record]);
      if (x.plat) return openPlat(plats[x.plat]);
      showTab('map');
      L.popup({ maxWidth: 320 }).setLatLng(x.source === 'NGS' ? [res.ngs.lat, res.ngs.lon] : q.point)
        .setContent(authority(x, res)).openOn(map);
    };
    doc.querySelectorAll('.cite').forEach(a => a.onclick = e => { e.preventDefault(); openSource(+a.dataset.n, a.closest('.advice, .finding')); });
    list.querySelectorAll('li').forEach(li => li.onclick = () => openSource(+li.dataset.n, null));
    draw(res);
  }

  // The popup for a FEMA, NGS or GCAD Source: what it says at the address (or, for a split parcel, its pieces today)
  function authority(x, res) {
    const head = `<b>${esc(x.label)}</b><br>`, f = res.fema, b = res.ngs, p = res.parcel;
    const body = x.parcels ? x.parcels.map(esc).join('<br>')
      : x.source === 'FEMA' ? (f.zone ? `Zone ${esc(f.zone)}${f.bfe != null ? ` · BFE ${f.bfe} ft` : ''}` : 'No flood zone at this point') +
        (f.panel ? `<br>FIRM panel ${esc(f.panel)}${f.panel_date ? `, effective ${esc(when(f.panel_date))}` : ''}` : '')
      : x.source === 'NGS' ? `${esc(b.id)} “${esc(b.name)}”<br>${b.height_ft.toFixed(2)} ft · ${ft(b.distance_ft)} from the address`
      : p ? `Parcel ${esc(p.id)}<br>${esc(p.legal)}<br>${esc(p.acres)} acres${p.situs ? ' · ' + esc(p.situs) : ''}` : 'No parcel holds this point';
    return `${head}${body}<br><small>Saved copy, read with no network</small>`;
  }

  // ------------------------------------------------------------ a Job's Records and the Record viewer
  const fileName = r => r.id.split('/').pop();
  const when = iso => iso ? new Date(iso + 'T12:00').toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'no date';
  const recorded = d => /^\d{4}-\d{2}-\d{2}$/.test(d || '') ? when(d) : (d || 'no date');  // a Recorded Plat's date can be a year only
  const recordButton = r => `
    <button class="rec" data-rec="${esc(r.id)}">
      ${r.photo ? `<img loading="lazy" src="/photo?id=${encodeURIComponent(r.id)}" alt="Building photo">` : `<span class="rec-icon">${esc(r.kind[0])}</span>`}
      <span class="rec-text">${kindTag(r.kind)} <b>${esc(fileName(r))}</b>
        <small>${esc(when(r.date))} · ${esc(plural(r.pages || 1, 'page'))}</small><small>${esc(factLine(r))}</small></span>
    </button>`;

  function toggleRow(job) {
    const detail = root.querySelector(`tr.detail[data-for="${CSS.escape(job)}"]`);
    if (detail) detail.hidden = !detail.hidden;
  }

  function showTab(name) {
    root.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
    root.querySelector('.pane-map').hidden = name !== 'map';
    root.querySelector('.pane-record').hidden = name !== 'record';
  }

  function openRecord(rec) {
    const tab = root.querySelector('.tabs [data-tab="record"]');
    tab.disabled = false;
    tab.textContent = `Record: ${fileName(rec)}`;
    let page = 1;
    const pane = root.querySelector('.pane-record'), id = encodeURIComponent(rec.id), plat = rec.plat && `/plat?id=${encodeURIComponent(rec.plat)}`;
    const show = () => {
      pane.innerHTML = `
        <div class="viewer">
          <div class="viewer-bar">${kindTag(rec.kind)}
            <div class="viewer-title"><b>${esc(fileName(rec))}</b><span>Job ${esc(rec.job)} · ${esc(when(rec.date))}</span></div>
            <nav class="viewer-pages">${Array.from({ length: rec.pages || 1 }, (_, i) => i + 1).map(n =>
              `<button data-p="${n}" class="${n === page ? 'on' : ''}" title="Page ${n}${n === rec.photo_page ? ': building photo' : ''}">${n}${n === rec.photo_page ? ' 📷' : ''}</button>`).join('')}${rec.plat ? `
              <button data-p="plat" class="${page === 'plat' ? 'on' : ''}" title="The Recorded Plat this Survey cites (county Map Records)">Recorded Plat</button>` : ''}</nav>
            <a class="viewer-open" href="/pdf?id=${id}" target="_blank" rel="noopener">Open PDF ↗</a>${plat ? `
            <a class="viewer-open" href="${plat}" target="_blank" rel="noopener" title="The Recorded Plat this Survey cites">Open Recorded Plat ↗</a>` : ''}
          </div>
          <div class="viewer-body">
            <div class="viewer-page">${page === 'plat'
              ? `<img src="${plat}" alt="Recorded Plat ${esc(rec.plat)}, cited by ${esc(fileName(rec))}">`
              : `<img src="/page?id=${id}&n=${page}" alt="${esc(fileName(rec))}, page ${page}">`}</div>
            <aside class="viewer-side">
              <dl class="viewer-facts">${rec.facts.map(f => `
                <div class="fact ${f.ok ? '' : 'bad'}"><dt>${esc(f.label)} <small>page ${esc(f.page)} · ${esc(f.read_by)}</small></dt>
                  <dd>${esc(f.value)}${f.ok ? '' : `<em>⚠ ${esc(f.note || 'Failed its check.')} Kept for review; not used in the summary.</em>`}</dd></div>`).join('')}
              </dl>
              <p class="muted small">${esc(rec.location ? 'Location: ' + rec.location.found_by : 'Not located')}</p>
            </aside>
          </div>
        </div>`;
      pane.querySelectorAll('.viewer-pages button').forEach(b => b.onclick = () => { page = b.dataset.p === 'plat' ? 'plat' : +b.dataset.p; show(); });
    };
    show();
    showTab('record');
  }

  // A Recorded Plat (an Authoritative source, not a Record) in the same viewer
  function openPlat(p) {
    const tab = root.querySelector('.tabs [data-tab="record"]'), src = `/plat?id=${encodeURIComponent(p.id)}`;
    tab.disabled = false;
    tab.textContent = `Recorded Plat: Vol. ${p.volume}, p. ${p.page}`;
    root.querySelector('.pane-record').innerHTML = `
      <div class="viewer">
        <div class="viewer-bar"><span class="kind k-auth">Recorded Plat</span>
          <div class="viewer-title"><b>${esc(p.name || 'Name not read')}</b><span>Volume ${esc(p.volume)}, Page ${esc(p.page)} · ${esc(recorded(p.date))}</span></div>
          <a class="viewer-open" href="${src}" target="_blank" rel="noopener">Open Recorded Plat ↗</a>
        </div>
        <div class="viewer-body">
          <div class="viewer-page"><img src="${src}" alt="Recorded Plat, Volume ${esc(p.volume)}, Page ${esc(p.page)}"></div>
          <aside class="viewer-side">
            <dl class="viewer-facts">${[['Subdivision', p.name || 'Name not read'], ['Kind', p.kind], ['Recorded', recorded(p.date)]].map(([k, v]) => `
              <div class="fact"><dt>${k} <small>read by the vision model</small></dt><dd>${esc(v)}</dd></div>`).join('')}
            </dl>
            <p class="muted small">County Map Records, an Authoritative source. Placed on the GCAD parcels it lays out.</p>
          </aside>
        </div>
      </div>`;
    showTab('record');
  }

  function noJobs(res) {
    const n = res.nearest_outside;
    return `<div class="empty"><p>The Firm has no Jobs within ${mi(res.query.distance_mi)} of this address.${n
      ? ` The nearest is <b>${esc(n.job)}</b>, ${ft(n.distance_ft)} away.` : ''}</p>
      ${n && n.reaches_at_2_mi && res.query.distance_mi < 2 ? '<button class="widen">Search within 2 mi</button>' : ''}</div>`;
  }

  function draw(res) {
    const q = res.query, center = q.point, radius = q.distance_mi * 1609.344;
    map.invalidateSize();
    if (layer) layer.remove();
    layer = L.layerGroup().addTo(map);
    L.circle(center, { radius, color: '#0e6b7d', weight: 2, dashArray: '6 6', fillOpacity: 0.05, interactive: false }).addTo(layer);
    // A ring under the pins, so a Job at the address itself stays visible inside it
    L.marker(center, { icon: L.divIcon({ className: 'pin-wrap', html: '<div class="here"></div>', iconSize: [40, 40] }), zIndexOffset: -1000 })
      .bindTooltip(esc(q.label)).addTo(layer);
    const rows = {};
    root.querySelectorAll('tr[data-job]').forEach(tr => rows[tr.dataset.job] = tr);
    const drawn = [];
    res.jobs.forEach(j => j.pins.forEach(p => {
      // Jobs at the same point (within 50 m, as Records share a pin) sit side by side
      const dx = drawn.filter(q => map.distance(q, [p.lat, p.lon]) <= 50).length * 16;
      drawn.push([p.lat, p.lon]);
      const m = L.marker([p.lat, p.lon], { icon: L.divIcon({ className: 'pin-wrap', html: `<div class="pin ${mix(j.records.filter(r => p.records.includes(r.id)).map(r => r.kind))}">${j.rank}</div>`, iconSize: [28, 28], iconAnchor: [14 - dx, 14] }) })
        .bindTooltip(`<b>${esc(j.job)}</b> · ${ft(j.distance_ft)}<br>${esc(j.address || '')}`).addTo(layer);
      m.on('click', () => {
        if (root.querySelector(`tr.detail[data-for="${CSS.escape(j.job)}"]`).hidden) toggleRow(j.job);
        rows[j.job].scrollIntoView({ block: 'center', behavior: 'smooth' });
        rows[j.job].classList.add('flash');
        setTimeout(() => rows[j.job].classList.remove('flash'), 1200);
      });
      rows[j.job].addEventListener('mouseenter', () => m.getElement().firstChild.classList.add('hl'));
      rows[j.job].addEventListener('mouseleave', () => m.getElement().firstChild.classList.remove('hl'));
    }));
    fit = L.latLng(center).toBounds(radius * 2);
    if (res.ngs) {
      L.marker([res.ngs.lat, res.ngs.lon], { icon: L.divIcon({ className: 'pin-wrap', html: '<div class="ngs">▲</div>', iconSize: [20, 20] }) })
        .bindTooltip(`NGS Benchmark ${esc(res.ngs.id)} “${esc(res.ngs.name)}”, ${res.ngs.height_ft.toFixed(2)} ft`).addTo(layer);
      if (res.ngs.distance_ft <= 2 * 5280) fit = fit.extend([res.ngs.lat, res.ngs.lon]);
    }
    map.fitBounds(fit, { padding: [20, 20], animate: false });
  }

  async function boot() {
    start = await (await fetch('/api/start')).json();
    // ponytail: the 13 MB streets file is read whole, once, before the page shows: the app's server cannot send part of
    // a file, which pmtiles asks for by URL. Add Range requests to the server if the file grows much bigger.
    if (!start.map.live) streetsFile = new pmtiles.PMTiles(new pmtiles.FileSource(
      new File([await (await fetch('/tiles/galveston.pmtiles')).blob()], 'galveston.pmtiles')));
    const dl = document.createElement('datalist');
    dl.id = 'ss-addresses';
    dl.innerHTML = start.addresses.map(a => `<option value="${esc(a.address)}">`).join('');
    document.body.appendChild(dl);
    window.onpopstate = () => { state = fromURL(); state.id || state.q ? run() : home(); };
    window.onpopstate();
  }
  boot();
})();
