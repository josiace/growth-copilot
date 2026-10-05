import hmac, os, re, secrets, threading
from .conf import conf
from textwrap import wrap
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape
from django.db.models import Count
from django.contrib import messages
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from . import blog_auto, services
from .forms import ArticleForm, BlogForm, PromoForm
from .models import Article, Conversion, Lead, Post, Project, Promo, Setting
from .views import _ctx

def _base(request):
    return conf("BASE_URL", "").rstrip("/") or request.build_absolute_uri("/").rstrip("/")

def _phone(raw):
    d = re.sub(r"\D", "", raw or "")
    return "223" + d if len(d) == 8 else d

# ---------- espace privé : onglet Croissance ----------
def growth(request, pk):
    p = get_object_or_404(Project, pk=pk)
    b, promo, leads = _base(request), p.promo_set.first(), []
    for l in p.lead_set.all()[:40]:
        msg = f"Bonjour {l.name}, c'est {p.name}. " + (f"Votre code : {promo.code}. " if promo else "") + "On reste à votre écoute !"
        l.wa, l.refs = f"https://wa.me/{_phone(l.phone)}?text={quote(msg)}", l.referrals.count()
        leads.append(l)
    return render(request, "clients.html", _ctx(p, "clients", leads=leads, promos=p.promo_set.all(),
        top=p.lead_set.annotate(n=Count("referrals")).filter(n__gt=0).order_by("-n")[:5], promo_form=PromoForm(),
        n_leads=p.lead_set.count(), n_clients=p.lead_set.filter(status="client").count(),
        n_refs=p.lead_set.exclude(referrer=None).count(),
        landing=b + reverse("landing", args=[pk])))

def create(request, pk):
    p = get_object_or_404(Project, pk=pk)
    b = _base(request)
    return render(request, "create.html", _ctx(p, "create", articles=p.article_set.all(), blog_form=BlogForm(instance=p),
        pending=p.article_set.filter(published=False, publish_at__isnull=False).order_by("publish_at"),
        has_ai=bool(conf("ANTHROPIC_API_KEY")), blog=b + reverse("blog_index", args=[pk])))

@require_POST
def promo_add(request, pk):
    p = get_object_or_404(Project, pk=pk)
    form = PromoForm(request.POST)
    if form.is_valid():
        x = form.save(commit=False)
        x.project = p
        x.save()
        messages.success(request, "Code promo ajouté : il s'affiche sur ta page de capture.")
    return redirect("growth", pk)

@require_POST
def promo_del(request, pk):
    x = get_object_or_404(Promo, pk=pk)
    x.delete()
    messages.success(request, "Code promo retiré.")
    return redirect("growth", x.project_id)

@require_POST
def lead_status(request, pk):
    l = get_object_or_404(Lead, pk=pk)
    order = ["nouveau", "contacté", "client"]
    l.status = order[(order.index(l.status) + 1) % 3]
    l.save()
    messages.success(request, f"{l.name} : statut « {l.status} ».")
    return redirect("growth", l.project_id)

@require_POST
def article_gen(request, pk):
    p = get_object_or_404(Project, pk=pk)
    a = Article.objects.create(project=p, **services.article(p, request.POST.get("topic", "").strip() or p.name))
    a.slug = f"{slugify(a.title)[:70]}-{a.pk}"
    a.save()
    messages.success(request, "Brouillon créé : relis-le puis publie-le.")
    return redirect("article_edit", a.pk)

def article_edit(request, pk):
    a = get_object_or_404(Article, pk=pk)
    form = ArticleForm(request.POST or None, instance=a)
    if form.is_valid():
        a = form.save()
        a.publish_at = None  # relu par toi : plus de publication automatique
        a.save()
        messages.success(request, "Article enregistré.")
        return redirect("create", a.project_id)
    return render(request, "article_form.html", _ctx(a.project, "create", form=form, a=a,
                  url=_base(request) + reverse("blog_article", args=[a.project_id, a.slug])))

@require_POST
def article_del(request, pk):
    a = get_object_or_404(Article, pk=pk)
    a.delete()
    messages.success(request, "Article supprimé.")
    return redirect("create", a.project_id)

def visual(request, pk):
    p = get_object_or_404(Project, pk=pk)
    first, promo = p.post_set.filter(status="planned").first(), p.promo_set.first()
    t = request.GET.get("t") or (promo.label if promo else (first.text.split("\n")[0][:90] if first else p.name))
    f = "story" if request.GET.get("f") == "story" else "square"
    return render(request, "visual.html", _ctx(p, "create", t=t, f=f, svg=reverse("visual_svg", args=[pk]) + "?" + urlencode({"t": t, "f": f})))

def visual_svg(request, pk):
    p = get_object_or_404(Project, pk=pk)
    w, h = (1080, 1920) if request.GET.get("f") == "story" else (1080, 1080)
    col = p.color if re.fullmatch(r"#[0-9a-fA-F]{6}", p.color or "") else "#2b3fa0"
    lines = wrap(request.GET.get("t", p.name)[:120], 18)[:6]
    size = 92 if len(lines) <= 3 else 74
    y0 = h / 2 - len(lines) * size * 0.55
    txt = "".join(f'<text x="80" y="{y0 + i * size * 1.15:.0f}" font-size="{size}" font-weight="800" fill="#fff">{escape(l)}</text>' for i, l in enumerate(lines))
    cta = f"WhatsApp : +{_phone(p.whatsapp)}" if p.whatsapp else p.url
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, Helvetica, sans-serif">'
           f'<rect width="{w}" height="{h}" fill="{col}"/><rect x="80" y="{y0 - size * 1.5:.0f}" width="160" height="14" fill="#f2b632"/>{txt}'
           f'<text x="80" y="{h - 150}" font-size="52" font-weight="700" fill="#f2b632">{escape(p.name)}</text>'
           f'<text x="80" y="{h - 80}" font-size="40" fill="#fff">{escape(cta)}</text></svg>')
    return HttpResponse(svg, content_type="image/svg+xml")

# ---------- pages publiques (SEO) ----------
def landing(request, pid):
    p = get_object_or_404(Project, pk=pid)
    lead, err, b = None, "", _base(request)
    if request.method == "POST" and not request.POST.get("site"):  # champ "site" = piège anti-robots
        name, phone = request.POST.get("name", "").strip()[:80], re.sub(r"[^\d+ ]", "", request.POST.get("phone", ""))[:20]
        if name and len(re.sub(r"\D", "", phone)) >= 8:
            post = Post.objects.filter(project=p, code=request.POST.get("src", "")).first()
            lead = Lead.objects.create(project=p, name=name, phone=phone, post=post,
                                       referrer=Lead.objects.filter(project=p, code=request.POST.get("ref", "")).first())
            Conversion.objects.create(project=p, post=post, kind="lead")
        else:
            err = "Indique ton nom et un numéro de téléphone valide."
    url = b + reverse("landing", args=[pid])
    return render(request, "landing.html", {"p": p, "lead": lead, "err": err, "promo": p.promo_set.first(), "canonical": url,
        "ref": request.GET.get("ref", request.POST.get("ref", "")), "src": request.GET.get("utm_content", request.POST.get("src", "")),
        "articles": p.article_set.filter(published=True)[:3], "wa": _phone(p.whatsapp),
        "share": url + (f"?ref={lead.code}" if lead else "")})

def blog_index(request, pid):
    p = get_object_or_404(Project, pk=pid)
    return render(request, "blog_index.html", {"p": p, "articles": p.article_set.filter(published=True),
                  "canonical": _base(request) + reverse("blog_index", args=[pid])})

def blog_article(request, pid, slug):
    a = get_object_or_404(Article, project_id=pid, slug=slug, published=True)
    desc = re.sub(r"\s+", " ", a.body).strip()[:155]
    return render(request, "article.html", {"p": a.project, "a": a, "desc": desc,
                  "canonical": _base(request) + reverse("blog_article", args=[pid, slug]), "landing": reverse("landing", args=[pid])})

def sitemap(request):
    b, urls = _base(request), []
    for p in Project.objects.all():
        urls += [b + reverse("landing", args=[p.pk]), b + reverse("blog_index", args=[p.pk])]
        urls += [b + reverse("blog_article", args=[p.pk, a.slug]) for a in p.article_set.filter(published=True)]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + \
          "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls) + "</urlset>"
    return HttpResponse(xml, content_type="application/xml")

def robots(request):
    return HttpResponse(f"User-agent: *\nDisallow: /admin/\nDisallow: /go/\nDisallow: /projet/\nSitemap: {_base(request)}/sitemap.xml\n", content_type="text/plain")

@require_POST
def article_publish(request, pk):
    a = get_object_or_404(Article, pk=pk)
    a.published, a.publish_at = True, None
    a.save()
    messages.success(request, "Article publié sur le blog.")
    return redirect("create", a.project_id)

@require_POST
def blog_auto_settings(request, pk):
    p = get_object_or_404(Project, pk=pk)
    form = BlogForm(request.POST, instance=p)
    if form.is_valid():
        form.save()
        messages.success(request, "Rythme du blog enregistré.")
    return redirect("create", pk)

_lock = threading.Lock()

def cron(request):
    key = conf("CRON_KEY", "")
    if not key or not hmac.compare_digest(request.GET.get("key", ""), key):
        return JsonResponse({"error": "clé invalide"}, status=403)
    def job():
        if _lock.acquire(blocking=False):
            try:
                blog_auto.run()
            finally:
                _lock.release()
                connection.close()
    threading.Thread(target=job, daemon=True).start()
    return JsonResponse({"ok": True})

FIELDS = [("ANTHROPIC_API_KEY", "Clé API Anthropic (écriture par IA)", True), ("ANTHROPIC_MODEL", "Modèle IA (laisse vide pour le modèle par défaut)", False),
          ("TELEGRAM_BOT_TOKEN", "Jeton du bot Telegram", True), ("TELEGRAM_CHAT_ID", "Identifiant de ta conversation Telegram", False),
          ("BASE_URL", "Adresse publique de l'outil (ex. https://growth.onrender.com)", False),
          ("BLOG_HOUR", "Heure à partir de laquelle l'IA écrit (0 à 23, défaut 7)", False),
          ("BLOG_DELAY_MINUTES", "Délai de validation avant publication automatique (minutes, défaut 60)", False)]

def app_settings(request):
    if request.method == "POST":
        act = request.POST.get("action", "save")
        if act == "save":
            for name, _, secret in FIELDS:
                val = request.POST.get(name, "").strip()
                if request.POST.get("del_" + name):
                    Setting.objects.filter(key=name).delete()
                elif name in request.POST and not (secret and not val):  # champ absent ou secret vide : on garde l'ancien
                    Setting.objects.update_or_create(key=name, defaults={"value": val})
            messages.success(request, "Paramètres enregistrés.")
        elif act == "gen_cron":
            Setting.objects.update_or_create(key="CRON_KEY", defaults={"value": secrets.token_urlsafe(24)})
            messages.success(request, "Clé de déclenchement créée. Copie l'adresse ci-dessous dans ton minuteur.")
        elif act == "test_ai":
            if not conf("ANTHROPIC_API_KEY"):
                messages.error(request, "Aucune clé Anthropic enregistrée.")
            elif services._ask("Réponds uniquement par le mot OK."):
                messages.success(request, "L'IA répond : la clé fonctionne.")
            else:
                messages.error(request, "L'IA ne répond pas : vérifie la clé, le modèle et ta connexion.")
        elif act == "test_tg":
            ok = services.send_telegram("Test Growth Copilot : tout fonctionne.")
            (messages.success if ok else messages.error)(request, "Message Telegram envoyé." if ok else "Envoi impossible : vérifie le jeton et l'identifiant (et écris d'abord un message à ton bot).")
        return redirect("app_settings")
    rows = []
    for name, label, secret in FIELDS:
        v = conf(name)
        rows.append({"name": name, "label": label, "secret": secret, "set": bool(v), "value": "" if secret else v,
                     "hint": f"•••• {v[-4:]}" if secret and v else ""})
    key = conf("CRON_KEY")
    return render(request, "app_settings.html", {"rows": rows, "has_cron": bool(key), "projects": Project.objects.all(),
        "cron_url": f"{_base(request)}{reverse('cron')}?key={key}" if key else ""})
