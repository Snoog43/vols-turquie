"""GET /api/vols?o=MRS&d=IST,SAW&aller=2027-02-03&retour=2027-02-17 : liste détaillée des vols."""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _moteur import repondre, vols  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        repondre(self, vols)
