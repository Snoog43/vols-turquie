"""Serveur local pour tester le site : python serve.py puis http://127.0.0.1:4330"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "api"))
# en local sous Windows, fli est installé dans un dossier au chemin court (pip install --target %TEMP%\fli flights)
_court = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "fli")
if os.path.isdir(_court):
    sys.path.insert(0, _court)
from _moteur import calendrier, repondre, vols  # noqa: E402

ROUTES = {"/api/dates": calendrier, "/api/vols": vols}


class Local(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ICI, **k)

    def do_GET(self):
        fn = ROUTES.get(self.path.split("?")[0])
        if fn:
            repondre(self, fn)
        else:
            super().do_GET()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 4330))
    print(f"http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Local).serve_forever()
