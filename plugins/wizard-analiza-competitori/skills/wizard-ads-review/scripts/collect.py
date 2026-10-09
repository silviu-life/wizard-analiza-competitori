# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""Collect ads for a niche from the Meta Ad Library web UI into ./runs/<slug>/.

Default mode loads ONE results page per keyword (the 30 ads with the most
impressions) and reads the JSON Meta embeds in the HTML. Logged-out sessions get
"Rate limit exceeded" on every pagination call, so --paginate is opt-in (for a
browser profile the user logged into) and stops for good on the first refusal.

--source searchapi reads the same data from SearchAPI.io instead of the browser
(needs SEARCHAPI_API_KEY; one credit per results page and per reach lookup).

Second pass, after analyze.py:  collect.py --reach runs/<slug>
opens the detail view of each ad that matches the research and stores Meta's EU
transparency data (total reach, reach by country, age and gender, declared
targeting, payer). The search results do not carry it, so it costs one view per ad.
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlencode
from urllib.request import Request, urlopen

# Active ads only: an ad that was switched off says nothing about what works today.
SEARCH = ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={cc}"
          "&q={q}&search_type=keyword_unordered&media_type=all{lang}")
JSON_BLOB = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)
COOKIE_BUTTONS = ["Decline optional cookies", "Allow all cookies",
                  "Refuză modulele cookie opționale", "Permite toate modulele cookie"]


def slugify(text):
    ascii_ = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def find_ads(obj, out):
    """Walk any JSON shape and collect the ad nodes (HTML blob and GraphQL pages differ)."""
    if isinstance(obj, dict):
        if "ad_archive_id" in obj and "snapshot" in obj:
            out.append(obj)
            return
        for v in obj.values():
            find_ads(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_ads(v, out)


def real(text):
    """Catalog ads carry templates like {{product.brand}} instead of copy."""
    text = (text or "").strip()
    return "" if "{{" in text else text


def day(ts):
    if isinstance(ts, str):  # SearchAPI sends ISO strings, the site sends unix seconds
        return ts[:10]
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat() if ts else None


def normalize(node, keyword):
    s = node.get("snapshot") or {}
    cards = s.get("cards") or []
    card = cards[0] if cards else {}
    images, videos = s.get("images") or [], s.get("videos") or []
    image_url = next((u for u in [
        # resized first: originals are ~0.5 MB each and the viewer shows cards, not posters
        images and (images[0].get("resized_image_url") or images[0].get("original_image_url")),
        videos and videos[0].get("video_preview_image_url"),
        card.get("resized_image_url") or card.get("original_image_url"),
        card.get("video_preview_image_url"),
    ] if u), None)
    has_video = bool(videos) or bool(card.get("video_sd_url") or card.get("video_hd_url"))
    return {
        "id": str(node["ad_archive_id"]),
        "page_name": s.get("page_name") or node.get("page_name") or "",
        "body": real((s.get("body") or {}).get("text")) or real(card.get("body")),
        "title": real(s.get("title")) or real(card.get("title")),
        "link_description": real(s.get("link_description")) or real(card.get("link_description")),
        "cta": s.get("cta_text") or card.get("cta_text") or "",
        "link_url": s.get("link_url") or card.get("link_url") or "",  # where the button goes, for wizard-landing-review
        "caption": s.get("caption") or card.get("caption") or "",
        "format": "video" if has_video else "carousel" if len(cards) > 1 else "image",
        "display_format": s.get("display_format"),
        "start_date": day(node.get("start_date")),
        "end_date": day(node.get("end_date")),
        "is_active": bool(node.get("is_active")),
        "variants": node.get("collation_count") or 1,
        "platforms": node.get("publisher_platform") or [],
        "image_url": image_url,
        "image": None,
        "library_url": f"https://www.facebook.com/ads/library/?id={node['ad_archive_id']}",
        "keyword": keyword,
    }


def parse_reach(details):
    """EU transparency block of one ad (AdLibraryV3AdDetailsQuery) -> plain counts. None when Meta gives none."""
    det = ((details.get("data") or {}).get("ad_library_main") or {}).get("ad_details") or {}
    eu = (det.get("transparency_by_location") or {}).get("eu_transparency") or {}
    if not eu.get("eu_total_reach"):
        return None
    countries, segments = {}, {}
    for c in eu.get("age_country_gender_reach_breakdown") or []:
        for row in c.get("age_gender_breakdowns") or []:
            seg = segments.setdefault(row["age_range"], {"male": 0, "female": 0, "unknown": 0})
            for g in seg:
                seg[g] += row.get(g) or 0
                countries[c["country"]] = countries.get(c["country"], 0) + (row.get(g) or 0)
    age = eu.get("age_audience") or {}
    payer = ((det.get("aaa_info") or {}).get("payer_beneficiary_data") or [{}])[0]
    return {"eu_total": eu["eu_total_reach"], "countries": countries, "segments": segments,
            "targeting": {"locations": [l["name"] for l in eu.get("location_audience") or [] if not l.get("excluded")],
                          "excluded": [l["name"] for l in eu.get("location_audience") or [] if l.get("excluded")],
                          "gender": eu.get("gender_audience"), "age_min": age.get("min"), "age_max": age.get("max")},
            "payer": payer.get("payer"), "beneficiary": payer.get("beneficiary")}


def searchapi(**params):
    """One SearchAPI.io request = one credit."""
    req = Request("https://www.searchapi.io/api/v1/search?" + urlencode(params),
                  headers={"Authorization": "Bearer " + os.environ["SEARCHAPI_API_KEY"]})
    with urlopen(req, timeout=60) as r:
        return json.load(r)


def collect_keyword_api(keyword, country, language, limit):
    """Same contract as collect_keyword, 30 ads per page and per credit."""
    nodes, token, note = [], None, "limit reached"
    while len(nodes) < limit:
        params = {"engine": "meta_ad_library", "q": keyword, "country": country, "active_status": "active"}
        if language:
            params["content_languages"] = language.lower()
        if token:
            params["next_page_token"] = token
        data = searchapi(**params)
        nodes += data.get("ads") or []
        token = (data.get("pagination") or {}).get("next_page_token")
        if not data.get("ads") or not token:
            note = "no more results"
            break
    return [normalize(n, keyword) for n in nodes[:limit] if n.get("is_active")], f"searchapi, {note}"


def collect_reach(run, source="browser"):
    """One detail view per ad that matches the research, at human pace. Resumable; stops on the first refusal."""
    raw_path = run / "raw.json"
    raw = json.loads(raw_path.read_text())
    wanted = {a["id"] for a in json.loads((run / "ads.json").read_text())["ads"] if a.get("j") and a["in_niche"]}
    todo = [a for a in raw["ads"] if a["id"] in wanted and "reach" not in a]
    print(f"{len(wanted)} ads match the research, {len(todo)} still need reach", flush=True)
    if source == "searchapi":
        for i, ad in enumerate(todo, 1):
            try:
                det = searchapi(engine="meta_ad_library_ad_details", ad_archive_id=ad["id"], country=raw["country"])
            except HTTPError as e:  # out of credits or refused: keep what we have, resume later
                print(f"STOPPED: SearchAPI answered {e.code}. Run the same command later to resume.", file=sys.stderr)
                break
            ad["reach"] = parse_reach({"data": {"ad_library_main": {"ad_details": det}}})
            print(f"  [{i}/{len(todo)}] {ad['page_name']}: {ad['reach'] and ad['reach']['eu_total']}", flush=True)
            raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1))
        return reach_done(raw, wanted, run)

    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
    is_details = lambda r: "/api/graphql" in r.url and "AdLibraryV3AdDetailsQuery" in (r.request.post_data or "")
    misses = 0
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(Path("runs") / ".browser-profile"), headless=False,
            viewport={"width": 1400, "height": 1000}, locale="en-US")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, ad in enumerate(todo, 1):
            try:
                page.goto(ad["library_url"], wait_until="domcontentloaded")
                button = page.locator('[role="dialog"]').last.get_by_text("See ad details", exact=True).first
                button.wait_for(timeout=15000)
                with page.expect_response(is_details, timeout=15000) as info:
                    button.click()
                text = info.value.text()
            except PlaywrightTimeout:
                misses += 1
                print(f"  [{i}/{len(todo)}] {ad['page_name']}: no details view", flush=True)
                if misses >= 3:  # three in a row is a pattern, not bad luck: stop instead of hammering
                    print("STOPPED: details did not open for 3 ads in a row", file=sys.stderr)
                    break
                continue
            if "Rate limit exceeded" in text or '"errors"' in text[:200]:
                print("STOPPED: Meta refused the details request. Run the same command later to resume.", file=sys.stderr)
                break
            misses = 0
            ad["reach"] = parse_reach(json.loads(text.splitlines()[0]))  # None = Meta published no EU reach
            total = ad["reach"] and ad["reach"]["eu_total"]
            print(f"  [{i}/{len(todo)}] {ad['page_name']}: {total}", flush=True)
            raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1))
            time.sleep(5)  # slow on purpose: one tab, human pace
        ctx.close()
    reach_done(raw, wanted, run)


def reach_done(raw, wanted, run):
    done = sum("reach" in a for a in raw["ads"] if a["id"] in wanted)
    print(f"reach known for {done} of {len(wanted)} matching ads")
    print(f"RUN_DIR={run}")


def selfcheck():
    details = {"data": {"ad_library_main": {"ad_details": {
        "aaa_info": {"payer_beneficiary_data": [{"payer": "ACME SRL", "beneficiary": "ACME SRL"}]},
        "transparency_by_location": {"eu_transparency": {
            "eu_total_reach": 30, "gender_audience": "All", "age_audience": {"min": 25, "max": 65},
            "location_audience": [{"name": "Romania", "excluded": False}, {"name": "Italy", "excluded": True}],
            "age_country_gender_reach_breakdown": [
                {"country": "RO", "age_gender_breakdowns": [{"age_range": "25-34", "male": 8, "female": 12, "unknown": None}]},
                {"country": "AT", "age_gender_breakdowns": [{"age_range": "25-34", "male": 4, "female": 6, "unknown": None}]}]}}}}}}
    reach = parse_reach(details)
    assert reach["eu_total"] == 30 and reach["countries"] == {"RO": 20, "AT": 10}, reach
    assert reach["segments"] == {"25-34": {"male": 12, "female": 18, "unknown": 0}}, reach
    assert reach["targeting"]["locations"] == ["Romania"] and reach["targeting"]["excluded"] == ["Italy"], reach
    assert reach["payer"] == "ACME SRL" and parse_reach({"data": {}}) is None
    node = {"ad_archive_id": 1, "is_active": False, "start_date": 1771920000, "end_date": 1773990000,
            "collation_count": None, "snapshot": {
                "page_name": "P", "body": {"text": "{{product.brand}}"}, "title": "{{product.name}}",
                "cards": [{"body": "Real copy", "title": "Real title", "original_image_url": "http://x/i.jpg",
                           "link_url": "https://shop.ro/p"},
                          {"body": "second"}]}}
    ad = normalize(node, "kw")
    assert ad["body"] == "Real copy" and ad["title"] == "Real title" and ad["link_url"] == "https://shop.ro/p", ad
    assert ad["format"] == "carousel" and ad["variants"] == 1 and ad["image_url"] == "http://x/i.jpg", ad
    assert ad["start_date"] == "2026-02-24" and ad["end_date"] == "2026-03-20", ad
    assert day("2026-04-30T07:00:00Z") == "2026-04-30"
    found = []
    find_ads({"a": [{"b": {"node": node}}]}, found)
    assert len(found) == 1
    assert slugify("Suplimente pentru somn ȘĂ") == "suplimente-pentru-somn-sa"
    print("collect selfcheck ok")


def collect_keyword(page, url, keyword, paginate, limit):
    """Returns (ads, note). Never retries a refused pagination call."""
    nodes, state = [], {"limited": False}

    def on_response(r):
        if "/api/graphql" not in r.url:
            return
        name = (parse_qs(r.request.post_data or "").get("fb_api_req_friendly_name") or [""])[0]
        if name != "AdLibrarySearchPaginationQuery":
            return
        try:
            text = r.text()
        except Exception:
            return
        if "Rate limit exceeded" in text:
            state["limited"] = True
            return
        for line in text.splitlines():
            try:
                find_ads(json.loads(line), nodes)
            except ValueError:
                pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(5)
        for label in COOKIE_BUTTONS:
            button = page.get_by_role("button", name=label)
            if button.count():
                button.first.click()
                time.sleep(2)
                break
        if page.locator('input[name="pass"]').count():
            return [], "login wall"
        for _ in range(10):  # a cold first load can take longer than the fixed pause above
            if '"ad_archive_id"' in page.content():
                break
            time.sleep(1)
        for blob in JSON_BLOB.findall(page.content()):
            if '"ad_archive_id"' in blob:
                find_ads(json.loads(blob), nodes)
        note = "first page only"
        while paginate and not state["limited"] and len(nodes) < limit:
            more = page.get_by_text("See more", exact=True)
            if not more.count():
                note = "no more results"
                break
            before = len(nodes)
            more.first.scroll_into_view_if_needed()
            more.first.click()
            time.sleep(6)  # slow on purpose: one tab, human pace
            if len(nodes) == before:
                note = "pagination returned nothing"
                break
            note = "paginated"
        if state["limited"]:
            note = "rate limited by Meta - stopped paginating"
    finally:
        page.remove_listener("response", on_response)
    return [normalize(n, keyword) for n in nodes[:limit] if n.get("is_active")], note


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--niche")
    ap.add_argument("--country", default="RO", help="ISO-2 country code")
    ap.add_argument("--keywords", help="comma separated")
    ap.add_argument("--language", help="ISO-639-1 code, uses Ad Library's own language filter")
    ap.add_argument("--max-per-keyword", type=int, default=150)
    ap.add_argument("--paginate", action="store_true",
                    help="click 'See more' (only works when logged in); stops on the first rate-limit reply")
    ap.add_argument("--source", choices=["browser", "searchapi"], default="browser",
                    help="searchapi: SearchAPI.io instead of the browser, needs SEARCHAPI_API_KEY")
    ap.add_argument("--reach", metavar="RUN_DIR",
                    help="second pass: fetch EU transparency reach for the ads that ads.json marks as matching the research")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    if args.reach:
        return collect_reach(Path(args.reach), args.source)
    if not args.niche or not args.keywords:
        ap.error("--niche and --keywords are required")

    api = args.source == "searchapi"
    if not api:
        from playwright.sync_api import sync_playwright

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    run = Path("runs") / f"{slugify(args.niche)}-{args.country.lower()}"
    (run / "images").mkdir(parents=True, exist_ok=True)
    raw_path = run / "raw.json"
    previous = json.loads(raw_path.read_text()) if raw_path.exists() else {}
    if previous.get("collected_at", "")[:10] != dt.date.today().isoformat():
        previous = {"ads": [], "keywords": {}}  # an older collection may list ads that have since stopped
    ads = {a["id"]: a for a in previous["ads"] if a["is_active"]}  # a same-day re-run adds to the dossier
    notes, rate_limited = dict(previous["keywords"]), False
    lang = f"&content_languages[0]={args.language.lower()}" if args.language else ""

    with (contextlib.nullcontext() if api else sync_playwright()) as pw:
        if not api:
            ctx = pw.chromium.launch_persistent_context(
                str(Path("runs") / ".browser-profile"), headless=False,
                viewport={"width": 1400, "height": 1000}, locale="en-US")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, kw in enumerate(keywords):
            if api:
                found, note = collect_keyword_api(kw, args.country.upper(), args.language, args.max_per_keyword)
            else:
                if i:
                    time.sleep(8)
                url = SEARCH.format(cc=args.country.upper(), q=quote(kw), lang=lang)
                found, note = collect_keyword(page, url, kw, args.paginate and not rate_limited,
                                              args.max_per_keyword)
            rate_limited = rate_limited or note.startswith("rate limited")
            notes[kw] = f"{len(found)} ads ({note})"
            print(f"[{kw}] {notes[kw]}", flush=True)
            for ad in found:
                if ad["id"] in ads:
                    continue
                if ad["image_url"]:  # now, not later: CDN URLs expire
                    try:
                        if api:
                            body = urlopen(ad["image_url"], timeout=20).read()
                        else:
                            resp = ctx.request.get(ad["image_url"], timeout=20000)
                            body = resp.body() if resp.ok else None
                        if body:
                            (run / "images" / f"{ad['id']}.jpg").write_bytes(body)
                            ad["image"] = f"images/{ad['id']}.jpg"
                    except Exception as e:
                        print(f"  image failed for {ad['id']}: {e}", file=sys.stderr)
                ads[ad["id"]] = ad
            raw_path.write_text(json.dumps({  # after every keyword, so a crash keeps what we have
                "niche": args.niche, "country": args.country.upper(), "language": args.language,
                "collected_at": dt.datetime.now().isoformat(timespec="seconds"),
                "keywords": notes, "ads": list(ads.values())}, ensure_ascii=False, indent=1))
        if not api:
            ctx.close()

    if not ads:
        print("NO ADS COLLECTED: " + "; ".join(f"{k}: {v}" for k, v in notes.items()), file=sys.stderr)
        sys.exit(2)
    print(f"{len(ads)} unique ads -> {run}")
    print(f"RUN_DIR={run}")


if __name__ == "__main__":
    main()
