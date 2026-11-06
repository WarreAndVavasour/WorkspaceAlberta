/* Budget 2026 Explorer — shared page script.
   1. Chart tooltips ([data-tip]) with keyboard focus equivalents.
   2. PostHog analytics (same project as warreandvavasour.com, tagged product=budget2026).
      No cookies (sessionStorage), no person profiles, no autocapture, honours Do Not Track,
      and only runs on the production hostname.
   3. Click tracking: link_clicked / button_clicked for every link and button (label, page
      section, destination without its query string; form fields are never read), plus the
      named funnel events below. Add data-track-skip to leave an element out. */
(() => {
  // ---------- tooltips ----------
  const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; tip.setAttribute("role", "status"); document.body.appendChild(tip);
  const show = (t, x, y) => { tip.textContent = t.dataset.tip; tip.hidden = false; tip.style.left = Math.min(x + 14, innerWidth - 240) + "px"; tip.style.top = y + 14 + "px"; };
  document.addEventListener("pointermove", (e) => { const t = e.target.closest && e.target.closest("[data-tip]"); if (t) show(t, e.clientX, e.clientY); else tip.hidden = true; });
  document.addEventListener("focusin", (e) => { const t = e.target.closest && e.target.closest("[data-tip]"); if (t) { const r = t.getBoundingClientRect(); show(t, r.left, r.bottom); } });
  document.addEventListener("focusout", () => { tip.hidden = true; });
  document.addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });

  // ---------- analytics ----------
  const KEY = "phc_RDTMHJmWuROb9X3lYLTGydkyfvtRLQJbwcpQB0gQsPd";
  const HOST = "https://us.i.posthog.com";
  const live = /(^|\.)warreandvavasour\.com$/.test(location.hostname);
  const dnt = navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl === true;
  const pageType = (document.querySelector("meta[name='wv:page-type']") || {}).content || "page";
  const slug = (document.querySelector("meta[name='wv:slug']") || {}).content || "";
  let ready = false;
  const queue = [];
  window.wvTrack = (name, props = {}) => {
    const p = { page_type: pageType, slug, path: location.pathname, ...props };
    if (ready && window.posthog) { try { window.posthog.capture(name, p); } catch (_) { /* never affect the page */ } }
    else if (queue.length < 50) queue.push([name, p]);
  };
  if (live && !dnt) {
    try {
      /* PostHog loader stub (posthog-js array.js) */
      !function (t, e) { var o, n, p, r; e.__SV || (window.posthog = e, e._i = [], e.init = function (i, s, a) { function g(t, e) { var o = e.split("."); 2 == o.length && (t = t[o[0]], e = o[1]), t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))) } } (p = t.createElement("script")).type = "text/javascript", p.crossOrigin = "anonymous", p.async = !0, p.src = s.api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js", (r = t.getElementsByTagName("script")[0]).parentNode.insertBefore(p, r); var u = e; for (void 0 !== a ? u = e[a] = [] : a = "posthog", u.people = u.people || [], u.toString = function (t) { var e = "posthog"; return "posthog" !== a && (e += "." + a), t || (e += " (stub)"), e }, u.people.toString = function () { return u.toString(1) + ".people (stub)" }, o = "init capture register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset get_distinct_id get_property".split(" "), n = 0; n < o.length; n++)g(u, o[n]); e._i.push([i, s, a]) }, e.__SV = 1) }(document, window.posthog || []);
      window.posthog.init(KEY, {
        api_host: HOST, capture_pageview: true, capture_pageleave: true, autocapture: false,
        disable_session_recording: true, persistence: "sessionStorage", person_profiles: "never",
        loaded: (ph) => {
          ph.register({ product: "budget2026", site: "budget2026.warreandvavasour.com", page_type: pageType, slug });
          ready = true;
          queue.splice(0).forEach(([n, p]) => { try { ph.capture(n, p); } catch (_) { /* ignore */ } });
        },
      });
    } catch (_) { /* analytics must never break the page */ }
  }

  // Outbound and funnel clicks: W&V offers, the Claude connector, official sources and data downloads.
  const DEST = [
    [/warreandvavasour\.com\/workspacealberta/, "workspacealberta"], [/claude\.ai\/directory\/connectors/, "claude_connector"],
    [/warreandvavasour\.com\/training/, "training"], [/warreandvavasour\.com\/terminal/, "ai_terminal"],
    [/warreandvavasour\.com\/million/, "million_dollar_problem"], [/warreandvavasour\.com\/pacific-link/, "pacific_link"],
    [/warreandvavasour\.com\/?$/, "wv_home"], [/budget\.canada\.ca/, "official_budget"],
    [/\/data\/|\.json$/, "data_download"], [/(agents|skill)\.md$|llms\.txt$|agent-card\.json$/, "agent_file"],
  ];
  const placementOf = (el) => {
    const section = el.closest("section[id], section[aria-labelledby], aside, header, footer");
    return section ? (section.id || section.getAttribute("aria-labelledby") || section.tagName.toLowerCase()) : "body";
  };
  const labelOf = (el) => (el.getAttribute("aria-label") || el.textContent || el.getAttribute("title") ||
    (el.tagName === "INPUT" ? el.value : "") || "").replace(/\s+/g, " ").trim().slice(0, 80);
  const destinationOf = (raw) => {
    if (raw.startsWith("#")) return { link_type: "anchor", destination: raw.slice(0, 80) };
    try {
      const u = new URL(raw, location.href);
      if (u.protocol === "mailto:" || u.protocol === "tel:") return { link_type: u.protocol.slice(0, -1), destination: u.protocol + u.pathname };
      if (!/^https?:$/.test(u.protocol)) return { link_type: "other", destination: u.protocol };
      if (u.origin === location.origin) return { link_type: u.pathname === location.pathname && u.hash ? "anchor" : "internal", destination: u.pathname + u.hash };
      return { link_type: /(^|\.)warreandvavasour\.com$/.test(u.hostname) ? "internal" : "external", destination: u.host + u.pathname, destination_host: u.host };
    } catch (_) { return { link_type: "other", destination: "" }; }
  };
  const CLICKABLE = "a[href], button, [role='button'], summary, input[type='submit'], input[type='button']";
  document.addEventListener("click", (e) => {
    const el = e.target.closest && e.target.closest(CLICKABLE);
    if (!el || el.closest("[data-track-skip]")) return;
    const placement = placementOf(el);
    const base = { label: labelOf(el), section: placement, element: el.tagName.toLowerCase() };
    if (el.tagName !== "A") { window.wvTrack("button_clicked", base); return; }
    window.wvTrack("link_clicked", { ...base, ...destinationOf(el.getAttribute("href") || "") });
    const href = el.href;
    const hit = DEST.find(([re]) => re.test(href));
    if (!hit) return;
    window.wvTrack(hit[1] === "data_download" || hit[1] === "agent_file" ? "budget_data_opened" : "budget_outbound_click", {
      destination: hit[1], href, link_text: (el.textContent || "").trim().slice(0, 80), placement,
    });
  }, true);
})();
