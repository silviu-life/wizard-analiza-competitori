# /// script
# requires-python = ">=3.10"
# dependencies = ["typesafe-sdk"]
# ///
"""Judge the saved landing pages with Jev and build runs/<slug>/landings.html.

Reads  runs/<slug>/landings.json, landings/*.json (from fetch.py), ads.json, brief.json
Writes runs/<slug>/landings.json (with judgments), landings-data.js, landings.html
Jev judges the page text; facts the page states plainly (forms, phones, prices found)
are read here, in code.
"""
import argparse
import asyncio
import datetime as dt
import hashlib
import importlib.util
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWER = HERE.parent / "assets" / "viewer.html"
LOW_CONFIDENCE = 0.5

# load_research and pct live in wizard-ads-review; loaded by path because this script is also called analyze
_spec = importlib.util.spec_from_file_location("ads_analyze", HERE.parents[1] / "wizard-ads-review" / "scripts" / "analyze.py")
ads_analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ads_analyze)
pct, load_research, store, pick_judge = ads_analyze.pct, ads_analyze.load_research, ads_analyze.store, ads_analyze.pick_judge


def facts(landing):
    """What the page states plainly. Counted here: Jev is not a counter."""
    c = landing["contacts"]
    return {"has_form": bool(landing["forms"]), "form_fields": max((len(f["fields"]) for f in landing["forms"]), default=0),
            "has_phone": bool(c["phones"]), "has_whatsapp": bool(c["whatsapp"]), "has_email": bool(c["emails"]),
            "n_prices": len(landing["prices"])}


def for_jev(landing):
    """The page without what only code needs (hrefs, contacts)."""
    out = {k: landing[k] for k in ("url", "title", "meta_description", "hero", "sections", "forms", "footer")}
    out["buttons"] = [b["text"] for b in landing["buttons"]]
    out["prices"] = landing["prices"]
    return out


def summarize(pages, choice_ids, noul_ids, fact_ids):
    """Share of judged web pages per answer, in percent."""
    pool = [p for p in pages if p.get("j")]
    dims = {}
    for qid in choice_ids:
        n = Counter(p["j"][qid] for p in pool)
        dims[qid] = sorted(({"value": v, "pct": pct(k, len(pool))} for v, k in n.items()), key=lambda r: -r["pct"])
    for qid in noul_ids:
        dims[qid] = [{"value": "yes", "pct": pct(sum(p["j"][qid] >= 0.5 for p in pool), len(pool))}]
    for f in fact_ids:
        dims[f] = [{"value": "yes", "pct": pct(sum(bool(p["facts"][f]) for p in pool), len(pool))}]
    return {"n_pages": len(pool), "destinations": dict(Counter(p["type"] for p in pages)), "dims": dims}


def store_price(page, pick, prices):
    """The main price is copied from the amounts found in code, never generated."""
    i = int(pick[1:]) if pick.startswith("p") and pick[1:].isdigit() else -1
    page["price"] = prices[i]["value"] if 0 <= i < len(prices) else None


async def judge_all(pages, concurrency, judge="jev", batch=8):
    from questions import MODEL, QUESTIONS, price_pick

    if judge != "jev":  # no TypeSafe key: Claude Code judges `batch` pages per call
        n = max(len(state["landing"]["prices"]) for _, state in pages)
        # one schema for the whole batch, so price_pick names positions in `landing.prices`, not amounts
        questions = {**QUESTIONS, "price_pick": price_pick([{"value": f"landing.prices[{i}]", "context": "see that entry"}
                                                             for i in range(n)])}
        got = await ads_analyze.claude_judge(list(enumerate(state for _, state in pages)), questions,
                                             judge.split(":", 1)[1], batch=batch, concurrency=concurrency)
        for i, (page, state) in enumerate(pages):
            if i not in got:
                page["jev_error"] = "claude: no answer"
                continue
            store(page, got[i], QUESTIONS)
            store_price(page, got[i]["price_pick"].choice, state["landing"]["prices"])
        return len(pages) - len(got)

    from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy, TypeSafeAuthenticationError
    sem, failed = asyncio.Semaphore(concurrency), 0

    async def one(client, page, state):
        nonlocal failed
        prices = state["landing"]["prices"]
        questions = {**QUESTIONS, "price_pick": price_pick(prices)} if prices else QUESTIONS
        async with sem:
            try:
                answers = (await client.system_one(state=state, questions=questions, model=MODEL)).answers
            except TypeSafeAuthenticationError:
                raise
            except Exception as e:  # one bad page must not lose the batch
                failed += 1
                page["jev_error"] = f"{type(e).__name__}: {e}"[:200]
                return
        store(page, answers, QUESTIONS)
        store_price(page, answers["price_pick"].choice if prices else "none", prices)

    async with AsyncTypeSafeClient(retry=RetryPolicy(max_retries=3)) as client:
        await asyncio.gather(*(one(client, page, state) for page, state in pages))
    return failed


def selfcheck():
    landing = {"contacts": {"phones": ["0722"], "emails": [], "whatsapp": []}, "prices": [{"value": "9 lei", "context": ""}],
               "forms": [{"fields": [1, 2, 3], "submit": ""}, {"fields": [1], "submit": ""}]}
    assert facts(landing) == {"has_form": True, "form_fields": 3, "has_phone": True, "has_whatsapp": False,
                              "has_email": False, "n_prices": 1}
    pages = [{"type": "web", "j": {"page_type": "sales_page", "has_rating": 0.9}, "facts": {"has_form": True}},
             {"type": "web", "j": {"page_type": "sales_page", "has_rating": 0.2}, "facts": {"has_form": False}},
             {"type": "web", "j": {"page_type": "booking", "has_rating": 0.6}, "facts": {"has_form": False}},
             {"type": "whatsapp"}]
    s = summarize(pages, ["page_type"], ["has_rating"], ["has_form"])
    assert s["n_pages"] == 3 and s["destinations"] == {"web": 3, "whatsapp": 1}, s
    assert s["dims"]["page_type"][0] == {"value": "sales_page", "pct": 67}, s
    assert s["dims"]["has_rating"] == [{"value": "yes", "pct": 67}] and s["dims"]["has_form"] == [{"value": "yes", "pct": 33}], s
    prices = [{"value": "9 lei", "context": ""}, {"value": "19 lei", "context": ""}]
    for pick, want in (("p1", "19 lei"), ("p5", None), ("none", None), ("px", None)):
        page = {}
        store_price(page, pick, prices)
        assert page["price"] == want, (pick, page)
    print("analyze selfcheck ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", nargs="?", help="runs/<slug>")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--skip-jev", action="store_true", help="build the page with the facts read in code only")
    ap.add_argument("--claude-model", default=ads_analyze.CLAUDE_MODEL, help="model for `claude -p` when TYPESAFE_API_KEY is not set")
    ap.add_argument("--batch", type=int, default=8, help="pages per `claude -p` call (pages are long)")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    if not args.run:
        ap.error("run directory is required")
    from questions import CHOICES, NOULS, QUESTIONS, SCORES

    run = Path(args.run)
    index_path = run / "landings.json"
    if not index_path.exists():
        sys.exit(f"{index_path} is missing: run fetch.py on {run} first")
    index = json.loads(index_path.read_text())
    dossier = json.loads((run / "ads.json").read_text())
    ads = {i: a for a in dossier["ads"] for i in a.get("grouped_ids") or [a["id"]]}
    research = load_research(run, dossier["meta"]["niche"])
    judge = pick_judge(args.claude_model)
    qhash = hashlib.sha1((repr(QUESTIONS) + json.dumps(research, sort_keys=True) + str(judge)).encode()).hexdigest()[:12]
    if index.get("questions_hash") != qhash:  # questions, brief or judge changed: judge everything again
        for p in index["pages"]:
            p.pop("j", None)

    todo, bodies = [], {}
    for p in index["pages"]:
        linked = sorted((ads[i] for i in p["ad_ids"] if i in ads), key=lambda a: -a["days"])
        p["ads"] = [{k: a.get(k) for k in ("id", "page_name", "days", "bucket", "hook", "library_url")} for a in linked]
        p["max_days"] = linked[0]["days"] if linked else 0
        if not p.get("file") or p.get("error"):
            continue
        text = (run / p["file"]).read_text()
        landing = json.loads(text)
        bodies[p["id"]] = landing
        p["facts"] = facts(landing)
        content = hashlib.sha1((text + json.dumps(p["ads"][:1])).encode()).hexdigest()[:12]
        if p.get("j") and p.get("content_hash") == content:
            continue
        p.pop("j", None)
        p["content_hash"] = content
        ad = linked[0] if linked else {}
        state = {"research": research, "landing": for_jev(landing),
                 "ad": {k: ad.get(k, "") for k in ("page_name", "body", "title", "link_description", "cta")}}
        todo.append((p, state))

    failed = 0
    if args.skip_jev:
        print(f"--skip-jev: {len(todo)} pages left unjudged")
    elif todo:
        if not judge:
            sys.exit("TYPESAFE_API_KEY is not set and Claude Code (`claude`) is not installed. Put the key in .env and run "
                     "with: uv run --env-file .env ... (or pass --skip-jev for a facts-only page)")
        print(f"judging {len(todo)} pages with {judge} ({sum(bool(p.get('j')) for p in index['pages'])} cached)...", flush=True)
        failed = asyncio.run(judge_all(todo, args.concurrency, judge, args.batch))
    for p in index["pages"]:
        if p.get("j"):
            p["unsure"] = [q for q, c in p["conf"].items() if c < LOW_CONFIDENCE]

    pages = sorted(index["pages"], key=lambda p: (p["type"] != "web", -len(p["ad_ids"]), -p["max_days"]))
    fact_ids = ["has_form", "has_phone", "has_whatsapp", "has_email"]
    summary = summarize(pages, CHOICES, NOULS, fact_ids)
    meta = {"niche": dossier["meta"]["niche"], "country": dossier["meta"]["country"], "research": research,
            "fetched_at": index["fetched_at"], "analyzed_at": dt.datetime.now().isoformat(timespec="seconds"), "judge": judge,
            "n_ads": sum(len(p["ad_ids"]) for p in pages), "n_destinations": len(pages),
            "n_web": sum(p["type"] == "web" for p in pages), "n_saved": len(bodies),
            "n_judged": summary["n_pages"], "n_failed": failed,
            "dims": {"choices": CHOICES, "nouls": NOULS, "scores": SCORES, "facts": fact_ids}}
    index.update(questions_hash=qhash, pages=pages)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    view = [dict(p, landing=bodies.get(p["id"])) for p in pages]
    # a <script src>, not fetch(): fetch is blocked on file://
    dump = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    (run / "landings-data.js").write_text(
        f"window.META={dump(meta)};\nwindow.SUMMARY={dump(summary)};\nwindow.LANDINGS={dump(view)};\n")
    shutil.copyfile(VIEWER, run / "landings.html")

    print(f"{meta['n_ads']} ads -> {meta['n_destinations']} destinations, {meta['n_web']} web | saved {meta['n_saved']} | "
          f"judged {meta['n_judged']} | failed {failed} | {summary['destinations']}")
    print(f"DOSSIER={run / 'landings.html'}")


if __name__ == "__main__":
    main()
