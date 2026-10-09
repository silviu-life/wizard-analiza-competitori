"""The Jev taxonomy. This is the only file to edit when changing what gets judged.

State sent with every request (see analyze.py):
    {"research": {"niche", "product", "audience", "problem", "exclude"},
     "ad": {"page_name", "hook", "body", "title", "link_description", "cta"}}
`research` is runs/<slug>/brief.json (only `niche` when there is no brief).
`ad.hook` is the opening sentence of the copy, cut out in code so hook_type judges
exactly that and not the whole text. After editing, run: /wizard-ads-review reanalyze <slug>
"""
from typesafe_sdk import Choice, Noul, NoulCriteria, Score

MODEL = "jev-latest"
AD = "the ad copy in `ad.body`, `ad.title` and `ad.link_description`"

QUESTIONS = {
    "fit": Choice(
        instructions="We are researching ads for the business described in `research`. How does this ad relate to that research?",
        criteria={
            "direct": {
                "what": "The ad sells the same type of product as `research.product`, for the same problem: a direct competitor",
                "not_for": "Shops that merely stock such a product among many others without featuring it",
            },
            "adjacent": {
                "what": "The ad targets the same problem or the same audience as `research`, but sells a different kind "
                        "of solution. Its hooks and angles are still useful to study.",
                "examples": ["research is a sleep supplement; the ad sells a sleep app or a calming oil",
                             "research is an AI course; the ad sells an AI tool, a coaching program or a different kind of course to the same people"],
            },
            "store_wide": {
                "what": "A generic shop, marketplace, platform or brand ad: many products or no specific one, a site-wide "
                        "sale, an abandoned-cart reminder or a page-like request. Not written for this problem.",
            },
            "unrelated": {
                "what": "Sells something for a different problem and audience, shares at most a keyword with `research`, "
                        "or matches something listed in `research.exclude`",
            },
        },
    ),
    "language": Choice(
        instructions=f"In which language is {AD} written?",
        criteria={
            "ro": "Romanian", "en": "English", "hu": "Hungarian", "de": "German", "fr": "French",
            "it": "Italian", "es": "Spanish", "pl": "Polish", "bg": "Bulgarian", "ru": "Russian",
            "uk": "Ukrainian", "tr": "Turkish", "nl": "Dutch", "pt": "Portuguese", "el": "Greek",
            "mixed": "Two or more languages each carry a substantial part of the copy",
            "other": "A language not listed here",
        },
    ),
    "awareness": Choice(
        instructions=f"Which stage of customer awareness (Eugene Schwartz) is {AD} written for?",
        criteria={
            "unaware": {
                "what": "Reader does not know they have a problem. The ad opens with a story, an identity or "
                        "a surprising fact and does not name the problem or the product early.",
                "not_for": "Ads that name a pain or symptom up front",
            },
            "problem_aware": {
                "what": "Reader feels the problem but does not know solutions exist. The ad names and agitates "
                        "the pain or symptom first, then reveals that a solution exists.",
                "examples": ["Can't fall asleep for hours? Here is why.", "Still doing this by hand every week?"],
            },
            "solution_aware": {
                "what": "Reader knows the kind of solution they want but not this product. The ad argues why "
                        "this type of product, ingredient or mechanism is the better way to get the result.",
                "not_for": "Ads that assume the reader already knows the brand",
            },
            "product_aware": {
                "what": "Reader knows this product but is not convinced. The ad gives proof, reviews, "
                        "comparisons, answers to objections or details about the product itself.",
            },
            "most_aware": {
                "what": "Reader already wants the product and only needs a deal. The ad is mostly the offer: "
                        "price, discount, bundle, deadline, free shipping, 'buy now'.",
            },
        },
    ),
    "hook_type": Choice(
        instructions="What kind of hook is the opening line in `ad.hook`? Judge only `ad.hook`, not the rest of the ad.",
        criteria={
            "question": "Opens by asking the reader a question",
            "bold_claim": "Opens with a strong, surprising or contrarian statement presented as fact",
            "pain_point": "Opens by describing a problem, symptom or frustration the reader has (not phrased as a question)",
            "personal_story": "Opens as a first-person story or anecdote from the advertiser or founder",
            "testimonial": "Opens with a customer's words, review or result",
            "statistic": "Opens with a number, percentage or study result as the main attention device",
            "curiosity_gap": "Opens by teasing a secret, a reason or a discovery without revealing it",
            "offer": "Opens with a discount, price, gift, free shipping or a limited-time deal",
            "audience_callout": "Opens by naming who the ad is for, such as 'Moms over 40' or 'Attention runners'",
            "how_to": "Opens by promising instructions, tips or a method",
            "news": "Opens by announcing something new: a launch, a new product, back in stock",
            "warning": "Opens with a warning, a danger or a mistake to avoid",
            "product_name": "Opens by simply naming or describing the product, with no attention device",
            "other": "None of the above fits",
        },
    ),
    "voice": Choice(
        instructions=f"From whose perspective is {AD} written?",
        criteria={
            "brand": "The company speaks as 'we' or in a neutral brand voice about its product",
            "founder": "The founder or owner speaks personally as 'I' about why or how they made it",
            "customer": "A customer speaks in first person about their own experience or result",
            "expert": "A doctor, specialist or other authority explains or recommends",
            "editorial": "Written like a news article or advertorial by a seemingly independent third party",
            "ugc_creator": "A creator or influencer casually shows or reviews the product, as in a social post",
        },
    ),
    "angle": Choice(
        instructions=f"What is the main persuasion angle of {AD}: the single strongest reason it gives to act?",
        criteria={
            "pain_relief": "Getting rid of a pain, symptom or frustration",
            "transformation": "Becoming a better version of yourself or reaching a desired outcome",
            "social_proof": "Many others use it, love it or got results",
            "authority": "Experts, studies, certifications or awards back it",
            "unique_mechanism": "A specific ingredient, technology or method explains why it works where others fail",
            "price_value": "A good deal: discount, bundle, low price or more for the money",
            "convenience": "It is easy, fast or effortless to use or to get",
            "vs_alternatives": "It is better than a named or implied alternative",
            "identity": "It is for people like you; belonging to a group or lifestyle",
            "urgency": "Act now because time or stock is limited",
            "other": "None of the above is the main reason",
        },
    ),
    "emotion": Choice(
        instructions=f"Which emotion does {AD} mainly try to evoke in the reader?",
        criteria={
            "fear": "Worry about a risk, a health consequence or missing out",
            "frustration": "Being fed up with a problem that will not go away",
            "hope": "Relief and optimism that things can get better",
            "curiosity": "Wanting to find out something intriguing",
            "belonging": "Feeling understood or part of a group",
            "status": "Pride, confidence or being admired",
            "guilt": "Feeling one should be doing better for oneself or others",
            "humor": "Amusement or playfulness",
            "neutral": "Informational, no clear emotional pull",
        },
    ),
    "structure": Choice(
        instructions=f"Which copywriting structure does {AD} follow?",
        criteria={
            "pas": "Names a problem, makes it feel worse, then presents the solution",
            "aida": "Grabs attention, builds interest with information, creates desire, then asks for action",
            "story_to_offer": "Tells a narrative and ends with the product or offer",
            "benefit_list": "Mostly a list of benefits or features, often with bullets, checkmarks or emoji",
            "testimonial": "Mostly one or more customer quotes or reviews",
            "one_liner": "One or two short sentences and nothing else",
            "advertorial": "Long article-like text that educates before selling",
            "offer_only": "Just the deal: product, price or discount, and a call to action",
            "other": "None of the above fits",
        },
    ),
    "has_offer": Noul(instructions=f"Does {AD} mention a discount, a special price, a gift, a bundle deal or free shipping?"),
    "has_urgency": Noul(instructions=f"Does {AD} say that time or stock is limited, such as a deadline, 'today only' or 'while stocks last'?"),
    "has_social_proof_numbers": Noul(
        instructions=f"Does {AD} cite a number of customers, reviews, ratings or units sold as proof?",
        criteria=NoulCriteria(
            true="A concrete count or rating is given, such as '10,000 customers' or '4.8 stars'",
            false="Only vague proof such as 'loved by many', or no proof at all",
        ),
    ),
    "has_guarantee": Noul(instructions=f"Does {AD} promise a guarantee, a money-back period or free returns?"),
    "handles_objection": Noul(
        instructions=f"Does {AD} explicitly answer a doubt a buyer might have, such as side effects, price, whether it really works, or difficulty of use?",
    ),
    "has_numeric_promise": Noul(
        instructions=f"Does {AD} promise a result with a specific number or timeframe, such as 'fall asleep in 20 minutes', 'lose 5 kg' or 'build your first app in 7 days'?",
    ),
    "specificity": Score(
        instructions=f"How specific are the claims in {AD}?",
        criteria=[
            "Generic claims any brand could make, such as 'best quality' or 'feel better'",
            "Names concrete benefits or product details, but gives no numbers, ingredients or proof",
            "Names exact ingredients, amounts, numbers, timeframes or mechanisms that make the claims checkable",
        ],
    ),
    "emotional_intensity": Score(
        instructions=f"How emotionally charged is the language of {AD}?",
        criteria=[
            "Flat and factual, like a product listing",
            "Some warm or persuasive wording, but mostly calm",
            "Vivid emotional language: describes feelings and struggles, uses exclamations or dramatic wording",
        ],
    ),
    "cta_clarity": Score(
        instructions=f"How clearly does {AD} tell the reader what to do next?",
        criteria=[
            "No call to action in the text",
            "A generic call to action such as 'find out more' or only a link",
            "A direct instruction tied to a reason, such as 'order today and get 20% off'",
        ],
    ),
}

CHOICES = [k for k, q in QUESTIONS.items() if isinstance(q, Choice)]
NOULS = [k for k, q in QUESTIONS.items() if isinstance(q, Noul)]
SCORES = [k for k, q in QUESTIONS.items() if isinstance(q, Score)]
