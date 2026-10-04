"""Osvežava trke.json: spaja ručne podatke (data/manual.json) sa trka.rs, RunTrace i Trčanje.rs.
Svaki izvor je u try/except: ako jedan padne, ostali i ručni podaci ostaju. Skripta nikad ne briše ručne unose."""
import json, re, sys, datetime as dt
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
END = dt.date(2027, 12, 31)          # do kad prikazujemo trke
UA = {"User-Agent": "Mozilla/5.0 (kalendar-trka-bot)"}
MESECI = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAJ":5,"JUN":6,"JUL":7,"AVG":8,"SEP":9,"OKT":10,"NOV":11,"DEC":12}

def ok(d): return TODAY <= d <= END
def norm(t): return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", t.lower().replace("č","c").replace("ć","c").replace("š","s").replace("ž","z").replace("đ","dj")))
def get(url):
    r = requests.get(url, headers=UA, timeout=30); r.raise_for_status(); return BeautifulSoup(r.text, "html.parser")

def scrape_trkars():
    out = []
    soup = get("https://trka.rs/")
    for a in soup.select('a[href*="/events/"]'):
        href = a.get("href", "")
        if not re.search(r"/events/\d+-", href): continue
        box = a
        for _ in range(4):                       # tražimo roditelja koji sadrži datum
            if box.parent is None: break
            box = box.parent
            if re.search(r"\d{2}/\d{2}/\d{4}", box.get_text(" ")): break
        text = box.get_text("\n", strip=True)
        dates = re.findall(r"(\d{2})/(\d{2})/(\d{4})", text)
        if not dates: continue
        d1 = dt.date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
        d2 = dt.date(int(dates[-1][2]), int(dates[-1][1]), int(dates[-1][0])) if len(dates) > 1 else None
        h = box.find(["h5","h4","h3","h6"]); img = box.find("img", alt=True)
        name = (h.get_text(strip=True) if h else (img["alt"] if img else "")).strip()
        lines = [l for l in text.split("\n") if l and l != name and not re.search(r"\d{2}/\d{2}/\d{4}|Registration|Advertisement", l)]
        if not name: continue
        if ok(d2 or d1):
            out.append(dict(date=d1.isoformat(), end=d2.isoformat() if d2 else None, name=name, place=lines[0] if lines else "",
                            country="Srbija", distances=[], url=href if href.startswith("http") else "https://trka.rs"+href, source="trka.rs"))
    return out

def scrape_runtrace():
    out = []
    soup = get("https://runtrace.net/")
    for t in soup.find_all(string=re.compile(r"\d{2}\.\d{2}\.\d{4}\.")):
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\.", t)
        d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        box = t.parent
        for _ in range(4):
            if box.parent is None: break
            if box.parent.find("a"): box = box.parent; break
            box = box.parent
        links = box.find_all("a", href=True)
        name = next((a.get_text(strip=True) for a in links if a.get_text(strip=True) and a["href"] != "#" and "Results" not in a.get_text() and "Sign" not in a.get_text() and "Particip" not in a.get_text()), "")
        if not name:
            h = box.find(["h3","h4","h5","a"]); name = h.get_text(strip=True) if h else ""
        strings = [s for s in box.stripped_strings if s != name and not re.search(r"\d{2}\.\d{2}\.\d{4}|Results|Sign up|Participants", s)]
        slug = next((a["href"] for a in links if a["href"].startswith("http") and "/reg" not in a["href"] and "runtrace.net/" in a["href"]), "https://runtrace.net/")
        if name and ok(d):
            out.append(dict(date=d.isoformat(), name=name, place=strings[0] if strings else "", country="Srbija", distances=[], url=slug, source="RunTrace"))
    return out

def scrape_trcanje():
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        for year in (2026, 2027):
            pg.goto(f"https://www.trcanje.rs/kalendar/?e-filter-0af86fa-godina={year}", wait_until="networkidle")
            for _ in range(15):                  # skrolujemo da se učita cela lista
                pg.mouse.wheel(0, 4000); pg.wait_for_timeout(700)
            for a in pg.query_selector_all('a[href*="/event/"]'):
                txt = " ".join((a.inner_text() or "").split()); href = a.get_attribute("href")
                m = re.match(r"(\d{1,2})\s+([A-ZČĆŠŽ]{3})\w*\s+(.*)", txt)
                if not m or m.group(2) not in MESECI: continue
                d = dt.date(year, MESECI[m.group(2)], int(m.group(1)))
                rest = m.group(3); dist = []
                if "·" in rest:
                    rest, ds = rest.rsplit("·", 1)
                    for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*km", ds):
                        v = float(x.replace(",", ".")); dist.append({21.0:21.1, 42.0:42.2}.get(v, v))
                if ok(d): out.append(dict(date=d.isoformat(), name=rest.strip(), place="", country="Srbija/region", distances=dist, url=href, source="Trčanje.rs"))
        b.close()
    return out

def same(a, b):
    if a["date"] != b["date"]: return False
    A, B = set(norm(a["name"]).split()), set(norm(b["name"]).split())
    return len(A & B) >= 2 or (len(A & B) / max(1, len(A | B))) >= 0.4

def main():
    manual = json.loads((ROOT/"data/manual.json").read_text(encoding="utf-8"))
    merged = [r for r in manual if ok(dt.date.fromisoformat(r.get("end") or r["date"]))]
    stats = {}
    for name, fn in (("trka.rs", scrape_trkars), ("RunTrace", scrape_runtrace), ("Trčanje.rs", scrape_trcanje)):
        try:
            found = fn(); added = 0
            for r in found:
                dup = next((m for m in merged if same(m, r)), None)
                if dup is None: merged.append(r); added += 1
                elif not dup.get("distances") and r.get("distances"): dup["distances"] = r["distances"]   # dopuni distance
            stats[name] = f"{len(found)} pronađeno, {added} novih"
        except Exception as e:
            stats[name] = f"GREŠKA: {e}"
    merged.sort(key=lambda r: r["date"])
    out = {"updated": TODAY.strftime("%d.%m.%Y."), "races": merged}
    (ROOT/"trke.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1)); print("Ukupno trka:", len(merged))

if __name__ == "__main__":
    main()
