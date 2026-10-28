#!/usr/bin/env python3
"""Ruska kopia mapy Braiders United pre GitHub Pages (Dean 28.10.2026).

PRECO: v Rusku Cloudflare neprejde (16 KB limit, na Tele2 uplny blok), GitHub Pages ano
(test Julie 27.10.2026). Tibor 27.10.2026: ANO ZA PODMIENOK.

AKO: GitHub Action kazdu hodinu spusti tento skript. Skript stiahne verejnu /ru z
braidersunited.com (stranky, styly, skripty, obrazky), zive karticky z /api/karty a ich
fotky z Workera a posklada staticku stranku do priecinka (default _site). Stranka potom
nenacitava nic z Cloudflare (braidersunited.com, workers.dev, cdn-cgi, cloudflareinsights).

Tvrde podmienky Tibora:
- karticky NIKDY v repozitari: skript ich len stiahne do _site, ide to cez Pages artefakt;
- karticka nesie len polia verejnej karticky (POLIA nizsie), nikdy e-mail, token, IP, suhlas;
- zmazana karticka zmizne do hodiny: kazdy beh stava cele _site nanovo.

Pouzitie: python3 postav.py [_site]   (len standardna kniznica)
"""
import hashlib
import html as htmlmod
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ZDROJ = "https://braidersunited.com"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
# Erik 28.10.2026: kam vedu tlacidla prihlasky a ci sa kopia indexuje (doplnene podla jeho hlasenia)
PRIHLASKA = "https://oobraider.ru/anketa_karta_br"   # GetCourse ruskej skoly, v Rusku sa otvori
NOINDEX = True   # Erik: noindex bez canonical a hreflang, v indexe ostava len braidersunited.com/ru/
# whitelist poli verejnej karticky (Tibor 27.10.2026); html/net/alt/noflag su len vykreslenie tych istych poli
POLIA = {"n", "city", "country", "addr", "lat", "lon", "net", "net_key", "handle", "shown", "url",
         "phone", "lang", "img", "listed", "checked", "pending", "prevzata", "html", "alt", "noflag"}
DAVKA = 40
ZAKAZANE = ("workers.dev", "cdn-cgi", "cloudflareinsights")
UA = {"User-Agent": "braidersunited-ru-kopia (+https://github.com/braidersunited)"}

stiahnute = set()


def get(url, binarne=False, pokusy=3):
    for i in range(pokusy):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
                return (data, r.headers.get("Content-Type", "")) if binarne else data.decode("utf-8")
        except Exception as e:
            if i == pokusy - 1:
                raise RuntimeError(f"{url}: {e}")
            time.sleep(3 * (i + 1))


def uloz(rel, data):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(data, bytes) else lambda d: p.write_text(d, encoding="utf-8"))(data)


def zdroj(rel):
    """Stiahne staticky subor (img/, assets/, vendor/) z braidersunited.com pod tou istou cestou."""
    rel = rel.split("?")[0].split("#")[0].lstrip("/")
    if not rel or rel in stiahnute or rel.startswith(("img/k/", "assets/karty_")) or (OUT / rel).exists():
        return
    stiahnute.add(rel)
    data, _ = get(f"{ZDROJ}/{urllib.parse.quote(rel)}", binarne=True)
    uloz(rel, data)
    if rel.endswith(".css"):   # fonty a obrazky v CSS (url(...) relativne k CSS)
        base = rel.rsplit("/", 1)[0]
        for u in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", data.decode("utf-8")):
            if not re.match(r"^(data:|https?:|#)", u):
                zdroj(str(Path(base, u)).replace("\\", "/"))


nova_cesta = {}


def foto(u):
    """Fotku karticky z Workera ulozi do img/k/ a vrati cestu od korena webu."""
    if u not in nova_cesta:
        data, typ = get(u, binarne=True)
        ext = ".png" if "png" in typ else ".webp" if "webp" in typ else ".jpg"
        c = re.search(r"/foto/(\w+)", u)
        rel = f"img/k/f{c.group(1) if c else ''}_{hashlib.md5(u.encode()).hexdigest()[:6]}{ext}"
        uloz(rel, data)
        nova_cesta[u] = rel
    return nova_cesta[u]


def cf_email(hexa):
    k = int(hexa[:2], 16)
    return "".join(chr(int(hexa[i:i + 2], 16) ^ k) for i in range(2, len(hexa), 2))


def odkazy_na_zdroje(text, z_ru=True):
    """Vrati cesty (od korena webu) vsetkych img/assets/vendor/favicon odkazov v texte."""
    out = set()
    for m in re.finditer(r"""(?:\.\./|/)?((?:img|assets|vendor)/[^"'\s)<>\\?#]+|favicon\.ico)""", text):
        out.add(m.group(1))
    return out


def stranka(nazov, html):
    """Upravi jednu stranku /ru: bez Cloudflare skriptov, e-maily odkryte, odkazy mimo kopie absolutne."""
    html = re.sub(r'<script[^>]*cloudflareinsights[^>]*>\s*</script>', "", html)
    html = re.sub(r'<script[^>]*cdn-cgi[^>]*>\s*</script>', "", html)
    html = re.sub(r'<a href="/cdn-cgi/l/email-protection#([0-9a-f]+)"',
                  lambda m: f'<a href="mailto:{cf_email(m.group(1))}"', html)
    html = re.sub(r'<span class="__cf_email__" data-cfemail="([0-9a-f]+)">[^<]*</span>',
                  lambda m: cf_email(m.group(1)), html)
    html = re.sub(r'href="/cdn-cgi/l/email-protection"', 'href="#"', html)
    # jazyky mimo kopie idu na braidersunited.com; /ru/ ostava v kopii
    html = re.sub(r'href="/(sk/|de/)?"', lambda m: f'href="{ZDROJ}/{m.group(1) or ""}"', html)
    html = re.sub(r'href="apply\.html[^"]*"', f'href="{PRIHLASKA}"', html)
    if NOINDEX:
        html = re.sub(r'<meta name="robots"[^>]*>\s*', "", html)
        html = re.sub(r'<link rel="(?:canonical|alternate)"[^>]*>\s*', "", html)
        html = html.replace("<head>", '<head>\n<meta name="robots" content="noindex, follow">', 1)
    return html


def main():
    if OUT.exists():
        import shutil
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) stranky /ru: od titulky po vsetky dosiahnutelne /ru/*.html okrem prihlasky
    fronta, hotove = ["index.html"], {}
    while fronta:
        n = fronta.pop(0)
        if n in hotove:
            continue
        try:
            html = get(f"{ZDROJ}/ru/" + ("" if n == "index.html" else n))
        except RuntimeError as e:
            if n == "index.html":
                raise
            print("preskakujem", n, e)
            hotove[n] = None
            continue
        hotove[n] = html
        for odk in re.findall(r'href="([a-z0-9\-]+\.html)(?:#[^"]*)?"', html):
            if odk != "apply.html" and odk not in hotove and len(hotove) + len(fronta) < 80:
                fronta.append(odk)
    for n, html in hotove.items():
        if html is not None:
            uloz(f"ru/{n}", stranka(n, html))
    # odkazy na stranky, ktore sa nestiahli, idu na original
    for n in hotove:
        p = OUT / "ru" / n
        if p.exists():
            t = p.read_text(encoding="utf-8")
            for chyba in [k for k, v in hotove.items() if v is None]:
                t = t.replace(f'href="{chyba}', f'href="{ZDROJ}/ru/{chyba}')
            p.write_text(t, encoding="utf-8")

    # 2) staticke karticky (data_ru.js): len polia z whitelistu
    t = get(f"{ZDROJ}/assets/data_ru.js")
    m = re.fullmatch(r"\s*window\.BRAIDERS\s*=\s*(\[.*\])\s*;?\s*", t, re.S)
    if not m:
        raise RuntimeError("data_ru.js: necakany tvar")
    staticke = [{k: v for k, v in b.items() if k in POLIA} for b in json.loads(m.group(1))]
    uloz("assets/data_ru.js", "window.BRAIDERS=" + json.dumps(staticke, ensure_ascii=False) + ";")

    # 3) zive karticky z /api/karty po davkach + ich fotky z Workera do img/k/
    prva = json.loads(get(f"{ZDROJ}/api/karty?d=0"))
    if not prva.get("ok"):
        raise RuntimeError("/api/karty neodpoveda ok")
    zive = list(prva["karty"])
    for i in range(1, prva["casti"]):
        j = json.loads(get(f"{ZDROJ}/api/karty?d={i}"))
        if not j.get("ok"):
            raise RuntimeError(f"/api/karty?d={i} neodpoveda ok")
        zive += j["karty"]
    for b in zive:
        if str(b.get("img") or "").startswith("http"):
            b["img"] = "../" + foto(b["img"])
    zive = [{k: v for k, v in b.items() if k in POLIA} for b in zive]
    casti = max(1, -(-len(zive) // DAVKA))
    for i in range(casti):
        uloz(f"assets/karty_{i}.json", json.dumps({"ok": True, "casti": casti, "karty": zive[i * DAVKA:(i + 1) * DAVKA]}, ensure_ascii=False))

    # stranky z Pages Function (browse, krajiny) nesu fotky zivych karticiek z Workera: tiez do img/k/
    for p in (OUT / "ru").glob("*.html"):
        t = p.read_text(encoding="utf-8")
        t2 = re.sub(r"""https://[a-z0-9.\-]+\.workers\.dev/bu/foto/[^"'\s)]+""",
                    lambda m: "../" + foto(htmlmod.unescape(m.group(0))), t)
        if t2 != t:
            p.write_text(t2, encoding="utf-8")

    # 4) skripty: home.js berie dávky z kopie, Worker sa nevola
    home = get(f"{ZDROJ}/assets/home.js")
    for stare, nove in [
        ('fetch("/api/karty?d=" + i)', 'fetch(T.root + "assets/karty_" + i + ".json")'),
        ('return fetch(window.BU_API + "/bu/karty").then(function (r) { return r.json(); });', 'return Promise.reject(new Error("kopia"));'),
    ]:
        if home.count(stare) != 1:
            raise RuntimeError(f"home.js sa zmenil, nenasiel som: {stare}")
        home = home.replace(stare, nove)
    uloz("assets/home.js", home)
    # icons.js: adresa Workera sa v kopii nepouziva (home.js ju uz nevola), nesmie tam ostat
    icons = get(f"{ZDROJ}/assets/icons.js")
    icons, n = re.subn(r'window\.BU_API="[^"]*"', 'window.BU_API="kopia"', icons)
    if n != 1:
        raise RuntimeError("icons.js sa zmenil, nenasiel som BU_API")
    uloz("assets/icons.js", icons)
    stiahnute.add("assets/icons.js")
    stiahnute.add("assets/home.js")
    stiahnute.add("assets/data_ru.js")

    # mini.json: male fotky pinov; kluce zivych karticiek prepisane na img/k/
    mini = json.loads(get(f"{ZDROJ}/assets/mini.json"))
    mini = {nova_cesta.get(k, k): v for k, v in mini.items() if not k.startswith("http") or k in nova_cesta}
    uloz("assets/mini.json", json.dumps(mini, ensure_ascii=False))
    stiahnute.add("assets/mini.json")

    # 5) vsetky obrazky, styly, skripty a fonty, na ktore stranky a data odkazuju
    vlajky = set()
    for nazov in ("FLAG", "CFLAG"):
        mm = re.search(r"window\." + nazov + r"=(\{[^}]*\})", icons)
        if mm:
            vlajky |= {f"img/flags/{v}.svg" for v in json.loads(mm.group(1)).values() if v}
    potrebne = set(vlajky) | {"img/bez_fotky.svg", "favicon.ico"}
    for p in list(OUT.rglob("*")):
        if p.suffix in (".html", ".js", ".json", ".css"):
            potrebne |= odkazy_na_zdroje(p.read_text(encoding="utf-8"))
    potrebne |= {f"assets/{s}" for s in ("t_ru.js", "ui.js", "icons.js", "site.css")}
    for rel in sorted(potrebne):
        if rel.startswith("img/k/"):
            continue
        try:
            zdroj(rel)
        except RuntimeError as e:   # odkaz najdeny v skripte nemusi byt subor; povinne su len odkazy zo stranok (krok 7)
            print("preskakujem", e)
    # druhe kolo: odkazy v prave stiahnutych skriptoch (napr. t_ru.js, ui.js)
    for rel in list(stiahnute):
        if rel.endswith(".js"):
            for r2 in odkazy_na_zdroje((OUT / rel).read_text(encoding="utf-8")):
                if not r2.startswith("img/k/"):
                    try:
                        zdroj(r2)
                    except RuntimeError as e:
                        print("preskakujem", e)

    # 6) koren: presmerovanie na /ru/, 404 tiez
    presmer = ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex">'
               '<meta http-equiv="refresh" content="0; url=/ru/"><title>Braiders United</title></head>'
               '<body><a href="/ru/">Braiders United</a><script>location.replace("/ru/"+location.hash)</script></body></html>')
    uloz("index.html", presmer)
    uloz("404.html", presmer)
    uloz(".nojekyll", "")
    spolu = len(staticke) + len(zive)
    uloz("verzia.json", json.dumps({"obnovene": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "staticke": len(staticke), "zive": len(zive), "spolu": spolu}))

    # 7) poistka: kazdy obrazok, styl a skript zo stranok existuje, nic z Cloudflare, ziadne nepovolene polia
    for p in (OUT / "ru").glob("*.html"):
        for u in re.findall(r'(?:src|href)="(\.\./[^"#?]+|/(?:img|assets|vendor)/[^"#?]+)', p.read_text(encoding="utf-8")):
            ciel = (p.parent / u).resolve() if u.startswith("..") else (OUT / u.lstrip("/")).resolve()
            if not ciel.exists():
                raise RuntimeError(f"{p.name}: chyba {u}")
    for p in OUT.rglob("*"):
        if p.suffix in (".html", ".js", ".json", ".css"):
            t = p.read_text(encoding="utf-8")
            for z in ZAKAZANE:
                if z in t:
                    raise RuntimeError(f"{p.relative_to(OUT)} obsahuje {z}")
            if re.search(r"""(src=|url\(|fetch\()\s*["']?https://braidersunited\.com""", t):
                raise RuntimeError(f"{p.relative_to(OUT)} nacitava nieco z braidersunited.com")
            if p.name.startswith("karty_") and re.search(r'"(e-?mail|token|ip|suhlas|consent)"\s*:', t, re.I):
                raise RuntimeError(f"{p.name} nesie nepovolene pole")
    print(f"HOTOVO: {spolu} karticiek ({len(staticke)} staticke, {len(zive)} zive), {len(stiahnute)} suborov, {len(hotove)} stranok")


if __name__ == "__main__":
    main()
