import json, os, urllib.parse, urllib.request
from .conf import conf
from datetime import date, timedelta
from django.db.models import Count
from .models import Post

def _ask(prompt):
    key = conf("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({"model": conf("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 3000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
        {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)["content"][0]["text"]
    except Exception:
        return None

def _fallback(p, channels, n):
    ideas = ["Présentation : {d}", "Pour {a} : {o}", "Question à la communauté : quel est votre plus gros problème avec {n} ?",
             "Exemple concret avec {n}", "Astuce du jour liée à {n}", "Offre à saisir : {o}", "Rappel : {n} est là pour {a}"]
    return [{"channel": channels[i % len(channels)],
             "text": ideas[i % len(ideas)].format(d=p.description, a=p.audience, o=p.offer or p.description, n=p.name)
                     + "\n\nEn savoir plus : {link}"} for i in range(n)]

def generate(project, days=7, start=None, channels=None):
    channels = channels or project.channel_list()
    start = start or date.today()
    top = Post.objects.filter(project=project).annotate(c=Count("click")).filter(c__gt=0).order_by("-c")[:3]
    best = "\n---\n".join(t.text for t in top) or "aucun pour l'instant"
    raw = _ask(f"""Tu es expert en marketing digital pour le marché ouest-africain (WhatsApp, Facebook, TikTok, Telegram).
Projet : {project.name}. Description : {project.description}. Cible : {project.audience}. Offre : {project.offer}. Ton : {project.tone}.
Écris {days} publications en français simple, une par jour, en alternant ces canaux : {', '.join(channels)}.
Chaque texte est prêt à publier, court, avec un appel à l'action clair et le marqueur {{link}} à l'endroit du lien.
Pour tiktok, écris un script vidéo de 20 secondes (accroche, 2 idées, appel à l'action).
Varie les angles (problème, preuve, offre, question, astuce). Imite ce qui a le mieux marché :
{best}
Réponds UNIQUEMENT par un tableau JSON d'objets {{"channel": "...", "text": "..."}}.""")
    items = None
    if raw:
        try:
            items = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
            items = [i for i in items if i.get("text")][:days] or None
        except Exception:
            items = None
    items = items or _fallback(project, channels, days)
    return [Post.objects.create(project=project, channel=i.get("channel", channels[0]).lower(),
            text=i["text"], scheduled_for=start + timedelta(days=k)) for k, i in enumerate(items)]


def article(project, topic="", avoid=(), strict=False):
    sujet = f"le sujet : {topic}" if topic else "un sujet de ton choix que ma cible cherche réellement sur Google"
    eviter = ("Évite de répéter ces titres déjà publiés : " + " | ".join(avoid) + ". ") if avoid else ""
    raw = _ask(f"""Tu es rédacteur SEO pour le marché ouest-africain. Projet : {project.name} ({project.description}). Cible : {project.audience}. Offre : {project.offer}.
Écris un article de blog utile en français d'environ 500 mots sur {sujet}. {eviter}N'invente aucun prix, chiffre ou fait que tu ne peux pas savoir.
Titre accrocheur contenant le mot-clé principal, paragraphes courts séparés par une ligne vide, conclusion avec un appel à l'action vers {project.name}.
Réponds UNIQUEMENT en JSON : {{"title": "...", "keywords": "3 à 6 mots-clés séparés par des virgules", "body": "..."}}""")
    try:
        d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        if d.get("title") and d.get("body"):
            return {"title": str(d["title"])[:150], "keywords": str(d.get("keywords", ""))[:200], "body": str(d["body"])}
    except Exception:
        pass
    if strict or not topic:
        return None
    return {"title": f"{topic} : le guide pour {project.audience}"[:150], "keywords": f"{topic}, {project.name}",
            "body": f"{project.description}\n\nPourquoi {topic} compte pour {project.audience} ?\n\n{project.offer or project.description}\n\n"
                    f"Contactez {project.name} dès aujourd'hui."}

def send_telegram(text):
    tok, chat = conf("TELEGRAM_BOT_TOKEN"), conf("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage",
                               urllib.parse.urlencode({"chat_id": chat, "text": text}).encode(), timeout=10)
        return True
    except Exception:
        return False

def notify(project, a):
    from django.utils import timezone
    base = conf("BASE_URL").rstrip("/")
    txt = f"Article à valider ({project.name}) : {a.title}\nPublication automatique à {timezone.localtime(a.publish_at):%H:%M}."
    send_telegram(txt + (f"\n{base}/article/{a.pk}/modifier/" if base else ""))
