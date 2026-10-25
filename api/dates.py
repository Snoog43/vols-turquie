"""GET /api/dates?o=MRS&d=IST,SAW&du=2027-02-01&au=2027-02-28&duree=14 : calendrier des prix."""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _moteur import calendrier, repondre  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        repondre(self, calendrier)
