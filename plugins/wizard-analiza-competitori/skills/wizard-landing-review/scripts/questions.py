"""What Jev judges on a landing page. This is the only file to edit when changing what gets judged.

State sent with every request (see analyze.py):
    {"research": {"niche", "product", "audience", "problem", "exclude"},
     "ad": {"page_name", "body", "title", "link_description", "cta"},   the longest-running ad that links here
     "landing": {"url", "title", "meta_description",
                 "hero": {"heading", "text", "buttons"},              the first screen, before scrolling
                 "sections": [{"heading", "text", "buttons"}],        the page cut at h1-h3
                 "buttons", "forms", "prices": [{"value", "context"}], "footer"}}
Facts the page states plainly (a form, a phone, WhatsApp, how many prices) are read in
code, not asked. After editing, run: /wizard-landing-review reanalyze <slug>
"""
from typesafe_sdk import Choice, Noul, NoulCriteria, Score

MODEL = "jev-latest"
PAGE = "the landing page in `landing`"

QUESTIONS = {
    "page_type": Choice(
        instructions=f"What kind of page is {PAGE}? Judge from `landing.title`, `landing.hero`, `landing.sections` and `landing.buttons`.",
        criteria={
            "sales_page": {
                "what": "A long page written to sell one product or program directly: headline, benefits, proof, offer and "
                        "repeated order buttons, often with payment on delivery",
                "not_for": "Regular shop product pages with a short description and an add-to-cart button",
            },
            "product_page": {
                "what": "A standard online-shop page for one product: name, price, photos, specifications, add to cart or request an offer",
            },
            "shop_home": {"what": "The home page or a category or listing page of an online shop showing many products"},
            "offer_page": {
                "what": "A page dedicated to one campaign, promotion or offer, with its conditions and one call to action",
                "not_for": "Home pages that merely show a promo banner",
            },
            "lead_funnel": {"what": "A quiz, survey or lead-capture page whose main purpose is to collect contact details, often in steps"},
            "booking": {"what": "A page to book a stay, an appointment or a time slot: dates, availability, a booking form or engine"},
            "webinar": {"what": "A registration page for a webinar, workshop, masterclass or a video sales letter"},
            "service_home": {
                "what": "The home, services or contact page of a local business or service provider (a workshop, clinic, "
                        "installer, agency) describing its services and how to reach it",
            },
            "generic_home": {
                "what": "A brand or company home page not tied to the ad's product or offer: general navigation, many topics",
                "not_for": "Home pages of an online shop (shop_home) or of a local service (service_home)",
            },
            "content": {"what": "A blog post, an article, an advertorial or an informational page"},
            "other": "None of the above, or an error, login, cookie or empty page",
        },
    ),
    "main_action": Choice(
        instructions=f"What is the main action {PAGE} asks the visitor to take? Judge from `landing.hero`, `landing.buttons` and `landing.forms`.",
        criteria={
            "buy": "Add to cart or order the product online",
            "form": "Fill in a form to get an offer, a callback or information",
            "call": "Call a phone number",
            "chat": "Write on WhatsApp, Messenger or a chat",
            "book": "Book a date, an appointment or a stay",
            "register": "Register for an event, a webinar, a course or an account",
            "quiz": "Answer a quiz or a questionnaire",
            "visit": "Come to a shop, showroom or workshop",
            "none": "No clear action is asked",
        },
    ),
    "price_shown": Choice(
        instructions=f"How does {PAGE} show the price of what it sells? Use `landing.prices` and `landing.hero`.",
        criteria={
            "exact": "States an exact price for the main product or offer",
            "from": "Only a starting price such as 'from 99 lei', or a price range",
            "on_request": "Says the price comes on request, after a call or in a personal offer",
            "none": "No price at all",
        },
    ),
    "offer_in_hero": Noul(
        instructions="Does the first screen in `landing.hero` state a concrete offer: a price, a discount, a gift, a bundle, free shipping or a voucher?",
    ),
    "has_guarantee": Noul(instructions=f"Does {PAGE} promise a guarantee, a warranty, a money-back period or free returns?"),
    "has_rating": Noul(
        instructions=f"Does {PAGE} show a rating or a count of reviews, customers or sales as proof?",
        criteria=NoulCriteria(
            true="A concrete number is given, such as '4.8 stars', '310 reviews' or '10,000 customers'",
            false="Only vague claims such as 'thousands of happy customers' without a source, or no proof at all",
        ),
    ),
    "has_testimonials": Noul(instructions=f"Does {PAGE} show written testimonials or reviews from customers, with a name or initials?"),
    "has_urgency": Noul(
        instructions=f"Does {PAGE} give a concrete deadline or a limited stock count?",
        criteria=NoulCriteria(
            true="A date, a countdown, 'until Sunday', 'only 5 left', campaign dates",
            false="Only vague words such as 'limited offer', or nothing",
        ),
    ),
    "has_company_id": Noul(
        instructions="Do `landing.footer` or `landing.sections` give the company's legal identity: a registration number "
                     "(CUI, CIF, J../../..) or a full street address?",
    ),
    "has_anpc": Noul(instructions=f"Does {PAGE} mention ANPC, SAL or SOL, the Romanian consumer-protection and dispute-resolution bodies?"),
    "cash_on_delivery": Noul(instructions=f"Does {PAGE} offer payment on delivery (ramburs, plata la livrare)?"),
    "has_delivery_time": Noul(
        instructions=f"Does {PAGE} promise how fast the product arrives or the work is done, such as 'delivery in 24-48h' or 'ready in 3 days'?",
    ),
    "has_installments": Noul(instructions=f"Does {PAGE} offer payment in installments or financing?"),
    "handles_objections": Noul(instructions=f"Does {PAGE} have an FAQ or explicitly answer doubts a buyer might have before buying?"),
    "promise_specificity": Score(
        instructions="How specific is the main promise in `landing.hero`?",
        criteria=[
            "Generic claims any business could make, such as 'best quality' or 'professional services'",
            "Names the concrete product, service or benefit, but gives no numbers, terms or proof",
            "Names exact numbers, timeframes, models, conditions or results that make the promise checkable",
        ],
    ),
    "cta_clarity": Score(
        instructions="How clear is it what the visitor should do next, judging from `landing.hero` and `landing.buttons`?",
        criteria=[
            "No clear next step, or many competing buttons of equal weight",
            "A next step exists but is generic, such as 'find out more' or 'contact us'",
            "One direct action tied to the offer, such as 'order now with payment on delivery' or 'book your date'",
        ],
    ),
    "trust": Score(
        instructions=f"How much evidence does {PAGE} give that the business is real and reliable: reviews, testimonials, "
                     "guarantees, company details, certifications, years in business, photos of real work?",
        criteria=["Almost none", "Some: one or two kinds of evidence", "A lot, of several different kinds"],
    ),
    "ad_match": Score(
        instructions="How closely does the page in `landing` continue what the ad in `ad` says? Compare the ad with `landing.hero` first.",
        criteria=[
            "Different: the page is about another product, offer or topic than the ad",
            "Related: same business or product category, but the visitor has to look for the specific promise or offer from the ad",
            "Same: the first screen is about exactly the product, promise and offer from the ad",
        ],
    ),
}

CHOICES = [k for k, q in QUESTIONS.items() if isinstance(q, Choice)]
NOULS = [k for k, q in QUESTIONS.items() if isinstance(q, Noul)]
SCORES = [k for k, q in QUESTIONS.items() if isinstance(q, Score)]


def price_pick(prices):
    """Built per page: which of the amounts found in code is the price of the main offer. Code copies the value."""
    return Choice(
        instructions="Which amount in `landing.prices` is the current price of the main product or offer the page sells?",
        criteria={**{f"p{i}": f"{p['value']}: {p['context']}" for i, p in enumerate(prices)},
                  "none": "None of them: they are shipping costs, old crossed-out prices, other products, or no main price is shown"},
    )
