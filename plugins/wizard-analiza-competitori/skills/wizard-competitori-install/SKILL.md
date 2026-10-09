---
name: wizard-competitori-install
description: Instalează pas cu pas tot ce le trebuie skill-urilor wizard-ads-review și wizard-landing-review (uv, Python, bibliotecile proiectului, Chromium pentru Playwright, fișierul .env). Explică pe înțelesul unui om fără cunoștințe tehnice ce instalează și de ce, și instalează fiecare componentă doar după ce userul spune „da”. Se activează la /wizard-competitori-install, „instalează ce trebuie”, „pregătește proiectul”, „de ce am nevoie ca să meargă”, „nu-mi merge ads-review, lipsește ceva”.
---

# wizard-competitori-install

Pregătește calculatorul ca să meargă `/wizard-ads-review` și `/wizard-landing-review`. Rulează totul din folderul în care lucrează userul (acolo vor apărea `runs/` și `.env`). Mai jos, `<skill>` e directorul de bază al acestui skill, afișat la încărcare; celelalte două skill-uri sunt alături, în `<skill>/..`.

Userul probabil nu e tehnic. Vorbește simplu, fără jargon; când un termen tehnic e inevitabil, explică-l într-o paranteză. Fraze scurte.

## Regula de aur: nimic fără acord

Pentru **fiecare** componentă din tabelul de mai jos, în ordine, una câte una:

1. **Verifică** dacă e deja instalată, cu comanda din coloana „Verificare”. Dacă da, scrie „✓ <componentă> e deja instalat” și treci la următoarea, fără nicio întrebare.
2. **Explică**, în 3–5 rânduri: ce este, de ce are nevoie proiectul de ea, ce comandă vei rula (arat-o), cam cât durează și cât ocupă, și că se poate dezinstala oricând.
3. **Întreabă cu `AskUserQuestion`**: întrebarea „Instalez <componentă>?”, opțiunile „Da, instalează” și „Nu, sar peste”. Câte o întrebare per componentă, niciodată mai multe deodată.
4. La „Da”: rulează comanda, apoi verifică din nou și spune pe scurt rezultatul. La eroare, explică pe înțeles ce s-a întâmplat și ce poate face userul; nu reîncerca în buclă.
   La „Nu” (sau orice alt răspuns): nu rula nimic; spune într-un rând ce nu va merge fără ea și treci mai departe.

Nu instala nimic în afara tabelului. Nu rula niciodată `sudo`: când e nevoie, îi dai userului comanda s-o scrie el, cu `!` în față, ca să-și pună singur parola.

## Înainte de toate: ce sistem e

`uname -s` și, pe Linux, `grep -qi microsoft /proc/version` (WSL = Linux în Windows). Spune-i userului într-un rând ce ai găsit („Ești pe Windows, în WSL”). Pe Windows fără WSL, comenzile din tabel au varianta de PowerShell indicată.

## Componentele, în ordine

| # | Componentă | Ce îi spui userului | Verificare | Instalare |
|---|---|---|---|---|
| 1 | **uv** | Un program mic care descarcă și pornește Python și bibliotecile de care au nevoie scripturile, fără să le amestece cu restul calculatorului. ~30 MB. | `uv --version` | Linux / macOS / WSL: `curl -LsSf https://astral.sh/uv/install.sh \| sh`, apoi `source $HOME/.local/bin/env`. Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| 2 | **Python 3.10+** | Limbajul în care sunt scrise scripturile. uv îl pune într-un folder separat; nu atinge Python-ul sistemului. ~50 MB. | `uv python find ">=3.10"` | `uv python install 3.12` |
| 3 | **Bibliotecile proiectului** (playwright, typesafe-sdk) | Piesele de cod folosite de scripturi: una controlează browserul, cealaltă vorbește cu Jev. Se descarcă o dată și se păstrează. Rulez și verificările proiectului, ca să știm că merg. ~60 MB. | — (mereu se întreabă, dacă 1 și 2 sunt instalate) | cele patru verificări: `uv run <skill>/../wizard-ads-review/scripts/collect.py --selfcheck`, `uv run <skill>/../wizard-ads-review/scripts/analyze.py --selfcheck`, `uv run <skill>/../wizard-landing-review/scripts/fetch.py --selfcheck`, `uv run <skill>/../wizard-landing-review/scripts/analyze.py --selfcheck`. Fiecare trebuie să scrie „selfcheck ok”. |
| 4 | **Chromium pentru Playwright** | Un browser separat, pe care scripturile îl deschid singure ca să citească Meta Ad Library și paginile concurenței. Nu atinge Chrome-ul tău, istoricul sau parolele. ~150 MB, 1–2 minute. | `uv run --with playwright python -c "from playwright.sync_api import sync_playwright as p; pw=p().start(); pw.chromium.launch().close(); pw.stop()"` | `uv run --with playwright playwright install chromium` |
| 5 | **Librăriile de sistem pentru Chromium** — doar pe Linux/WSL și doar dacă verificarea de la 4 pică și după instalare (eroare cu „missing dependencies” / „shared libraries”) | Câteva piese ale sistemului de care browserul are nevoie ca să pornească. Cer parola calculatorului, de aceea comanda o scrii tu. | aceeași ca la 4 | Nu o rulezi tu. Îi dai userului să scrie: `! sudo $(which uv) run --with playwright playwright install-deps chromium`. După ce confirmă, refă verificarea de la 4. |
| 6 | **Fișierul `.env`** | Un fișier text, doar pe calculatorul tău, unde se pun cheile (parole pentru servicii). Ambele chei sunt opționale: fără TypeSafe, textele le judecă Claude Code; SearchAPI e doar pentru colectarea fără browser. | `test -f .env` (doar dacă există; nu-l citi și nu-l afișa) | `cp <skill>/assets/env.example .env` |

După pasul 6, dacă userul are chei: spune-i să deschidă `.env` în editorul lui și să le completeze acolo, nu în chat. Dacă totuși lipește o cheie în chat, scrie-o tu în `.env` (fără s-o afișezi) și spune-i s-o regenereze.

## Final

Un tabel scurt cu fiecare componentă: ✓ instalată / ✗ sărită. Pentru cele sărite, ce nu merge din cauza lor:
- fără uv sau Python: nimic nu merge;
- fără Chromium: nu merge colectarea prin browser și nici `/wizard-landing-review`; colectarea merge doar cu SearchAPI (cheie, cu credite);
- fără `.env`: totul merge, doar că nu se folosesc cheile.

Apoi pasul următor: „Scrie `/wizard-ads-review <nișa ta>`, de exemplu `/wizard-ads-review suplimente pentru somn`.”
