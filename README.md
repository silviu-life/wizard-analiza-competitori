# wizard-analiza-competitori

Un plugin pentru [Claude Code](https://claude.com/claude-code) care îți arată ce reclame ține pornite competiția pe Meta și de ce ar putea merge.

Pornești de la o nișă („cursuri AI”, „suplimente pentru somn”). Skill-ul adună reclamele **active** din Meta Ad Library, verifică pe fiecare dacă se potrivește cu afacerea ta, îi analizează textul (hook, nivel de conștientizare, unghi, emoție, structură), adaugă reach-ul din UE pe țări, vârstă și gen și îți lasă un dosar local cu o pagină HTML cu filtre.

Ideea de bază: o reclamă activă pe care o companie o ține pornită de săptămâni întregi e, cel mai probabil, una care aduce bani. Zilele de rulare spun că reclama e ținută pornită; reach-ul pe zi spune câți bani se bagă în ea.

## Instalare

În Claude Code, o singură dată:

```
/plugin marketplace add silviu-life/wizard-analiza-competitori
/plugin install wizard-analiza-competitori@wizard-analiza-competitori
```

Apoi, în folderul în care vrei să lucrezi (acolo apar `runs/` și `.env`), scrie `/wizard-competitori-install`. Îți explică pe rând ce trebuie instalat (uv, Python, Chromium pentru Playwright, fișierul `.env`) și de ce, și instalează doar ce aprobi.

Cheile sunt opționale și se pun în `.env`, nu în chat:
- TypeSafe, pentru Jev, modelul care judecă textele. Fără ea judecă Claude Code, din abonamentul tău Claude.
- [SearchAPI.io](https://www.searchapi.io), pentru colectare fără browser și mai mult de 30 de reclame per cuvânt-cheie.

Actualizare: `/plugin marketplace update wizard-analiza-competitori`.

## Folosire

În Claude Code:

```
/wizard-ads-review cursuri AI
/wizard-ads-review <nișă> [țară] [limbă]     fluxul complet (implicit RO, limba pieței)
/wizard-ads-review reanalyze <slug>          rejudecă un dosar existent, fără colectare
/wizard-ads-review list                      dosarele din runs/
```

Claude îți propune cuvintele-cheie, colectează, îți pune patru întrebări despre afacere (ce vinzi, cui, ce problemă rezolvi, ce să excludă), apoi analizează și îți dă un raport: tiparele reclamelor care rulează de mult, primele după reach pe zi și după zile de rulare, cine le vede și trei idei de testat. Dacă ai deja un document de cercetare, dă-i-l și își extrage răspunsurile de acolo.

## Ce primești

Totul ajunge în `runs/<nișă>-<țară>/` (o rulare nouă pe aceeași nișă și țară suprascrie reclamele, păstrează `brief.json`):

| Fișier | Ce e |
|---|---|
| `index.html` | pagina cu filtre; se deschide cu dublu-click |
| `ads.json` | aceleași date, pentru Claude sau pentru alte scripturi |
| `raw.json` | ce s-a colectat, înainte de analiză |
| `brief.json` | descrierea afacerii tale, față de care se judecă potrivirea |
| `images/` | imaginile reclamelor |

Categorii după durată: **winner** (cel puțin 14 zile), **promițător** (7-13), **prea nou** (sub 7).

## Paginile de landing: `/wizard-landing-review`

Al doilea skill, `wizard-landing-review`, pornește de la un dosar făcut de `/wizard-ads-review`. Deschide în browser paginile la care duc reclamele potrivite, câte o dată pe fiecare URL. Transformă fiecare pagină într-un JSON cu primul ecran, secțiuni, butoane, formulare, prețuri și contacte, apoi Jev o judecă: tipul paginii, ce i se cere vizitatorului, prețul, garanția, recenziile, urgența, datele de firmă și cât de bine continuă reclama.

```
/wizard-landing-review jacuzzi-ro            fluxul complet pe runs/jacuzzi-ro
/wizard-landing-review reanalyze <slug>      rejudecă paginile deja salvate
```

Adaugă în dosar `landings.html` (pagina cu filtre), `landings.json` și `landings/`, cu câte un JSON pe pagină. Dosarele colectate înainte de acest skill nu au URL-ul paginii de landing, așa că trebuie colectate din nou cu `/wizard-ads-review`.

## Două surse de date

**Browser (implicit, gratuit).** Deschide o fereastră și citește Ad Library ca un vizitator nelogat. Meta dă astfel doar prima pagină per căutare: cele 30 de reclame cu cele mai multe impresii. Reach-ul se cere separat, cam 20 de secunde per reclamă potrivită. Dacă Meta începe să refuze browserul (pagină goală), nu insista; treci pe a doua sursă.

**SearchAPI.io (`--source searchapi`, cu credite).** Fără browser, cu paginare. Un credit per pagină de 30 de reclame și un credit per reclamă la reach; contul nou vine cu 100 de credite gratuite. Cere-i lui Claude „folosește SearchAPI” și spune-i câte reclame per cuvânt-cheie vrei; îți spune costul înainte.

Opțiuni utile la analiză: `--no-group` (o fișă per reclamă, nu una per text; vezi separat variantele cu alt titlu sau alt format), `--winner-days`, `--promising-days`.

## Limite, pe scurt

- Vezi doar reclame active, deci nu știi ce s-a încercat și a fost oprit. Tiparele sunt descrieri, nu dovezi.
- Reach-ul arată unde se duce bugetul, nu cât costă un lead.
- Skill-ul nu ocolește limitele Meta: fără proxy-uri, fără profiluri rotite, fără reîncercări în buclă. Pentru acoperire completă pe cale oficială există API-ul Ad Library (cere confirmarea identității la Meta).
- Cheile nu se lipesc în chat. Le pui în `.env`.

## Dezvoltare

Codul e în `plugins/wizard-analiza-competitori/skills/`. Pornește Claude Code cu pluginul local: `claude --plugin-dir plugins/wizard-analiza-competitori`. După o schimbare, crește `version` în `plugins/wizard-analiza-competitori/.claude-plugin/plugin.json`, altfel cursanții nu primesc actualizarea.

## Verificare rapidă, fără rețea

```
uv run plugins/wizard-analiza-competitori/skills/wizard-ads-review/scripts/collect.py --selfcheck
uv run plugins/wizard-analiza-competitori/skills/wizard-ads-review/scripts/analyze.py --selfcheck
uv run plugins/wizard-analiza-competitori/skills/wizard-landing-review/scripts/fetch.py --selfcheck
uv run plugins/wizard-analiza-competitori/skills/wizard-landing-review/scripts/analyze.py --selfcheck
```
