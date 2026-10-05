import base64, hmac, os
from django.http import HttpResponse

class Gate:
    """Mot de passe simple (variable APP_PASSWORD). /go/ et /api/ restent publics."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pw = os.environ.get("APP_PASSWORD")
        if pw and not request.path.startswith(("/go/", "/api/", "/static/", "/p/", "/blog/", "/sitemap.xml", "/robots.txt")):
            h, ok = request.META.get("HTTP_AUTHORIZATION", ""), False
            if h.startswith("Basic "):
                try:
                    ok = hmac.compare_digest(base64.b64decode(h[6:]).decode().partition(":")[2], pw)
                except Exception:
                    pass
            if not ok:
                r = HttpResponse("Accès protégé", status=401)
                r["WWW-Authenticate"] = 'Basic realm="Growth Copilot"'
                return r
        return self.get_response(request)
