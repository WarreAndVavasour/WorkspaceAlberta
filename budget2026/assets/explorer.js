/* Budget 2026 Explorer — JSON Crack-style map (after the workspaceAlberta requirements board).
   Budget → chapter → section → measure. Text from the budget is data only; it is escaped, never executed. */
(() => {
  const root = document.getElementById("explorer");
  if (!root) return;
  const CFG = document.querySelector("[data-base]") || document.documentElement;
  const BASE = CFG.dataset.base || "/";
  const IDX = CFG.dataset.index || "";
  const $ = (s, el = root) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const link = (p) => BASE + p.replace(/^\//, "") + (p.endsWith("/") ? IDX : "");
  const track = (name, props) => { try { if (window.wvTrack) window.wvTrack(name, props); } catch (_) { /* analytics never blocks the map */ } };
  let lastQ = "", qTrackT = null;
  const money = (m) => {
    if (m == null) return "—";
    const a = Math.abs(m), s = m < 0 ? "−" : "";
    return a >= 1000 ? `${s}$${(a / 1000).toFixed(a >= 10000 ? 1 : 2).replace(/\.?0+$/, "")}B` : `${s}$${a.toFixed(0)}M`;
  };

  let D = null;
  const S = { q: "", lens: "", types: new Set(["spending", "tax", "savings_or_revenue", "no_line_item"]), loansOnly: false,
              open: new Set(), closed: new Set(), sel: "root", view: "map" };
  const W = { root: 300, chapter: 310, section: 310, measure: 330 }, HH = 32, RH = 22, VG = 16, HG = 64;

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    S.q = h.get("q") || ""; S.lens = h.get("lens") || ""; if (h.get("m")) S.sel = "m:" + h.get("m");
    if (h.get("view") === "list") S.view = "list";
  }
  function writeHash() {
    const h = new URLSearchParams();
    if (S.q) h.set("q", S.q); if (S.lens) h.set("lens", S.lens);
    if (S.sel && S.sel.startsWith("m:")) h.set("m", S.sel.slice(2)); if (S.view === "list") h.set("view", "list");
    const s = h.toString(); history.replaceState(null, "", s ? "#" + s : location.pathname + location.search);
  }

  const filtering = () => !!(S.q || S.lens || S.types.size < 4 || S.loansOnly);
  function matches(m) {
    if (!S.types.has(m.type)) return false;
    if (S.loansOnly && !m.loans) return false;
    if (S.lens && !m.lenses.includes(S.lens)) return false;
    if (S.q) {
      const hay = (m.t + " " + (m.quote || "") + " " + (m.facts || []).join(" ") + " " + m.lenses.join(" ") + " " + (m.sect || "")).toLowerCase();
      if (!S.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  // ---------- tree ----------
  function rowsFor(kind, x, kids) {
    if (kind === "root") return [
      { k: "title", v: D.meta.title, c: "v-str" }, { k: "tabled", v: D.meta.date, c: "v-str" },
      { k: "deficit_26_27", v: `−$${D.meta.deficit}B`, c: "v-num" }, { k: "measures", v: `${D.meta.measure_count}`, c: "v-num" },
      { k: "chapters", v: `[${kids}] ${S.closed.has("root") ? "▸" : "▾"}`, c: "v-ref", toggle: "root" }];
    if (kind === "chapter") return [
      { k: "net_5yr", v: money(x.net_total), c: "v-num" }, { k: "capital_5yr", v: money(x.capital_total), c: "v-num" },
      { k: "pages", v: x.pages, c: "v-str" },
      { k: "sections", v: `[${kids}] ${S.closed.has(x.id) ? "▸" : "▾"}`, c: "v-ref", toggle: x.id }];
    if (kind === "section") return [
      { k: "net_5yr", v: x.net_total == null ? "no cost line" : money(x.net_total), c: "v-num" },
      { k: "measures", v: `[${kids}] ${isOpen(x.id) ? "▾" : "▸"}`, c: "v-ref", toggle: x.id }];
    return [
      { k: "type", v: D.types[x.type].name.toLowerCase() + (x.loans ? " + financing" : ""), c: "v-str" },
      { k: "net_5yr", v: x.type === "no_line_item" ? "null" : money(x.net_total), c: "v-num" },
      { k: "lenses", v: x.lenses.length ? x.lenses.join(", ") : "[]", c: "v-str" },
      { k: "source", v: `p. ${x.printed ?? "?"} (PDF ${x.page})`, c: "v-str" }];
  }
  const isOpen = (id) => (filtering() ? !S.closed.has(id) : S.open.has(id));
  function buildTree() {
    const f = filtering();
    const chapters = D.chapters.map((ch) => {
      const secs = ch.sections.map((sc) => {
        const ms = sc.measures.map((id) => D.measures[id]).filter((m) => !f || matches(m));
        return { sc, ms };
      }).filter(({ ms }) => !f || ms.length);
      return { ch, secs };
    }).filter(({ secs }) => !f || secs.length);
    const color = (t) => `var(--m-${{ spending: "spending", tax: "tax", savings_or_revenue: "savings", no_line_item: "none" }[t]})`;
    const rootKids = S.closed.has("root") ? [] : chapters.map(({ ch, secs }) => {
      const kids = S.closed.has(ch.id) ? [] : secs.map(({ sc, ms }) => {
        const mk = isOpen(sc.id) ? ms.map((m) => ({ id: "m:" + m.id, kind: "measure", x: m, head: m.t, color: color(m.type), sq: m.loans, w: W.measure, rows: rowsFor("measure", m), children: [] })) : [];
        return { id: sc.id, kind: "section", x: sc, head: `${sc.code} ${sc.title}`, color: "var(--ink-3)", w: W.section, rows: rowsFor("section", sc, ms.length), children: mk };
      });
      return { id: ch.id, kind: "chapter", x: ch, head: `Chapter ${ch.n}: ${ch.title}`, color: "var(--gold)", w: W.chapter, rows: rowsFor("chapter", ch, secs.length), children: kids };
    });
    return { id: "root", kind: "root", head: "Budget 2026", color: "var(--gold)", w: W.root, rows: rowsFor("root", null, chapters.length), children: rootKids };
  }
  const nodeH = (n) => HH + n.rows.length * RH + 6;
  function layout(tree) {
    const nodes = [], edges = [], colW = []; let cursor = 0;
    (function walk(n, depth) {
      n.depth = depth; nodes.push(n); colW[depth] = Math.max(colW[depth] || 0, n.w);
      const start = cursor;
      if (!n.children.length) { n.y = cursor; cursor += nodeH(n) + VG; return; }
      n.children.forEach((c) => walk(c, depth + 1));
      const first = n.children[0].y, last = n.children[n.children.length - 1].y;
      n.y = Math.max(start, Math.round((first + last) / 2 - nodeH(n) / 2 + 20));
      n.y = Math.max(n.y, start);
      cursor = Math.max(cursor, n.y + nodeH(n) + VG);
    })(tree, 0);
    const colX = colW.map((_, d) => colW.slice(0, d).reduce((a, w) => a + w + HG, 0));
    nodes.forEach((n) => { n.x = colX[n.depth]; n.children.forEach((c) => edges.push([n, c])); });
    return { nodes, edges, width: colX.at(-1) + colW.at(-1), height: cursor };
  }

  // ---------- render map ----------
  const V = { k: 0.8, x: 16, y: 16, ready: false };
  let G = null;
  const world = $("#world"), canvas = $("#canvas");
  function applyView(ease) { world.classList.toggle("ease", !!ease); world.style.transform = `translate(${V.x}px,${V.y}px) scale(${V.k})`; }
  function renderMap() {
    G = layout(buildTree());
    const on = new Set();
    let n = G.nodes.find((x) => x.id === S.sel);
    const parent = (c) => G.edges.find((e) => e[1] === c)?.[0];
    while (n) { on.add(n.id); n = parent(n); }
    const svg = G.edges.map(([a, b]) => {
      const ri = a.rows.findIndex((r) => r.toggle); const x1 = a.x + a.w, y1 = a.y + HH + ri * RH + RH / 2, x2 = b.x, y2 = b.y + HH / 2, mx = (x2 - x1) / 2;
      return `<path class="edge ${on.has(a.id) && on.has(b.id) ? "on" : ""}" d="M${x1},${y1} C${x1 + mx},${y1} ${x2 - mx},${y2} ${x2},${y2}"/>`;
    }).join("");
    const cards = G.nodes.map((n) => `<div class="node ${n.kind} ${n.id === S.sel ? "sel" : ""}" data-node="${esc(n.id)}" style="left:${n.x}px;top:${n.y}px;width:${n.w}px">
      <button type="button" class="nh" data-select="${esc(n.id)}" title="${esc(n.head)}"><i class="${n.sq ? "sq" : ""}" style="--c:${n.color}"></i><b>${esc(n.head)}</b></button>
      ${n.rows.map((r) => r.toggle ? `<button type="button" class="nr" data-toggle="${esc(r.toggle)}" aria-label="Show or hide ${esc(r.k)}"><span class="nk">${r.k}</span><span class="nv ${r.c}">${esc(r.v)}</span></button>`
        : `<div class="nr"><span class="nk">${r.k}</span><span class="nv ${r.c}">${esc(r.v)}</span></div>`).join("")}</div>`).join("");
    world.innerHTML = `<svg width="${G.width}" height="${G.height}" aria-hidden="true">${svg}</svg>${cards}`;
    world.style.width = G.width + "px"; world.style.height = G.height + "px";
    if (!V.ready) {
      V.ready = true; V.k = innerWidth < 640 ? 0.6 : 0.85;
      const r = G.nodes[0], c = canvas.getBoundingClientRect();
      V.k = Math.max(0.62, Math.min(V.k, (c.height - 32) / G.height, (c.width - 32) / G.width));
      V.x = Math.max(16, (c.width - G.width * V.k) / 2);
      V.y = G.height * V.k < c.height - 32 ? (c.height - G.height * V.k) / 2 : c.height * 0.45 - (r.y + nodeH(r) / 2) * V.k;
      applyView();
    } else applyView();
  }
  function fit() {
    const c = canvas.getBoundingClientRect();
    V.k = Math.max(0.12, Math.min(1, (c.width - 32) / G.width, (c.height - 32) / G.height)); V.x = 16; V.y = 16; applyView(true);
  }
  function zoomAt(f, cx, cy) { const k = Math.min(1.8, Math.max(0.1, V.k * f)); V.x = cx - ((cx - V.x) * k) / V.k; V.y = cy - ((cy - V.y) * k) / V.k; V.k = k; applyView(); }
  function focusNode(id) {
    const n = G && G.nodes.find((x) => x.id === id); if (!n) return;
    const c = canvas.getBoundingClientRect(); V.k = Math.max(V.k, 0.75);
    V.x = c.width * 0.42 - (n.x + n.w / 2) * V.k; V.y = c.height * 0.32 - n.y * V.k; applyView(true);
  }
  (function panZoom() {
    const pts = new Map(); let last = null, pinch = null, moved = 0;
    canvas.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".zoom")) return;
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY }); moved = 0; last = { x: e.clientX, y: e.clientY }; canvas.classList.add("drag");
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = Math.hypot(a.x - b.x, a.y - b.y); }
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pts.size === 2 && pinch) { const [a, b] = [...pts.values()], d = Math.hypot(a.x - b.x, a.y - b.y), r = canvas.getBoundingClientRect();
        zoomAt(d / pinch, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top); pinch = d; moved += 10; return; }
      if (moved > 4 && !canvas.hasPointerCapture(e.pointerId)) canvas.setPointerCapture(e.pointerId);
      V.x += e.clientX - last.x; V.y += e.clientY - last.y; moved += Math.abs(e.clientX - last.x) + Math.abs(e.clientY - last.y); last = { x: e.clientX, y: e.clientY }; applyView();
    });
    const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch = null; if (!pts.size) canvas.classList.remove("drag"); if (pts.size === 1) last = [...pts.values()][0]; };
    canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("click", (e) => {
      if (moved > 6) { moved = 0; e.preventDefault(); return; }
      const t = e.target.closest("[data-toggle]"), s = e.target.closest("[data-select]");
      if (t) { toggle(t.dataset.toggle); return; }
      if (s) select(s.dataset.select);
    }, true);
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault(); const r = canvas.getBoundingClientRect();
      if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top);
      else { V.x -= e.deltaX; V.y -= e.deltaY; applyView(); }
    }, { passive: false });
    $("#zin").onclick = () => { const r = canvas.getBoundingClientRect(); zoomAt(1.2, r.width / 2, r.height / 2); };
    $("#zout").onclick = () => { const r = canvas.getBoundingClientRect(); zoomAt(1 / 1.2, r.width / 2, r.height / 2); };
    $("#zfit").onclick = () => fit();
    $("#zfull").onclick = () => { root.classList.toggle("full"); if (root.classList.contains("full")) track("budget_map_fullscreen", {}); $("#zfull").textContent = root.classList.contains("full") ? "Close" : "Full"; setTimeout(fit, 30); };
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && root.classList.contains("full")) $("#zfull").click(); });
  })();
  function toggle(id) {
    const f = filtering();
    if (id === "root" || id.startsWith("ch")) { S.closed.has(id) ? S.closed.delete(id) : S.closed.add(id); }
    else if (f) { S.closed.has(id) ? S.closed.delete(id) : S.closed.add(id); }
    else { S.open.has(id) ? S.open.delete(id) : S.open.add(id); }
    renderMap();
  }

  // ---------- detail ----------
  function bars(vals) {
    const w = 260, h = 92, pad = 18, bw = 30, gap = (w - pad * 2 - bw * 5) / 4;
    const nums = vals.map((v) => v ?? 0), max = Math.max(1, ...nums.map(Math.abs));
    const hasNeg = nums.some((v) => v < 0), hasPos = nums.some((v) => v > 0);
    const zero = hasNeg && hasPos ? h / 2 : hasNeg ? 14 : h - 22, span = hasNeg && hasPos ? h / 2 - 16 : h - 38;
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Yearly impact, millions of dollars">${nums.map((v, i) => {
      const x = pad + i * (bw + gap), bh = Math.max(v ? 2 : 0, (Math.abs(v) / max) * span), y = v >= 0 ? zero - bh : zero;
      return `<rect class="bar" x="${x}" y="${y}" width="${bw}" height="${bh}" rx="3" style="--c:var(${v < 0 ? "--neg" : "--pos"})" data-tip="${D.years[i]}: ${vals[i] == null ? "no amount" : money(v)}"/>
        <text x="${x + bw / 2}" y="${h - 4}" text-anchor="middle">${D.years[i].slice(2)}</text>`;
    }).join("")}<line class="axis" x1="${pad - 6}" x2="${w - pad + 6}" y1="${zero}" y2="${zero}"/></svg>`;
  }
  function renderDetail() {
    const el = $("#detail");
    if (S.sel && S.sel.startsWith("m:")) {
      const m = D.measures[S.sel.slice(2)]; if (!m) return;
      const t = D.types[m.type];
      el.innerHTML = `<span class="k">Chapter ${m.ch} · ${esc(m.sec || "")}</span><h3>${esc(m.t)}</h3>
        <div class="badges"><span class="badge t-${m.type}">${esc(t.name)}</span>${m.loans ? '<span class="badge t-loans">Loans, equity or financing</span>' : ""}${m.cap ? '<span class="badge plain">Includes capital</span>' : ""}</div>
        ${m.type === "no_line_item" ? `<p>${esc(t.short)}</p>` : `<p><strong class="num">${money(m.net_total)}</strong> over five years (accrual impact on the budgetary balance).</p>${bars(m.net)}`}
        ${m.quote ? `<blockquote>“${esc(m.quote.length > 240 ? m.quote.slice(0, 230).replace(/\s\S*$/, "") + " …" : m.quote)}”</blockquote><p class="source-line">Budget 2026, p. ${m.qp ?? "?"}</p>` : ""}
        ${m.facts && m.facts.length ? `<ul class="facts">${m.facts.slice(0, 3).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
        ${m.note ? `<div class="wv"><span class="tag">W&amp;V perspective</span><p>${esc(m.note)}</p></div>` : ""}
        <div class="chips">${m.lenses.map((l) => `<a class="chip" href="${link("/topics/" + l + "/")}">${esc(D.lensNames[l] || l)}</a>`).join("")}</div>
        <p><a href="${link(m.url)}">Full measure page →</a><br><a href="${esc(m.src)}" rel="noopener">Official chapter on budget.canada.ca ↗</a></p>`;
      return;
    }
    if (S.sel && S.sel.startsWith("ch")) {
      const c = D.chapters.find((x) => x.id === S.sel);
      el.innerHTML = `<span class="k">Chapter ${c.n} · ${esc(c.pages)}</span><h3>${esc(c.title)}</h3>
        <p><strong class="num">${money(c.net_total)}</strong> net fiscal impact over five years, of which <strong class="num">${money(c.capital_total)}</strong> is capital investment.</p>${bars(c.net)}
        <p>${c.count} measures. Open a section on the map to see them.</p><p><a href="${link(c.url)}">Chapter page →</a><br><a href="${esc(c.src)}" rel="noopener">Official chapter ↗</a></p>`;
      return;
    }
    if (S.sel && S.sel.startsWith("sec")) {
      const sc = D.chapters.flatMap((c) => c.sections).find((x) => x.id === S.sel); if (!sc) return;
      el.innerHTML = `<span class="k">Section ${esc(sc.code)}</span><h3>${esc(sc.title)}</h3>
        <p>${sc.net_total == null ? "Announcements without their own cost line." : `<strong class="num">${money(sc.net_total)}</strong> over five years.`}</p>
        <ul class="facts">${sc.measures.map((id) => D.measures[id]).filter((m) => !filtering() || matches(m)).map((m) => `<li><a href="#" data-pick="${esc(m.id)}">${esc(m.t)}</a> <span class="num muted">${m.type === "no_line_item" ? "" : money(m.net_total)}</span></li>`).join("")}</ul>`;
      return;
    }
    el.innerHTML = `<span class="k">How to use the map</span><h3>Budget 2026, as a tree</h3>
      <p>Start at the budget, open a chapter, then a section, then a measure. Every measure links to its page in the budget.</p>
      <p>Search or pick a lens to light up the measures that match. The coloured dot shows the money type; a square dot means loans, equity or financing are involved.</p>
      <div class="legend">${Object.entries(D.types).map(([k, t]) => `<span style="--c:var(--m-${{ spending: "spending", tax: "tax", savings_or_revenue: "savings", no_line_item: "none" }[k]})">${esc(t.name)}</span>`).join("")}</div>
      <p class="muted small">Five-year totals are accrual impacts on the budgetary balance. Don't add tax measures, spending and loans together as if they were one pot of money.</p>`;
  }
  root.addEventListener("click", (e) => { const a = e.target.closest("[data-pick]"); if (a) { e.preventDefault(); select("m:" + a.dataset.pick, true); } });

  // ---------- list view ----------
  function renderList() {
    const ms = Object.values(D.measures).filter(matches).sort((a, b) => (b.net_total ?? -1e9) - (a.net_total ?? -1e9));
    $("#list").innerHTML = `<table class="data"><caption>${ms.length} measures${filtering() ? " match your filters" : ""}. Five-year net impact, CAD.</caption>
      <thead><tr><th scope="col">Measure</th><th scope="col">Chapter</th><th scope="col">Type</th><th scope="col" class="n">5-year net</th></tr></thead><tbody>
      ${ms.map((m) => `<tr><td><a href="${link(m.url)}">${esc(m.t)}</a></td><td>${m.ch}</td><td><span class="badge t-${m.type}">${esc(D.types[m.type].name)}</span></td><td class="n">${m.type === "no_line_item" ? "—" : money(m.net_total)}</td></tr>`).join("")}</tbody></table>`;
  }

  // ---------- state changes ----------
  function status() {
    const n = Object.values(D.measures).filter(matches).length;
    $("#status").textContent = filtering() ? `${n} of ${D.meta.measure_count} measures match.` : `${D.meta.measure_count} measures in 6 chapters. Open a section to see its measures.`;
  }
  function render() {
    $("#canvas").hidden = S.view !== "map"; $("#list").hidden = S.view !== "list";
    root.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === S.view)));
    root.querySelectorAll("[data-lens]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lens === S.lens)));
    if (S.view === "map") renderMap(); else renderList();
    renderDetail(); status(); writeHash();
  }
  function select(id, focus) {
    S.sel = id;
    if (id.startsWith("m:")) track("budget_measure_opened", { measure: id.slice(2), surface: "map" });
    else if (id.startsWith("ch")) track("budget_chapter_opened", { chapter: id, surface: "map" });
    if (id.startsWith("m:")) {
      const m = D.measures[id.slice(2)];
      if (m) { const sc = D.chapters.flatMap((c) => c.sections).find((s) => s.measures.includes(m.id)); if (sc) { S.open.add(sc.id); S.closed.delete(sc.id); } S.closed.delete("ch" + m.ch); S.closed.delete("root"); }
    }
    render(); if (focus || id.startsWith("m:")) focusNode(id);
    if (innerWidth < 960 && id !== "root") $("#detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  let qt = null;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(qt); qt = setTimeout(() => { S.q = e.target.value.trim(); S.closed.clear(); render(); if (S.view === "map" && filtering()) fit(); }, 160);
    clearTimeout(qTrackT); qTrackT = setTimeout(() => {
      const q = e.target.value.trim().toLowerCase().slice(0, 60);
      if (q.length >= 3 && q !== lastQ) { lastQ = q; track("budget_search", { query: q, results: Object.values(D.measures).filter(matches).length }); }
    }, 1200);
  });
  $("#search").addEventListener("submit", (e) => e.preventDefault());
  root.querySelectorAll("[data-lens]").forEach((b) => b.addEventListener("click", () => { S.lens = S.lens === b.dataset.lens ? "" : b.dataset.lens; S.closed.clear(); render(); if (S.view === "map") fit(); if (S.lens) track("budget_lens_selected", { lens: S.lens, surface: "map" }); }));
  root.querySelectorAll("[data-type]").forEach((c) => c.addEventListener("change", () => { c.checked ? S.types.add(c.dataset.type) : S.types.delete(c.dataset.type); render(); track("budget_filter_changed", { filter: "money_type", money_type: c.dataset.type, on: c.checked }); }));
  $("#loans").addEventListener("change", (e) => { S.loansOnly = e.target.checked; render(); if (S.loansOnly) track("budget_filter_changed", { filter: "loans_only" }); });
  root.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => { S.view = b.dataset.view; render(); if (S.view === "map") fit(); track("budget_view_changed", { view: S.view }); }));
  $("#reset").addEventListener("click", () => { S.q = ""; S.lens = ""; S.loansOnly = false; $("#q").value = ""; $("#loans").checked = false; S.types = new Set(["spending", "tax", "savings_or_revenue", "no_line_item"]); root.querySelectorAll("[data-type]").forEach((c) => (c.checked = true)); S.closed.clear(); S.open.clear(); S.sel = "root"; render(); fit(); });


  fetch(link("/data/explorer.json")).then((r) => r.json()).then((data) => {
    D = data; readHash(); $("#q").value = S.q;
    if (!filtering()) D.chapters.forEach((c) => S.closed.add(c.id));
    if (S.sel.startsWith("m:") && D.measures[S.sel.slice(2)]) { V.ready = true; select(S.sel, true); }
    else { if (!D.measures[S.sel.slice(2)]) S.sel = "root"; render(); }
    if (location.hash.includes("=")) root.scrollIntoView({ block: "start" });
  }).catch(() => { $("#status").textContent = "The map could not load. Use the chapter and topic pages below; every measure is listed there."; });
})();
