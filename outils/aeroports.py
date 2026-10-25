"""Génère airports.json pour l'autocomplétion du site.

Croise les aéroports connus de Google Flights (liste de fli) avec OurAirports (ville, pays, taille).
Usage : python outils/aeroports.py chemin/vers/airports.csv
Source OurAirports : https://davidmegginson.github.io/ourairports-data/airports.csv (domaine public)
"""
import csv
import json
import os
import sys

from fli.models import Airport

# noms français des grandes villes, pour pouvoir taper « Londres » ou « Athènes »
FR = {
    "London": "Londres", "Rome": "Rome", "Athens": "Athènes", "Venice": "Venise", "Geneva": "Genève",
    "Barcelona": "Barcelone", "Seville": "Séville", "Lisbon": "Lisbonne", "Warsaw": "Varsovie", "Vienna": "Vienne",
    "Cairo": "Le Caire", "Beijing": "Pékin", "Moscow": "Moscou", "Brussels": "Bruxelles", "Copenhagen": "Copenhague",
    "Edinburgh": "Édimbourg", "Munich": "Munich", "Cologne": "Cologne", "Frankfurt am Main": "Francfort",
    "Frankfurt": "Francfort", "Hamburg": "Hambourg", "Milan": "Milan", "Naples": "Naples", "Florence": "Florence",
    "Turin": "Turin", "Basel": "Bâle", "Zurich": "Zurich", "Krakow": "Cracovie", "Kraków": "Cracovie",
    "Thessaloniki": "Thessalonique", "Dubai": "Dubaï", "Algiers": "Alger", "Tangier": "Tanger", "Fes": "Fès",
    "Agadir": "Agadir", "Casablanca": "Casablanca", "Djerba": "Djerba", "Bangkok": "Bangkok", "Tokyo": "Tokyo",
    "New York": "New York", "Montreal": "Montréal", "Mexico City": "Mexico", "Havana": "La Havane",
    "Sao Paulo": "São Paulo", "Buenos Aires": "Buenos Aires", "Singapore": "Singapour", "Seoul": "Séoul",
    "Shanghai": "Shanghai", "Hong Kong": "Hong Kong", "Delhi": "Delhi", "New Delhi": "New Delhi", "Mumbai": "Bombay",
    "Ho Chi Minh City": "Hô Chi Minh-Ville", "Hanoi": "Hanoï", "Denpasar": "Bali (Denpasar)", "Tbilisi": "Tbilissi",
    "Beirut": "Beyrouth", "Amman": "Amman", "Tel Aviv": "Tel Aviv", "Valletta": "La Valette", "Luqa": "Malte (Luqa)",
    "Nice": "Nice", "Marseille": "Marseille", "Lyon": "Lyon", "Strasbourg": "Strasbourg", "Lisboa": "Lisbonne",
    "Antalya": "Antalya", "Istanbul": "Istanbul", "Izmir": "Izmir", "Ankara": "Ankara", "Dalaman": "Dalaman",
    "Bodrum": "Bodrum", "Prague": "Prague", "Budapest": "Budapest", "Dublin": "Dublin", "Reykjavik": "Reykjavik",
    "Oslo": "Oslo", "Stockholm": "Stockholm", "Helsinki": "Helsinki", "Porto": "Porto", "Faro": "Faro",
    "Palma de Mallorca": "Palma de Majorque", "Malaga": "Malaga", "Madrid": "Madrid", "Valencia": "Valence",
    "Alicante": "Alicante", "Split": "Split", "Dubrovnik": "Dubrovnik", "Bucharest": "Bucarest", "Sofia": "Sofia",
    "Belgrade": "Belgrade", "Tirana": "Tirana", "Larnaca": "Larnaca", "Heraklion": "Héraklion", "Rhodes": "Rhodes",
    "Marrakesh": "Marrakech", "Marrakech": "Marrakech", "Tunis": "Tunis", "Dakar": "Dakar", "Abidjan": "Abidjan",
}

# aéroports secondaires vendus sous le nom d'une grande ville
PAR_CODE = {
    "BVA": "Paris", "CRL": "Bruxelles", "BGY": "Milan", "STN": "Londres", "LTN": "Londres", "LGW": "Londres",
    "LCY": "Londres", "CIA": "Rome", "GRO": "Barcelone", "TRF": "Venise", "HHN": "Francfort", "NYO": "Stockholm",
    "WMI": "Varsovie", "EIN": "Amsterdam", "XCR": "Paris", "SAW": "Istanbul", "MXP": "Milan", "LIN": "Milan",
    "NRT": "Tokyo", "HND": "Tokyo", "KIX": "Osaka", "EWR": "New York", "ADB": "Izmir", "BJV": "Bodrum",
    "DMK": "Bangkok", "GIG": "Rio de Janeiro", "GRU": "São Paulo", "YUL": "Montréal", "YYZ": "Toronto",
    "PVG": "Shanghai", "PEK": "Pékin", "PKX": "Pékin", "TFS": "Tenerife", "TFN": "Tenerife",
}

# grands aéroports passagers, proposés en premier quand on choisit un pays
TOP = set("""IST SAW AYT ESB ADB DLM BJV CDG ORY NCE LYS MRS TLS BOD NTE BVA MPL LHR LGW STN MAN LTN EDI FRA MUC BER DUS
HAM MAD BCN PMI AGP ALC VLC TFS LPA FCO MXP BGY VCE NAP CIA LIN CTA AMS BRU CRL ZRH GVA VIE LIS OPO FAO ATH SKG HER RHO
DUB CPH ARN OSL HEL WAW KRK PRG BUD OTP SOF RAK CMN AGA TNG FEZ RBA TUN DJE ALG ORN CAI HRG SSH DXB AUH DOH TLV AMM BEY
BKK HKT DMK CNX DPS CGK SIN KUL HND NRT KIX ICN PEK PKX PVG CAN HKG DEL BOM JFK EWR LAX SFO MIA ORD ATL YUL YYZ YVR MEX
CUN GRU GIG EZE BOG LIM SYD MEL JNB CPT DSS ABJ MRU RUN PTP FDF TBS LCA MLA SPU DBV ZAG BEG TIA KEF""".split())

RANG = {"large_airport": 3, "medium_airport": 2, "small_airport": 1}


def main(src):
    connus = {a.name for a in Airport}
    sortie = []
    with open(src, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            code = r["iata_code"].strip()
            if code not in connus or r["type"] not in RANG:
                continue
            if r["scheduled_service"] != "yes" and r["type"] != "large_airport":
                continue
            ville, nom = r["municipality"].strip(), r["name"].strip()
            # la « ville » est parfois la commune (Marignane pour Marseille) : on cherche aussi dans le nom
            # « commence par » pour éviter East London -> Londres
            alias = {fr for en, fr in FR.items() if ville.startswith(en) or nom.startswith(en)}
            if code in PAR_CODE:
                alias = {PAR_CODE[code]} | alias
            alias = sorted(alias - {ville}, key=lambda a: a != PAR_CODE.get(code))
            rang = 4 if code in TOP else RANG[r["type"]]
            sortie.append([code, nom, ville, r["iso_country"], rang, "|".join(alias)])
    sortie.sort(key=lambda x: (-x[4], x[0]))
    dst = os.path.join(os.path.dirname(__file__), "..", "airports.json")
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(sortie, fh, ensure_ascii=False, separators=(",", ":"))
    print(len(sortie), "aéroports ->", os.path.abspath(dst), os.path.getsize(dst) // 1024, "Ko")


if __name__ == "__main__":
    main(sys.argv[1])
