# Kalendar trka

- `index.html` – stranica (čita `trke.json`)
- `data/manual.json` – ručno uneti i proverene trke (ovde ispravljaš i dodaješ)
- `scripts/scrape.py` – dopunjuje listu sa trka.rs, RunTrace i Trčanje.rs
- `.github/workflows/update.yml` – pokreće skriptu svake noći
- `trke.json` – generisan fajl koji stranica prikazuje (ne menjaj ručno)

Ručni unosi uvek imaju prednost, a skripta ih nikad ne briše. Ako neki izvor prestane da radi, ostali i ručni podaci ostaju.
