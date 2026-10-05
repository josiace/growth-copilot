import os

def conf(name, default=""):
    """Réglage saisi dans l'interface (page Paramètres), sinon variable d'environnement, sinon valeur par défaut."""
    from .models import Setting
    try:
        s = Setting.objects.filter(key=name).first()
    except Exception:
        s = None
    return s.value if s and s.value else os.environ.get(name, default)
