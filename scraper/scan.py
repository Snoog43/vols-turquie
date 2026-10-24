"""Scanne Google Flights : aller-retour France -> Istanbul pour chaque jour d'un mois.

Usage :
  python scraper/scan.py --origines PAR,MPL,FNI,MRS --dests IST,SAW --mois 2027-02 --sejours 12,14,16
Écrit data/resultats.json (lu par index.html).
"""
import argparse
import calendar
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from fast_flights import FlightQuery, create_query
from fast_flights.parser import parse_js
from primp import Client
from selectolax.lexbor import LexborHTMLParser

NOMS = {
    "PAR": "Paris (CDG/Orly/Beauvais)", "MPL": "Montpellier", "FNI": "Nîmes", "MRS": "Marseille",
    "LYS": "Lyon", "TLS": "Toulouse", "IST": "Istanbul Aéroport", "SAW": "Istanbul Sabiha Gökçen",
}
URL = "https://www.google.com/travel/flights"
_local = threading.local()


def client():
    # une connexion par thread : Google coupe les connexions HTTP/2 partagées trop chargées
    if not hasattr(_local, "c"):
        _local.c = Client(impersonate="chrome_145", impersonate_os="windows", referer=True, cookie_store=True)
    return _local.c


def search(origine, dest, aller, retour):
    q = create_query(
        flights=[FlightQuery(date=aller, from_airport=origine, to_airport=dest),
                 FlightQuery(date=retour, from_airport=dest, to_airport=origine)],
        trip="round-trip", currency="EUR", language="fr")
    # SOCS=CAI : réponse « tout refuser » au bandeau cookies européen de Google
    html = client().get(URL, params=q.params(), headers={"Cookie": "SOCS=CAI"}).text
    return lire_vols(html), q.url()


def lire_vols(html):
    """Lit les « meilleurs vols » (payload[3]) ET les « autres vols » (payload[2]).

    fast-flights ne lit que payload[3] : on lui repasse chaque section à cet emplacement.
    """
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        return []
    try:
        payload = json.loads(script.text().split("data:", 1)[1].rsplit(",", 1)[0])
    except (IndexError, ValueError):
        return []
    vols = []
    for idx in (3, 2):
        if not payload[idx] or not payload[idx][0]:
            continue
        p = list(payload)
        p[3] = payload[idx]
        try:
            vols += parse_js("data:" + json.dumps(p) + ",x")
        except Exception:
            pass
    return vols


def un_vol(origine, dest, aller, retour):
    time.sleep(random.uniform(0.8, 2.0))
    for essai in range(3):
        try:
            res, url = search(origine, dest, aller.isoformat(), retour.isoformat())
            break
        except Exception as e:
            print(f"  erreur {origine}-{dest} {aller} : {e}", file=sys.stderr)
            _local.__dict__.pop("c", None)
            time.sleep(4 * (essai + 1))
    else:
        return []
    return [{
        "origine": origine, "dest": dest, "aller": aller.isoformat(), "retour": retour.isoformat(),
        "prix": f.price, "compagnies": f.airlines, "escales": len(f.flights) - 1,
        "duree_min": sum(s.duration for s in f.flights),
        "segments": [f"{s.from_airport.code}→{s.to_airport.code} {s.departure.time[0]:02d}:{s.departure.time[1]:02d}"
                     for s in f.flights],
        "url": url,
    } for f in res]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origines", default="PAR,MPL,FNI,MRS")
    ap.add_argument("--dests", default="IST,SAW")
    ap.add_argument("--mois", default="2027-02")
    ap.add_argument("--sejours", default="12,14,16")
    ap.add_argument("--sortie", default=os.path.join(os.path.dirname(__file__), "..", "data", "resultats.json"))
    a = ap.parse_args()

    origines = [x.strip().upper() for x in a.origines.split(",") if x.strip()]
    dests = [x.strip().upper() for x in a.dests.split(",") if x.strip()]
    sejours = [int(x) for x in a.sejours.split(",") if x.strip()]
    an, mo = map(int, a.mois.split("-"))
    jours = [date(an, mo, j) for j in range(1, calendar.monthrange(an, mo)[1] + 1)]
    taches = [(o, d, j, j + timedelta(days=s)) for o in origines for d in dests for j in jours for s in sejours]
    print(f"{len(taches)} recherches…", flush=True)

    resultats, fait, vides = [], 0, 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for r in ex.map(lambda t: un_vol(*t), taches):
            resultats.extend(r)
            vides += not r
            fait += 1
            if fait % 25 == 0:
                print(f"  {fait}/{len(taches)}", flush=True)

    resultats.sort(key=lambda r: r["prix"])
    os.makedirs(os.path.dirname(os.path.abspath(a.sortie)), exist_ok=True)
    with open(a.sortie, "w", encoding="utf-8") as fh:
        json.dump({
            "genere": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "params": {"origines": origines, "dests": dests, "mois": a.mois, "sejours": sejours},
            "noms": {k: NOMS.get(k, k) for k in origines + dests},
            "recherches": len(taches), "sans_resultat": vides,
            "resultats": resultats,
        }, fh, ensure_ascii=False)
    print(f"{len(resultats)} vols ({vides}/{len(taches)} recherches vides) -> {a.sortie}")
    for r in resultats[:10]:
        print(r["prix"], "€", r["origine"], r["dest"], r["aller"], r["retour"], r["compagnies"])


if __name__ == "__main__":
    main()
