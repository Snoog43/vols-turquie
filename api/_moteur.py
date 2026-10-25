"""Moteur de recherche commun aux fonctions /api/dates et /api/vols (via fli, API interne de Google Flights)."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from fli.models import (Airport, BagsFilter, DateSearchFilters, FlightSearchFilters, FlightSegment, MaxStops,
                        PassengerInfo, SeatType, SortBy, TripType)
from fli.search import SearchDates, SearchFlights

LOCALE = {"currency": "EUR", "language": "fr", "country": "FR"}
ESCALES = {"0": MaxStops.NON_STOP, "1": MaxStops.ONE_STOP_OR_FEWER, "2": MaxStops.TWO_OR_FEWER_STOPS}
MAX_AEROPORTS = 10


class ErreurRequete(ValueError):
    pass


def lire(url):
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

    def aeroports(cle):
        codes = [c.strip().upper() for c in q.get(cle, "").split(",") if c.strip()]
        if not codes:
            raise ErreurRequete(f"paramètre {cle} manquant")
        if len(codes) > MAX_AEROPORTS:
            raise ErreurRequete(f"{MAX_AEROPORTS} aéroports maximum par côté")
        try:
            return [[Airport[c], 0] for c in codes]
        except KeyError as e:
            raise ErreurRequete(f"aéroport inconnu : {e.args[0]}")

    q["o"], q["d"] = aeroports("o"), aeroports("d")
    q["escales"] = ESCALES.get(q.get("escales", ""), MaxStops.ANY)
    q["adultes"] = max(1, min(9, int(q.get("adultes", "1") or 1)))
    q["bagages"] = max(0, min(2, int(q.get("bagages", "0") or 0)))
    return q


def segments(q, aller, retour=None):
    segs = [FlightSegment(departure_airport=q["o"], arrival_airport=q["d"], travel_date=aller)]
    if retour:
        segs.append(FlightSegment(departure_airport=q["d"], arrival_airport=q["o"], travel_date=retour))
    return segs


def calendrier(url):
    """Prix le plus bas pour chaque date de départ d'une période (et durée de séjour fixe si aller-retour)."""
    q = lire(url)
    debut, fin = q.get("du"), q.get("au")
    duree = int(q.get("duree", "0") or 0)
    if not debut or not fin:
        raise ErreurRequete("paramètres du / au manquants")
    retour = (date.fromisoformat(debut) + timedelta(days=duree)).isoformat() if duree else None

    # le calendrier de Google ne gère qu'un aéroport de départ : une requête par aéroport, en parallèle
    def un_depart(origine):
        qq = dict(q, o=[origine])
        f = DateSearchFilters(
            trip_type=TripType.ROUND_TRIP if duree else TripType.ONE_WAY,
            passenger_info=PassengerInfo(adults=q["adultes"]), flight_segments=segments(qq, debut, retour),
            stops=q["escales"], seat_type=SeatType.ECONOMY, from_date=debut, to_date=fin, duration=duree or None)
        try:
            return origine[0].name, SearchDates().search(f, **LOCALE) or []
        except Exception:
            return origine[0].name, []

    meilleur = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for code, res in ex.map(un_depart, q["o"]):
            for r in res:
                if not r.price:
                    continue
                aller = r.date[0].date().isoformat()
                if aller not in meilleur or r.price < meilleur[aller]["prix"]:
                    meilleur[aller] = {"aller": aller, "prix": round(r.price), "depuis": code,
                                       "retour": r.date[1].date().isoformat() if len(r.date) > 1 else None}
    return {"prix": sorted(meilleur.values(), key=lambda x: x["aller"])}


# la table de fli a quelques noms périmés ou faux
NOMS_COMPAGNIES = {
    "LH": "Lufthansa", "VL": "Lufthansa City Airlines", "VF": "AJet", "AZ": "ITA Airways", "TO": "Transavia",
    "HV": "Transavia", "LX": "Swiss", "TP": "TAP Air Portugal", "SK": "SAS",
}


def compagnie(leg):
    code = leg.airline.name.lstrip("_")
    return NOMS_COMPAGNIES.get(code, leg.airline.value)


def _trajet(v):
    return {
        "duree": v.duration, "escales": v.stops,
        "compagnies": list(dict.fromkeys(compagnie(l) for l in v.legs)),
        "codes": list(dict.fromkeys(l.airline.name.lstrip("_") for l in v.legs)),
        "depart": v.legs[0].departure_datetime.isoformat(timespec="minutes"),
        "arrivee": v.legs[-1].arrival_datetime.isoformat(timespec="minutes"),
        "de": v.legs[0].departure_airport.name, "vers": v.legs[-1].arrival_airport.name,
        "correspondances": [{"aeroport": c.airport.name, "duree": c.duration, "nuit": c.overnight}
                            for c in (v.layovers or [])],
        "vols": [{"numero": f"{l.airline.name.lstrip('_')} {l.flight_number}", "compagnie": compagnie(l),
                  "de": l.departure_airport.name, "vers": l.arrival_airport.name,
                  "depart": l.departure_datetime.isoformat(timespec="minutes"),
                  "arrivee": l.arrival_datetime.isoformat(timespec="minutes"),
                  "duree": l.duration, "avion": l.aircraft} for l in v.legs],
        "auto_correspondance": bool(v.self_transfer),
    }


def _cle(v):
    return "|".join(f"{l.airline.name}{l.flight_number}@{l.departure_datetime:%Y%m%d%H%M}" for l in v.legs)


def _liste(resultats):
    sortie, vus = [], set()
    for v in resultats or []:
        cle = _cle(v)
        if v.price is None or cle in vus:
            continue
        vus.add(cle)
        sortie.append(dict(_trajet(v), prix=round(v.price), cle=cle))
    sortie.sort(key=lambda x: x["prix"])
    return sortie[:80]


def vols(url):
    """Comme Google Flights : d'abord les vols aller, puis (avec choix=cle) les retours du vol aller choisi.

    En aller-retour, chaque prix est le total du voyage (« aller-retour dès … » à la première étape).
    """
    q = lire(url)
    aller, retour, choix = q.get("aller"), q.get("retour") or None, q.get("choix")
    if not aller:
        raise ErreurRequete("paramètre aller manquant")
    f = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP if retour else TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=q["adultes"]), flight_segments=segments(q, aller, retour),
        stops=q["escales"], seat_type=SeatType.ECONOMY, sort_by=SortBy.CHEAPEST,
        bags=BagsFilter(checked_bags=q["bagages"]) if q["bagages"] else None)
    moteur = SearchFlights()

    def une_requete():
        # _fetch_flights = une seule requête Google, sans l'expansion automatique des retours de search().
        # Google renvoie parfois une page vide sur les recherches multi-aéroports : on réessaie une fois.
        for essai in range(2):
            res = moteur._fetch_flights(f, capture_session=False, **LOCALE)
            if res:
                return res
            time.sleep(0.6)
        return []

    allers = une_requete()
    if not retour or not choix:
        return {"etape": "aller", "vols": _liste(allers)}
    choisi = next((v for v in allers or [] if _cle(v) == choix), None)
    if choisi is None:
        raise ErreurRequete("ce vol aller n'est plus proposé, relance la recherche")
    f.flight_segments[0].selected_flight = choisi
    return {"etape": "retour", "aller": dict(_trajet(choisi), prix=round(choisi.price or 0), cle=choix),
            "vols": _liste(une_requete())}


def repondre(handler, fn):
    """Exécute fn(url) et renvoie du JSON (avec CORS pour la version GitHub Pages)."""
    try:
        code, corps = 200, fn(handler.path)
    except ErreurRequete as e:
        code, corps = 400, {"erreur": str(e)}
    except Exception as e:  # Google peut refuser ou changer son format
        code, corps = 502, {"erreur": f"recherche impossible : {type(e).__name__}: {e}"[:300]}
    data = json.dumps(corps, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "s-maxage=900, stale-while-revalidate=3600" if code == 200 else "no-store")
    handler.end_headers()
    handler.wfile.write(data)
