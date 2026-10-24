# Vols vers Istanbul

Site : https://snoog43.github.io/vols-turquie/

Le bouton **Rechercher** lance le robot GitHub Actions (`.github/workflows/recherche.yml`), qui scrape Google Flights
avec `scraper/scan.py` et enregistre `data/resultats.json`. Le robot tourne aussi tout seul chaque matin.

En local : `pip install fast-flights typing_extensions` puis `python scraper/scan.py --origines PAR,MRS --mois 2027-02`.
