(function () {
  const VAL = {winner: "Winner", promising: "Promițător", too_new: "Prea nou", image: "Imagine", video: "Video", carousel: "Carusel",
    direct: "Concurent direct", adjacent: "Adiacent", store_wide: "Magazin generic", unrelated: "Fără legătură",
    unaware: "Unaware", problem_aware: "Problem-aware", solution_aware: "Solution-aware", product_aware: "Product-aware", most_aware: "Most-aware",
    question: "Întrebare", bold_claim: "Afirmație îndrăzneață", pain_point: "Durere", personal_story: "Poveste personală", testimonial: "Testimonial",
    statistic: "Cifră", curiosity_gap: "Curiozitate", offer: "Ofertă", audience_callout: "Apel la public", how_to: "Cum să", news: "Noutate",
    warning: "Avertisment", product_name: "Numele produsului", pain_relief: "Eliminarea problemei", transformation: "Transformare",
    social_proof: "Dovadă socială", authority: "Autoritate", unique_mechanism: "Mecanism unic", price_value: "Preț / valoare",
    convenience: "Comoditate", vs_alternatives: "Comparație", identity: "Identitate", urgency: "Urgență", other: "Altele",
    fear: "Frică", frustration: "Frustrare", hope: "Speranță", curiosity: "Curiozitate", belonging: "Apartenență", status: "Statut", humor: "Umor", neutral: "Neutru",
    pas: "Problemă–agitare–soluție", aida: "AIDA", story_to_offer: "Poveste → ofertă", benefit_list: "Listă de beneficii", one_liner: "O frază",
    advertorial: "Advertorial", offer_only: "Doar oferta",
    shop_home: "Homepage magazin", product_page: "Pagină de produs", lead_funnel: "Funnel de lead-uri", service_home: "Homepage servicii",
    content: "Conținut", offer_page: "Pagină de ofertă", buy: "Cumpărare", form: "Formular", none: "Fără acțiune", call: "Apel", quiz: "Quiz", register: "Înregistrare",
    exact: "Preț exact", on_request: "La cerere", from: "De la", web: "Web", facebook: "Facebook", whatsapp: "WhatsApp"};
  const L = v => VAL[v] || v || "—";
  const fmt = n => n == null ? "—" : Number(n).toLocaleString("ro-RO");
  const short = n => n == null ? "—" : n >= 1e6 ? (n / 1e6).toFixed(1).replace(".", ",") + " mil." : n >= 1e3 ? Math.round(n / 1e3) + " k" : String(n);
  const pct = (a, b) => b ? Math.round(a / b * 100) : 0;
  const date = s => { try { return new Date(s).toLocaleDateString("ro-RO", {day: "numeric", month: "long", year: "numeric"}); } catch (e) { return s; } };
  const domain = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u || ""; } };
  const PAGE = 30;
  const COUNTRY = {RO: "România", MD: "Moldova", HU: "Ungaria", BG: "Bulgaria", DE: "Germania", AT: "Austria", IT: "Italia", ES: "Spania",
    FR: "Franța", PL: "Polonia", NL: "Olanda", BE: "Belgia", PT: "Portugalia", GR: "Grecia", CZ: "Cehia", SK: "Slovacia", GB: "Regatul Unit", US: "SUA"};

  function initState() {
    return {page: "ads", q: "", buckets: ["winner", "promising"], formats: [], angle: "", sort: "reach", limit: PAGE, modal: null,
      lq: "", ltype: "", laction: "", lsort: "days", llimit: PAGE, lmodal: null};
  }

  function countBy(list, f) { const m = {}; list.forEach(x => { const k = f(x); if (k != null) m[k] = (m[k] || 0) + 1; }); return Object.entries(m).sort((a, b) => b[1] - a[1]); }

  function vals(c) {
    const RD = window.RD; const s = c.state;
    const set = p => c.setState(p);
    if (!RD) return {ready: false, notReady: true};
    const all = RD.ads.filter(a => a.inNiche !== false);
    const aud = RD.summary.audience || {};
    const g = aud.gender || {};
    const gt = (g.male || 0) + (g.female || 0);
    const ageMax = Math.max(...(aud.ages || []).map(a => a.male + a.female), 1);
    const angles = countBy(all, a => a.j && a.j.angle);
    const hooks = countBy(all, a => a.j && a.j.hook_type);
    const aw = countBy(all, a => a.j && a.j.awareness);
    const winners = all.filter(a => a.bucket === "winner").length;
    const medDays = (() => { const d = all.map(a => a.days).sort((a, b) => a - b); return d[Math.floor(d.length / 2)] || 0; })();

    // players
    const pm = {};
    all.forEach(a => { const p = pm[a.page] || (pm[a.page] = {name: a.page, ads: 0, reach: 0, days: 0, best: null}); p.ads++; p.reach += a.reach || 0; p.days = Math.max(p.days, a.days); if (!p.best || (a.reach || 0) > (p.best.reach || 0)) p.best = a; });
    const players = Object.values(pm).sort((a, b) => b.reach - a.reach || b.ads - a.ads).slice(0, 10);
    const pMax = players[0] ? players[0].reach || 1 : 1;

    const bar = (rows, total) => { const mx = rows[0] ? rows[0][1] : 1; return rows.slice(0, 6).map(([k, n]) => ({label: L(k), n, share: pct(n, total) + "%", w: Math.round(n / mx * 100) + "%"})); };

    // ad filters
    const toggle = (key, v) => () => { const cur = s[key]; set({[key]: cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v], limit: PAGE}); };
    const chips = (key, list) => list.map(([v, n]) => { const on = s[key].includes(v); return {label: L(v), n, on, off: !on, toggle: toggle(key, v)}; });
    const SORTS = {reach: a => a.reach || -1, days: a => a.days, per_day: a => a.perDay || -1, recent: a => Date.parse(a.start), variants: a => a.variants};
    const q = s.q.trim().toLowerCase();
    const filtered = all.filter(a => (!s.buckets.length || s.buckets.includes(a.bucket)) && (!s.formats.length || s.formats.includes(a.format))
      && (!s.angle || (a.j && a.j.angle === s.angle)) && (!q || [a.body, a.title, a.page, a.hook].join(" ").toLowerCase().includes(q)))
      .sort((a, b) => SORTS[s.sort](b) - SORTS[s.sort](a));
    const reachMax = Math.max(...filtered.map(a => a.reach || 0), 1);
    const row = (a, i) => ({id: a.id, n: String(i + 1).padStart(2, "0"), img: a.img, hasImg: !!a.img, noImg: !a.img, page: a.page,
      hook: a.hook || a.title || "(fără text)", days: a.days, reach: short(a.reach), perDay: a.perDay ? fmt(a.perDay) + "/zi" : "—",
      reachW: Math.round((a.reach || 0) / reachMax * 100) + "%", bucket: L(a.bucket), isWinner: a.bucket === "winner", notWinner: a.bucket !== "winner",
      format: L(a.format), angle: L(a.j && a.j.angle), awareness: L(a.j && a.j.awareness), start: date(a.start),
      open: () => set({modal: a.id})});
    const rows = filtered.slice(0, s.limit).map(row);

    const ma = s.modal && all.find(a => a.id === s.modal);
    const m = ma ? Object.assign(row(ma, 0), {body: ma.body, title: ma.title, cta: ma.cta || "—", lib: ma.lib, link: domain(ma.link), linkUrl: ma.link,
      variants: ma.variants, platforms: (ma.platforms || []).map(p => p.toLowerCase()).join(" · "), reachFull: fmt(ma.reach),
      hookType: L(ma.j && ma.j.hook_type), emotion: L(ma.j && ma.j.emotion), structure: L(ma.j && ma.j.structure),
      top: ma.top ? `${ma.top.gender === "male" ? "Bărbați" : "Femei"} ${ma.top.age} · ${ma.top.pct}%` : "—",
      male: ma.gender ? ma.gender.male + "%" : "0%", female: ma.gender ? ma.gender.female + "%" : "0%",
      ages: (ma.ages || []).map(x => ({age: x.age, v: x.male + x.female, w: (x.male + x.female) + "%"})),
      flags: [["Ofertă", ma.j && ma.j.has_offer], ["Urgență", ma.j && ma.j.has_urgency], ["Garanție", ma.j && ma.j.has_guarantee]].map(([l, v]) => ({label: l, yes: v >= .5, no: !(v >= .5)}))}) : null;

    // landings
    const lands = RD.lands;
    const lsum = RD.lsummary || {dims: {}};
    const lq = s.lq.trim().toLowerCase();
    const LS = {days: l => l.days || 0, trust: l => l.j.trust || 0, match: l => l.j.ad_match || 0, ads: l => l.nAds};
    const lf = lands.filter(l => (!s.ltype || l.j.page_type === s.ltype) && (!s.laction || l.j.main_action === s.laction)
      && (!lq || [l.title, l.url, l.page, l.desc].join(" ").toLowerCase().includes(lq))).sort((a, b) => LS[s.lsort](b) - LS[s.lsort](a));
    const score = v => v == null ? "—" : Math.round(v * 100);
    const lrow = (l, i) => ({id: l.id, n: String(i + 1).padStart(2, "0"), title: l.title || domain(l.url), domain: domain(l.url), page: l.page || domain(l.url),
      img: l.thumb, hasImg: !!l.thumb, noImg: !l.thumb, type: L(l.j.page_type), action: L(l.j.main_action), price: L(l.j.price_shown),
      trust: score(l.j.trust), match: score(l.j.ad_match), trustW: (l.j.trust == null ? 0 : score(l.j.trust)) + "%", matchW: (l.j.ad_match == null ? 0 : score(l.j.ad_match)) + "%", days: l.days || 0, nAds: l.nAds,
      open: () => set({lmodal: l.id})});
    const lrows = lf.slice(0, s.llimit).map(lrow);
    const lm0 = s.lmodal && lands.find(l => l.id === s.lmodal);
    const lm = lm0 ? Object.assign(lrow(lm0, 0), {url: lm0.url, desc: lm0.desc || "—", hero: lm0.hero || "—", hooks: lm0.hooks.map(h => ({h})),
      cta: score(lm0.j.cta_clarity), spec: score(lm0.j.promise_specificity),
      facts: [["Formular", lm0.facts.has_form], ["Telefon", lm0.facts.has_phone], ["WhatsApp", lm0.facts.has_whatsapp], ["E-mail", lm0.facts.has_email],
        ["Garanție", lm0.j.has_guarantee >= .5], ["Rate", lm0.j.has_installments >= .5], ["Testimoniale", lm0.j.has_testimonials >= .5], ["Date firmă", lm0.j.has_company_id >= .5]]
        .map(([label, v]) => ({label, yes: !!v, no: !v}))}) : null;
  const dimRows = key => (lsum.dims[key] || []).slice(0, 6).map(d => ({label: L(d.value), pct: d.pct + "%", w: d.pct + "%"}));
    const yesPct = key => ((lsum.dims[key] || [])[0] || {}).pct || 0;
    const opt = (key, cur, field) => [{v: "", label: "Toate", on: !cur, off: !!cur, pick: () => set({[key]: "", llimit: PAGE})}].concat(
      countBy(lands, l => l.j[field]).map(([v, n]) => ({v, label: L(v) + " · " + n, on: cur === v, off: cur !== v, pick: () => set({[key]: v, llimit: PAGE})})));

    const meta = RD.meta;
    return {
      ready: true, notReady: false,
      isAds: s.page === "ads", isLand: s.page === "land", goAds: () => { set({page: "ads"}); window.scrollTo(0, 0); }, goLand: () => { set({page: "land"}); window.scrollTo(0, 0); },
      niche: meta.niche, nicheCap: meta.niche.charAt(0).toUpperCase() + meta.niche.slice(1), product: meta.research.product || meta.niche, audienceBrief: meta.research.audience,
      problem: meta.research.problem, collected: date(meta.collected_at), country: COUNTRY[meta.country] || meta.country, keywords: Object.keys(meta.keywords || {}).map(k => ({k})),
      nCollected: fmt(meta.n_collected), nCreatives: fmt(meta.n_creatives), nPlayers: fmt(Object.keys(pm).length),
      kpis: [
        {k: "Reclame analizate", v: fmt(all.length), note: `${fmt(meta.n_collected)} colectate, ${fmt(meta.n_off_niche)} excluse ca fiind în afara nișei`},
        {k: `Rulează de cel puțin ${meta.winner_days} zile`, v: pct(winners, all.length) + "%", note: `${fmt(winners)} reclame considerate câștigătoare`},
        {k: "Reach cumulat în UE", v: short(aud.eu_total), note: `din ${fmt(aud.n_ads)} reclame cu date de audiență`},
        {k: "Durata mediană", v: fmt(medDays) + " zile", note: `de rulare, pe ${fmt(Object.keys(pm).length)} advertiseri`}],
      malePct: (g.male || 0) + "%", femalePct: (g.female || 0) + "%", maleW: pct(g.male, gt) + "%", femaleW: pct(g.female, gt) + "%",
      ages: (aud.ages || []).filter(a => a.age !== "13-17").map(a => ({age: a.age, male: a.male, female: a.female, total: a.male + a.female,
        mW: Math.round(a.male / ageMax * 100) + "%", fW: Math.round(a.female / ageMax * 100) + "%", tW: Math.round((a.male + a.female) / ageMax * 100) + "%"})),
      angles: bar(angles, all.length), hooks: bar(hooks, all.length), awareness: bar(aw, all.length),
      topAngle: angles[0] ? L(angles[0][0]) : "—", topAnglePct: angles[0] ? pct(angles[0][1], all.length) + "%" : "",
      topHook: hooks[0] ? L(hooks[0][0]) : "—",
      players: players.map((p, i) => ({rank: String(i + 1).padStart(2, "0"), name: p.name, ads: p.ads, reach: short(p.reach), days: p.days, w: Math.round(p.reach / pMax * 100) + "%",
        img: p.best && p.best.img, hasImg: !!(p.best && p.best.img), open: () => p.best && set({modal: p.best.id})})),
      // ad list
      q: s.q, onQ: e => set({q: e.target.value, limit: PAGE}),
      bucketChips: chips("buckets", countBy(all, a => a.bucket)), formatChips: chips("formats", countBy(all, a => a.format)),
      angleOpts: [{label: "Toate unghiurile", on: !s.angle, off: !!s.angle, pick: () => set({angle: "", limit: PAGE})}].concat(angles.map(([v, n]) => ({label: L(v), n, on: s.angle === v, off: s.angle !== v, pick: () => set({angle: v, limit: PAGE})}))),
      sorts: [["reach", "Reach"], ["days", "Zile active"], ["per_day", "Reach / zi"], ["recent", "Cele mai noi"], ["variants", "Variante"]].map(([v, label]) => ({label, on: s.sort === v, off: s.sort !== v, pick: () => set({sort: v})})),
      count: fmt(filtered.length), total: fmt(all.length), rows, hasMore: filtered.length > s.limit, empty: !filtered.length,
      showMore: () => set({limit: s.limit + PAGE}), reset: () => set({q: "", buckets: [], formats: [], angle: "", limit: PAGE}),
      modalOpen: !!m, m: m || {}, closeModal: () => set({modal: null}), stop: e => e.stopPropagation(),
      // landings
      lN: fmt(lands.length), lPages: fmt(lsum.n_pages),
      lkpis: [
        {k: "Pagini de destinație", v: fmt(lands.length), note: lands.length ? `${fmt(lsum.n_pages)} pagini unice analizate` : "încă neanalizate: rulează /wizard-landing-review"},
        {k: "Afișează prețul exact", v: yesPct("price_shown") + "%", note: "restul: la cerere, „de la” sau deloc"},
        {k: "Ofertă vizibilă în hero", v: yesPct("offer_in_hero") + "%", note: "ofertă vizibilă fără scroll"},
        {k: "Folosesc testimoniale", v: yesPct("has_testimonials") + "%", note: `garanție: ${yesPct("has_guarantee")}% · urgență: ${yesPct("has_urgency")}%`}],
      ltypes: dimRows("page_type"), lactions: dimRows("main_action"), lprices: dimRows("price_shown"),
      lq: s.lq, onLq: e => set({lq: e.target.value, llimit: PAGE}), ltypeOpts: opt("ltype", s.ltype, "page_type"), lactionOpts: opt("laction", s.laction, "main_action"),
      lsorts: [["days", "Zile active"], ["trust", "Încredere"], ["match", "Potrivire cu reclama"], ["ads", "Nr. reclame"]].map(([v, label]) => ({label, on: s.lsort === v, off: s.lsort !== v, pick: () => set({lsort: v})})),
      lcount: fmt(lf.length), lrows, lhasMore: lf.length > s.llimit, lshowMore: () => set({llimit: s.llimit + PAGE}), lempty: !lf.length,
      lreset: () => set({lq: "", ltype: "", laction: "", llimit: PAGE}),
      lmodalOpen: !!lm, lm: lm || {}, closeLModal: () => set({lmodal: null})
    };
  }

  function mount(c) {
    const go = () => { if (window.RD) { c.forceUpdate(); reveal(); } else setTimeout(go, 60); };
    go();
    c._key = e => { if (e.key === "Escape") c.setState({modal: null, lmodal: null}); };
    window.addEventListener("keydown", c._key);
    c._mo = new MutationObserver(() => reveal()); c._mo.observe(document.body, {childList: true, subtree: true});
  }
  function unmount(c) { window.removeEventListener("keydown", c._key); c._mo && c._mo.disconnect(); }
  const seen = new WeakSet();
  let pending = [], bound = false;
  const show = el => { el.style.opacity = 1; el.style.transform = "none"; };
  function check() {
    const h = window.innerHeight * 0.94;
    pending = pending.filter(el => { if (!el.isConnected) return false; if (el.getBoundingClientRect().top < h) { show(el); return false; } return true; });
  }
  function reveal() {
    if (!bound) { bound = true; window.addEventListener("scroll", check, {passive: true}); window.addEventListener("resize", check); }
    const fresh = [];
    document.querySelectorAll("[data-reveal]").forEach(el => {
      if (seen.has(el)) return; seen.add(el);
      if (el.getBoundingClientRect().top < window.innerHeight) return;
      el.style.opacity = 0; el.style.transform = "translateY(24px)"; el.style.transition = "opacity .8s cubic-bezier(.2,.7,.2,1), transform .8s cubic-bezier(.2,.7,.2,1)";
      fresh.push(el);
    });
    pending = pending.concat(fresh);
    if (fresh.length) setTimeout(() => fresh.forEach(show), 2500);
  }
  window.RL = {initState, vals, mount, unmount};
})();
