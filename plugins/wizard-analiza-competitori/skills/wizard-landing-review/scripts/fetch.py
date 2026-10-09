# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Visit the landing pages of the matching ads in runs/<slug>/ and save each as structured JSON.

Reads  runs/<slug>/ads.json (made by wizard-ads-review; needs `link_url`, collected since that field exists)
Writes runs/<slug>/landings/<id>.json, one per unique URL, and the index runs/<slug>/landings.json

Each URL is visited once, however many ads point to it. Chat, phone, maps and social
destinations are classified from the URL and never visited. One tab, a pause between
pages, no retries: a page that fails is marked and skipped; re-running the command
tries it again once.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

FOLD = 1000  # px: what a visitor sees before scrolling
MAX_TEXT = 40000  # ponytail: long pages are cut here; judge per section if long pages lose accuracy
THIN = 300  # chars: less visible text than this means a JS shell, a block page or an empty page
TRACKING = {"fbclid", "gclid", "gbraid", "wbraid", "msclkid", "ttclid", "mc_cid", "mc_eid", "_ga"}
COOKIE_OK = re.compile(r"^\s*(accept(ă|a)?( tot| toate| all)?( cookie-urile| cookies)?|sunt de acord|de acord|"
                       r"allow all( cookies)?|permite toate|agree|i agree|ok|am înțeles|got it)\s*$", re.I)

CUR = r"lei|ron|€|eur|euro"
NUM = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRICE = re.compile(rf"(?<![\w.,])(?:(?:{CUR})\s?(?:{NUM})|(?:{NUM})\s?(?:{CUR}))(?!\w)", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+40|0040|0)\s?[237]\d{1,2}[\s.-]?\d{3}[\s.-]?\d{3,4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+\w")

# Runs in the page. Only raw material comes back; the structure is built in Python, where it is tested.
EXTRACT = """() => {
  const clean = t => (t || "").replace(/\\s+/g, " ").trim();
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.opacity !== "0"; };
  const top = e => Math.round(e.getBoundingClientRect().top + scrollY);
  const SKIP = "script,style,noscript,svg,template,iframe,nav,footer";
  const lines = [];
  let last = null;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const p = walker.currentNode.parentElement, text = clean(walker.currentNode.textContent);
    if (!text || !p || p.closest(SKIP) || !vis(p)) continue;
    let block = p;
    while (block.parentElement && block !== document.body && getComputedStyle(block).display.startsWith("inline")) block = block.parentElement;
    if (block === last) { lines[lines.length - 1].text += " " + text; continue; }
    const heading = block.closest("h1,h2,h3");
    lines.push({text, tag: heading ? heading.tagName : block.tagName, top: top(block)});
    last = block;
  }
  const looksLikeButton = e => e.tagName !== "A" || /btn|button|cta/i.test((e.getAttribute("class") || "") + " " + e.id);
  const buttons = [...document.querySelectorAll("button,input[type=submit],input[type=button],[role=button],a")]
    .filter(e => looksLikeButton(e) && !e.closest("nav,footer") && vis(e))
    .map(e => ({text: clean(e.innerText || e.value || e.getAttribute("aria-label")), href: e.href || "", top: top(e)}))
    .filter(b => b.text && b.text.length < 80);
  const forms = [...document.querySelectorAll("form")].filter(vis).map(f => ({
    fields: [...f.querySelectorAll("input,select,textarea")]
      .filter(i => !["hidden", "submit", "button", "search"].includes(i.type) && vis(i))
      .map(i => ({label: clean((i.labels && i.labels[0] && i.labels[0].innerText) || i.getAttribute("aria-label") || i.placeholder),
                  name: i.name, type: i.type || i.tagName.toLowerCase(), required: i.required})),
    submit: clean((f.querySelector("button,[type=submit]") || {}).innerText || (f.querySelector("[type=submit]") || {}).value)
  })).filter(f => f.fields.length);
  return {title: clean(document.title), meta_description: clean((document.querySelector("meta[name=description]") || {}).content),
          lines, buttons, forms, hrefs: [...document.querySelectorAll("a[href]")].map(a => a.href),
          footer: clean([...document.querySelectorAll("footer")].map(f => f.innerText).join(" "))};
}"""


def normalize_url(url):
    """Same page = same URL: unwrap Facebook's redirect, drop tracking parameters and the fragment."""
    u = urlsplit((url or "").strip())
    if u.netloc.endswith("l.facebook.com") and u.path == "/l.php":
        return normalize_url(unquote(dict(parse_qsl(u.query)).get("u", "")))
    query = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    host = u.netloc.lower().removeprefix("www.")  # www.a.ro and a.ro are the same page
    return urlunsplit((u.scheme.lower(), host, u.path or "/", urlencode(query), ""))


def destination_type(url):
    """Where the button goes, decided from the URL alone. Only `web` gets visited."""
    u = urlsplit(url)
    host = u.netloc.lower().removeprefix("www.")
    if u.scheme == "tel":
        return "phone"
    if u.scheme not in ("http", "https") or not host:
        return "no_link"
    if host in ("wa.me", "api.whatsapp.com", "whatsapp.com", "chat.whatsapp.com", "web.whatsapp.com"):
        return "whatsapp"
    if host in ("m.me", "messenger.com") or host.endswith(".messenger.com"):
        return "messenger"
    if host.startswith("maps.") or "/maps" in u.path and host.split(".")[0] == "google" or host == "maps.app.goo.gl":
        return "maps"
    if re.search(r"(^|\.)(facebook\.com|fb\.com|fb\.me|fb\.watch)$", host):
        return "facebook"
    if re.search(r"(^|\.)instagram\.com$", host):
        return "instagram"
    if host in ("apps.apple.com", "play.google.com"):
        return "app_store"
    return "web"


def find_prices(texts):
    """Every amount with a currency, with the words around it. Jev picks the main one; the value is copied from here."""
    out, seen = [], set()
    for text in texts:
        for m in PRICE.finditer(text):
            value = " ".join(m.group().split())
            if value.lower() not in seen:
                seen.add(value.lower())
                out.append({"value": value, "context": text[max(0, m.start() - 60):m.end() + 60].strip()})
    return out[:60]


def find_contacts(texts, hrefs):
    joined = " ".join(texts)
    phones = [h[4:] for h in hrefs if h.startswith("tel:")] + PHONE.findall(joined)
    emails = [h[7:].split("?")[0] for h in hrefs if h.startswith("mailto:")] + EMAIL.findall(joined)
    whatsapp = [h for h in hrefs if destination_type(h) == "whatsapp"]
    phone = lambda x: re.sub(r"^(\+40|0040)", "0", re.sub(r"[\s.()-]", "", x))  # +40 722... and 0722... are one number
    dedupe = lambda xs: list(dict.fromkeys(xs))[:5]
    return {"phones": dedupe(map(phone, phones)), "emails": dedupe(emails), "whatsapp": dedupe(whatsapp)}


def structure(raw, url, final_url):
    """Raw page material -> the JSON Jev reads: first screen, sections cut at h1-h3, buttons, forms, prices, contacts."""
    sections, cur = [], {"heading": "", "text": [], "top": 0}
    for ln in raw["lines"]:
        if ln["tag"] in ("H1", "H2", "H3"):
            sections.append(cur)
            cur = {"heading": ln["text"], "text": [], "top": ln["top"]}
        else:
            cur["text"].append(ln["text"])
    sections = [s for s in sections + [cur] if s["heading"] or s["text"]]
    budget = MAX_TEXT
    for i, s in enumerate(sections):
        end = sections[i + 1]["top"] if i + 1 < len(sections) else float("inf")
        s["buttons"] = list(dict.fromkeys(b["text"] for b in raw["buttons"] if s["top"] <= b["top"] < end))
        s["text"] = "\n".join(s["text"])[:max(budget, 0)]
        budget -= len(s["heading"]) + len(s["text"])
    fold = [ln for ln in raw["lines"] if ln["top"] < FOLD]
    heading = next((ln["text"] for ln in fold if ln["tag"] == "H1"), None) or \
        next((ln["text"] for ln in fold if ln["tag"] in ("H2", "H3")), "")
    all_text = [ln["text"] for ln in raw["lines"]] + [b["text"] for b in raw["buttons"]] + [raw["footer"]]
    return {
        "url": url, "final_url": final_url, "title": raw["title"], "meta_description": raw["meta_description"],
        "hero": {"heading": heading,
                 "text": "\n".join(ln["text"] for ln in fold if ln["text"] != heading)[:1500],
                 "buttons": list(dict.fromkeys(b["text"] for b in raw["buttons"] if b["top"] < FOLD))},
        "sections": [{k: s[k] for k in ("heading", "text", "buttons")} for s in sections if s["text"] or s["buttons"] or s["heading"]],
        "buttons": list({(b["text"], b["href"]): {"text": b["text"], "href": b["href"]} for b in raw["buttons"]}.values())[:60],
        "forms": raw["forms"],
        "prices": find_prices(all_text),
        "contacts": find_contacts(all_text, raw["hrefs"]),
        "footer": raw["footer"][:3000],
    }


def page_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def visit(page, url):
    """One attempt. Returns (structured page, error)."""
    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if resp and resp.status >= 400:
        return None, f"HTTP {resp.status}"
    time.sleep(4)
    button = page.get_by_role("button", name=COOKIE_OK)
    if button.count():
        try:
            button.first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass  # a banner that will not close only adds a line of text
    for _ in range(8):  # lazy sections only render once scrolled into view
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
    page.evaluate("window.scrollTo(0, 0)")
    return structure(page.evaluate(EXTRACT), url, page.url), None


def selfcheck():
    assert normalize_url("https://Shop.ro/p?utm_source=fb&id=3&fbclid=x#top") == "https://shop.ro/p?id=3"
    assert normalize_url("https://l.facebook.com/l.php?u=https%3A%2F%2Fa.ro%2F%3Futm_medium%3Dx&h=1") == "https://a.ro/"
    assert normalize_url("https://a.ro") == "https://a.ro/" == normalize_url("https://www.a.ro/")
    kinds = {"https://wa.me/40711": "whatsapp", "https://m.me/page": "messenger", "tel:+4071": "phone",
             "https://www.google.com/maps/place/x": "maps", "https://maps.app.goo.gl/x": "maps",
             "https://www.facebook.com/page": "facebook", "https://m.facebook.com/x": "facebook",
             "https://instagram.com/x": "instagram", "https://play.google.com/store": "app_store",
             "https://www.google.com/search": "web", "https://shop.ro/p": "web", "": "no_link"}
    for u, kind in kinds.items():
        assert destination_type(u) == kind, (u, destination_type(u))
    prices = [p["value"] for p in find_prices(["Preț 51.335 lei, redus de la 77.363 lei", "doar 59,99 RON azi",
                                               "de la € 22.377 sau 296 €/lună", "Ronaldo 7 ani, 2024 clienți, cod 1234lei5"])]
    assert prices == ["51.335 lei", "77.363 lei", "59,99 RON", "€ 22.377", "296 €"], prices
    c = find_contacts(["Sună la 0722 123 456 sau scrie la office@firma.ro"], ["tel:+40722123456", "https://wa.me/40722123456"])
    assert c == {"phones": ["0722123456"], "emails": ["office@firma.ro"], "whatsapp": ["https://wa.me/40722123456"]}, c
    raw = {"title": "T", "meta_description": "", "footer": "CUI RO123", "hrefs": [], "forms": [],
           "lines": [{"text": "Jacuzzi 5 locuri", "tag": "H1", "top": 100}, {"text": "Doar 9.999 lei", "tag": "P", "top": 200},
                     {"text": "De ce noi", "tag": "H2", "top": 1500}, {"text": "Garanție 2 ani", "tag": "LI", "top": 1600}],
           "buttons": [{"text": "Comandă", "href": "", "top": 300}, {"text": "Comandă", "href": "", "top": 1700}]}
    s = structure(raw, "https://a.ro/", "https://a.ro/")
    assert s["hero"] == {"heading": "Jacuzzi 5 locuri", "text": "Doar 9.999 lei", "buttons": ["Comandă"]}, s["hero"]
    assert [x["heading"] for x in s["sections"]] == ["Jacuzzi 5 locuri", "De ce noi"], s["sections"]
    assert s["sections"][1] == {"heading": "De ce noi", "text": "Garanție 2 ani", "buttons": ["Comandă"]}, s["sections"]
    assert s["prices"][0]["value"] == "9.999 lei" and len(s["buttons"]) == 1, s
    print("fetch selfcheck ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", nargs="?", help="runs/<slug>")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    if not args.run:
        ap.error("run directory is required")

    run = Path(args.run)
    ads = json.loads((run / "ads.json").read_text())["ads"]
    if not any("link_url" in a for a in ads):
        sys.exit(f"{run}/ads.json has no landing URLs: it was collected before wizard-ads-review kept them. "
                 "Collect the niche again with /wizard-ads-review, then run this again.")
    pool = [a for a in ads if a.get("j") and a["in_niche"]]  # same filter as the reach pass
    by_url = {}
    for ad in pool:
        url = normalize_url(ad.get("link_url"))
        by_url.setdefault(url, []).append(ad["id"])

    index_path = run / "landings.json"
    previous = {p["url"]: p for p in json.loads(index_path.read_text())["pages"]} if index_path.exists() else {}
    pages = []
    for url, ids in by_url.items():
        entry = previous.get(url) or {"url": url, "id": page_id(url), "type": destination_type(url)}
        entry["ad_ids"] = ids
        pages.append(entry)
    todo = [p for p in pages if p["type"] == "web" and (p.get("error") or not p.get("file"))]
    print(f"{len(pool)} matching ads -> {len(pages)} destinations "
          f"({sum(p['type'] == 'web' for p in pages)} web pages, {len(todo)} to visit)", flush=True)

    def save():  # after every page, so a crash keeps what we have
        index_path.write_text(json.dumps({"fetched_at": dt.datetime.now().isoformat(timespec="seconds"), "pages": pages},
                                         ensure_ascii=False, indent=1))

    save()
    if todo:
        from playwright.sync_api import sync_playwright
        (run / "landings").mkdir(exist_ok=True)
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(Path("runs") / ".browser-profile"), headless=False,
                viewport={"width": 1400, "height": FOLD}, locale="ro-RO")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for i, entry in enumerate(todo, 1):
                if i > 1:
                    time.sleep(3)  # slow on purpose: one tab, human pace
                try:
                    landing, error = visit(page, entry["url"])
                except Exception as e:
                    landing, error = None, f"{type(e).__name__}: {e}"[:200]
                entry.pop("error", None)
                if error:
                    entry["error"] = error
                else:
                    chars = sum(len(s["heading"]) + len(s["text"]) for s in landing["sections"])
                    entry.update(final_url=landing["final_url"], title=landing["title"], chars=chars, thin=chars < THIN,
                                 file=f"landings/{entry['id']}.json")
                    (run / entry["file"]).write_text(json.dumps(landing, ensure_ascii=False, indent=1))
                print(f"  [{i}/{len(todo)}] {entry['url']}: {error or str(entry['chars']) + ' chars'}", flush=True)
                save()
            ctx.close()

    done = sum(bool(p.get("file")) for p in pages)
    print(f"saved {done} pages, {sum(bool(p.get('error')) for p in pages)} failed, "
          f"{sum(bool(p.get('thin')) for p in pages)} thin")
    print(f"RUN_DIR={run}")


if __name__ == "__main__":
    main()
