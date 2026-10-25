# Mes vols

Un Google Flights perso : calendrier des prix du mois, vols aller puis retour, plusieurs aéroports par côté,
autocomplétion sur ~3 800 aéroports (villes et pays en français).

- `index.html` : le site. `airports.json` : la liste des aéroports (générée par `outils/aeroports.py`).
- `api/` : fonctions Vercel en Python. `dates.py` (calendrier) et `vols.py` (liste des vols), moteur commun dans `_moteur.py`,
  basé sur [fli](https://github.com/punitarani/fli) qui interroge l'API interne de Google Flights.
- En local : `pip install flights` puis `python serve.py` → http://127.0.0.1:4330
- Mise en ligne : `npx vercel --prod`
