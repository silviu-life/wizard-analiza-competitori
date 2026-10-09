---
name: wizard-analiza-reclame
description: Analiza completă a competiției pe Meta, cap-coadă: rulează întâi wizard-ads-review (reclamele active ale nișei, judecate față de cercetarea userului, cu reach-ul din UE), apoi wizard-landing-review pe același dosar (paginile la care duc reclamele potrivite) și dă un singur raport care leagă reclamele de paginile lor. Se activează la /wizard-analiza-reclame, „analiza completă a competiției”, „reclamele și landing-urile din nișa X”, „fă-mi tot, reclame și pagini”.
argument-hint: <nișă> [țară ISO-2, implicit RO] [limbă ISO-639-1, opțional]
---

# wizard-analiza-reclame

Leagă cele două skill-uri ale pluginului: întâi reclamele, apoi paginile la care duc. Nu are cod propriu; tot ce se rulează e în `wizard-ads-review` și `wizard-landing-review`, iar fluxul, limitele și regulile lor rămân valabile întocmai.

## Pași

1. **Argumente.** Nișa e obligatorie; dacă lipsește, cere-o. Țara și limba se dau mai departe neschimbate.

2. **Spune-i userului de la început ce urmează**, în câteva rânduri: se adună reclamele (se deschide browserul), îi pui patru întrebări despre afacere, se judecă textele, se cere reach-ul (cam 20 de secunde pe reclamă potrivită), apoi se vizitează paginile de landing (cam 10 secunde pe pagină). Totul poate dura de la 15 minute la o oră, în funcție de câte reclame potrivite ies.

3. **Reclamele.** Încarcă skill-ul `wizard-ads-review` cu tool-ul Skill (în plugin: `wizard-analiza-competitori:wizard-ads-review`), cu argumentele `<nișă> [țară] [limbă]`, și urmează-i fluxul complet, inclusiv reach-ul. Excepții, ca să nu se repete lucruri:
   - raportul lui (pasul 8) îl ții scurt: doar cifrele principale și tiparele de la winners. Analiza detaliată vine la final, în raportul comun;
   - reține slug-ul din `RUN_DIR=runs/<slug>`.

   Oprește-te aici, cu explicația de rigoare, dacă: colectarea dă zero reclame (cod 2), analiza nu are nicio reclamă potrivită cu cercetarea (`in_niche`), sau userul nu vrea să continue.

4. **Paginile de landing.** Încarcă skill-ul `wizard-landing-review` (`wizard-analiza-competitori:wizard-landing-review`) cu argumentul `<slug>` și urmează-i fluxul. Verificările deja făcute la pasul 3 (uv, Chromium, cheia TypeSafe sau Claude Code) nu le mai repeta; dacă userul a ales acolo `--skip-jev`, folosește-l și aici. Raportul lui îl ții și el scurt.

5. **Raport comun**, din `runs/<slug>/ads.json` și `runs/<slug>/landings.json`:
   - eșantionul: câte reclame, câte texte distincte, câte potrivite, câte winners; câte destinații, câte pagini web citite;
   - 5–8 tipare la reclame (hook, awareness, unghi, emoție, structură) și 4–6 la pagini (tip de pagină, acțiune cerută, preț, garanție, recenzii, formular);
   - **perechi reclamă → pagină** pentru primele 5 reclame după reach pe zi și zile de rulare: hook-ul, pagina la care duc (domeniul, tipul, prețul, ce promite primul ecran) și cât de bine continuă pagina reclama (`j.ad_match`). Asta e partea pe care niciun skill nu o dă singur;
   - unde pierde concurența: reclame puternice care duc pe pagini cu `ad_match` sub 0.5 sau pe pagini generice;
   - 3 idei concrete de testat, fiecare pe ambele părți: ce scrii în reclamă și ce pui pe primul ecran al paginii;
   - judecățile din listele `unsure` sunt incerte, iar tiparele sunt descrieri, nu dovezi: vedem doar reclame active.

6. **Predă raportul:** `runs/<slug>/raport.html`, cu tabul Reclame și tabul Landing-uri. Pe WSL: `explorer.exe "$(wslpath -w runs/<slug>/raport.html)"`.

## Reluare

O colectare nouă pe aceeași nișă și țară suprascrie reclamele din dosar. De aceea, dacă `runs/<nișă>-<țară>/ads.json` există deja, întreabă userul înainte de pasul 3: continuă cu dosarul existent (sari peste colectare: rulează doar analiza și reach-ul din `wizard-ads-review`, unde reclamele cu reach sunt sărite, apoi pasul 4) sau colectează din nou. Paginile de landing deja salvate și judecățile din cache se refolosesc oricum.
