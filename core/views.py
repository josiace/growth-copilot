import calendar as cal
import json, os, time
from .conf import conf
from datetime import timedelta
from urllib.parse import quote, urlencode
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .forms import PostForm, ProjectForm
from .models import Click, Conversion, Post, Project
from . import services

def _ctx(p, tab, **kw):
    t = timezone.localdate()
    return {"p": p, "tab": tab, "today": t, "projects": Project.objects.all(),
            "due_count": p.post_set.filter(status="planned", scheduled_for__lte=t).count(),
            "pending_count": p.article_set.filter(published=False, publish_at__isnull=False).count(), **kw}

def _rate(conv, clicks):
    return round(100 * conv / clicks, 1) if clicks else 0

def _daily(qs, since, days):
    per = {r["d"]: r["n"] for r in qs.annotate(d=TruncDate("at")).values("d").annotate(n=Count("id"))}
    return [per.get(since + timedelta(days=i), 0) for i in range(days)]

def _spark(vals, w=96, h=28):
    m, n = (max(vals) or 1), len(vals)
    return " ".join(f"{round(i * w / max(n - 1, 1), 1)},{round(h - 2 - (v / m) * (h - 4), 1)}" for i, v in enumerate(vals))

def _delta(cur, prev):
    return round(100 * (cur - prev) / prev) if prev else None

def help_page(request, pk=None):
    if pk:
        return render(request, "help.html", _ctx(get_object_or_404(Project, pk=pk), "help"))
    return render(request, "help.html", {"tab": "help"})

def home(request):
    t = timezone.localdate()
    since = t - timedelta(days=6)
    rows = []
    for p in Project.objects.all():
        series = _daily(Click.objects.filter(post__project=p, at__date__gte=since), since, 7)
        rows.append({"p": p, "due": p.post_set.filter(status="planned", scheduled_for__lte=t).count(),
                     "clicks": sum(series), "spark": _spark(series),
                     "convs": Conversion.objects.filter(project=p, at__date__gte=since).count()})
    return render(request, "home.html", {"rows": rows})

def project_new(request):
    form = ProjectForm(request.POST or None)
    if form.is_valid():
        p = form.save()
        messages.success(request, "Projet créé. Suis la liste « Pour bien démarrer » pour le lancer.")
        return redirect("today", p.pk)
    return render(request, "form.html", {"form": form})

def _decorate(request, post):
    base = conf("BASE_URL", "").rstrip("/") or request.build_absolute_uri("/").rstrip("/")
    link = base + reverse("go", args=[post.code])
    post.final = post.text.replace("{link}", link) if "{link}" in post.text else post.text + "\n" + link
    plain = post.text.replace("{link}", "").strip()
    post.wa = "https://wa.me/?text=" + quote(post.final)
    post.tg = "https://t.me/share/url?url=" + quote(link) + "&text=" + quote(plain)
    post.fb = "https://www.facebook.com/sharer/sharer.php?u=" + quote(link)
    return post

def _published_days(p):
    return set(p.post_set.filter(status="published").values_list("published_on", flat=True))

def _streak(p, t):
    days = _published_days(p)
    d, n = (t if t in days else t - timedelta(days=1)), 0
    while d in days:
        n, d = n + 1, d - timedelta(days=1)
    return n

def _steps(p):
    u = lambda n, *a: reverse(n, args=list(a))
    return [
        {"t": "Ajouter ton numéro WhatsApp", "h": "Il apparaît sur tes visuels et ta page publique.", "d": bool(p.whatsapp), "u": u("settings", p.pk)},
        {"t": "Générer ta première semaine de posts", "h": "Un clic suffit : 7 posts prêts à copier.", "d": p.post_set.exists(), "u": u("calendar", p.pk)},
        {"t": "Publier ton premier post", "h": "Copie le texte, colle-le sur ton réseau, marque-le publié.", "d": p.post_set.filter(status="published").exists(), "u": u("today", p.pk)},
        {"t": "Activer l'écriture par IA", "h": "Colle ta clé Anthropic dans Paramètres.", "d": bool(conf("ANTHROPIC_API_KEY")), "u": u("app_settings")},
        {"t": "Brancher ton site pour mesurer les commandes", "h": "Copie la clé du projet dans ton site.", "d": p.conversion_set.exclude(kind="lead").exists(), "u": u("settings", p.pk)},
        {"t": "Partager ta page de capture", "h": "Mets-la en bio : elle collecte les prospects.", "d": p.lead_set.exists(), "u": u("growth", p.pk)},
        {"t": "Activer le blog automatique", "h": "Choisis un rythme, l'IA écrit pour toi.", "d": p.blog_per_week > 0, "u": u("create", p.pk)},
    ]

def today(request, pk):
    p = get_object_or_404(Project, pk=pk)
    t = timezone.localdate()
    planned = p.post_set.filter(status="planned")
    since = t - timedelta(days=6)
    c_series = _daily(Click.objects.filter(post__project=p, at__date__gte=since), since, 7)
    v_series = _daily(Conversion.objects.filter(project=p, at__date__gte=since), since, 7)
    pub = _published_days(p)
    week = [{"d": since + timedelta(days=i), "on": (since + timedelta(days=i)) in pub, "now": i == 6} for i in range(7)]
    week_posts = p.post_set.filter(scheduled_for__gte=since, scheduled_for__lte=t)
    reg_total, reg_done = week_posts.count(), week_posts.filter(status="published").count()
    top = p.post_set.values("channel").annotate(c=Count("click")).order_by("-c").first()
    tip = f"Ton meilleur canal en ce moment : {top['channel']}." if top and top["c"] else \
          "Publie quelques posts par leurs liens pour savoir quel canal ramène des clients."
    steps = _steps(p)
    return render(request, "today.html", _ctx(p, "today", steps=steps, steps_done=sum(x["d"] for x in steps),
        due=[_decorate(request, x) for x in planned.filter(scheduled_for__lte=t)],
        done=p.post_set.filter(status="published", published_on=t).count(),
        upcoming=planned.filter(scheduled_for__gt=t)[:3], has_plan=planned.exists(), streak=_streak(p, t), tip=tip,
        clicks=sum(c_series), convs=sum(v_series), c_spark=_spark(c_series), v_spark=_spark(v_series), week=week,
        reg_total=reg_total, reg_done=reg_done, reg_pct=round(100 * reg_done / reg_total) if reg_total else 0))

def calendar(request, pk):
    p = get_object_or_404(Project, pk=pk)
    t = timezone.localdate()
    grid = cal.Calendar(0).monthdatescalendar(t.year, t.month)
    by_day = {}
    for x in p.post_set.filter(scheduled_for__gte=grid[0][0], scheduled_for__lte=grid[-1][-1]):
        by_day.setdefault(x.scheduled_for, []).append(x)
    weeks = [[{"d": d, "in_month": d.month == t.month, "posts": by_day.get(d, [])} for d in w] for w in grid]
    posts = p.post_set.filter(scheduled_for__gte=t - timedelta(days=7)).order_by("scheduled_for", "id")
    return render(request, "calendar.html", _ctx(p, "calendar", posts=posts, weeks=weeks))

KIND = {"signup": "inscription", "order": "commande", "lead": "prospect"}

def results(request, pk):
    p = get_object_or_404(Project, pk=pk)
    t = timezone.localdate()
    days = 30 if request.GET.get("j") == "30" else 7
    since = t - timedelta(days=days - 1)
    before = since - timedelta(days=days)
    clicks_qs = Click.objects.filter(post__project=p, at__date__gte=since)
    conv_qs = Conversion.objects.filter(project=p, at__date__gte=since)
    c_series, v_series = _daily(clicks_qs, since, days), _daily(conv_qs, since, days)
    n_clicks, n_conv = sum(c_series), sum(v_series)
    rev = conv_qs.aggregate(s=Sum("value"))["s"] or 0
    prev_rev = Conversion.objects.filter(project=p, at__date__gte=before, at__date__lt=since).aggregate(s=Sum("value"))["s"] or 0
    cost = round(p.monthly_cost * days / 30)
    roi = round(100 * (rev - cost) / cost) if cost else None
    prev_c = Click.objects.filter(post__project=p, at__date__gte=before, at__date__lt=since).count()
    prev_v = Conversion.objects.filter(project=p, at__date__gte=before, at__date__lt=since).count()
    chan = {}
    for r in clicks_qs.values("post__channel").annotate(n=Count("id")):
        chan.setdefault(r["post__channel"], {"c": 0, "v": 0})["c"] = r["n"]
    for r in conv_qs.exclude(post=None).values("post__channel").annotate(n=Count("id")):
        chan.setdefault(r["post__channel"], {"c": 0, "v": 0})["v"] = r["n"]
    revs = {r["post__channel"]: r["s"] for r in conv_qs.exclude(post=None).values("post__channel").annotate(s=Sum("value"))}
    rows = sorted(({"channel": k, "clicks": v["c"], "convs": v["v"], "rate": _rate(v["v"], v["c"]), "rev": revs.get(k, 0) or 0}
                   for k, v in chan.items()), key=lambda r: (-r["rev"], -r["convs"], -r["clicks"]))
    hours, weekdays = [0] * 24, [0] * 7
    for r in clicks_qs.annotate(h=ExtractHour("at")).values("h").annotate(n=Count("id")):
        hours[r["h"]] = r["n"]
    for r in clicks_qs.annotate(w=ExtractWeekDay("at")).values("w").annotate(n=Count("id")):
        weekdays[(r["w"] + 5) % 7] = r["n"]
    kinds = [f'{r["n"]} {KIND.get(r["kind"], r["kind"])}{"s" if r["n"] > 1 else ""}'
             for r in conv_qs.values("kind").annotate(n=Count("id")).order_by("-n")]
    tips = []
    if n_clicks and max(hours):
        h = hours.index(max(hours))
        tips.append(f"Tes visiteurs cliquent surtout vers {h} h : publie un peu avant.")
    if n_clicks and max(weekdays):
        tips.append(f"Meilleur jour : {['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche'][weekdays.index(max(weekdays))]}.")
    if rows and rows[0]["rev"]:
        tips.append(f"Le canal qui rapporte le plus : {rows[0]['channel']} ({rows[0]['rev']:,} FCFA).".replace(",", " "))
    elif rows and rows[0]["convs"]:
        tips.append(f"Le canal qui convertit le mieux : {rows[0]['channel']} ({rows[0]['rate']} % de ses clics).")
    elif rows:
        tips.append("Des clics mais aucune conversion : vérifie que la clé API est branchée sur ton site (Réglages).")
    best = p.post_set.annotate(c=Count("click", distinct=True), v=Count("conversion", distinct=True)) \
            .filter(c__gt=0).order_by("-v", "-c")[:5]
    for x in best:
        x.rev = x.conversion_set.aggregate(s=Sum("value"))["s"] or 0
    n_posts = p.post_set.filter(status="published", published_on__gte=since).count()
    chart = {"labels": [(since + timedelta(days=i)).strftime("%d/%m") for i in range(days)], "clicks": c_series, "convs": v_series,
             "channels": [r["channel"] for r in rows], "ch_clicks": [r["clicks"] for r in rows],
             "ch_rate": [r["rate"] for r in rows], "ch_convs": [r["convs"] for r in rows],
             "hours": hours, "weekdays": weekdays}
    return render(request, "results.html", _ctx(p, "results", days=days, n_clicks=n_clicks, n_conv=n_conv, n_posts=n_posts,
        rate=_rate(n_conv, n_clicks), d_clicks=_delta(n_clicks, prev_c), d_conv=_delta(n_conv, prev_v),
        rev=rev, d_rev=_delta(rev, prev_rev), roi=roi, cost=cost, rev_per_click=round(rev / n_clicks) if n_clicks else 0,
        per_post=round(n_clicks / n_posts, 1) if n_posts else 0, funnel_w=max(_rate(n_conv, n_clicks), 4),
        rows=rows, best=best, tips=tips, kinds=kinds, chart=chart, unlinked=conv_qs.filter(post=None).count()))

def project_settings(request, pk):
    p = get_object_or_404(Project, pk=pk)
    form = ProjectForm(request.POST or None, instance=p)
    if form.is_valid():
        form.save()
        messages.success(request, "Réglages enregistrés.")
        return redirect("settings", pk)
    return render(request, "settings.html", _ctx(p, "settings", form=form,
                  api=request.build_absolute_uri(reverse("conversion"))))

@require_POST
def project_delete(request, pk):
    get_object_or_404(Project, pk=pk).delete()
    messages.success(request, "Projet supprimé.")
    return redirect("home")

@require_POST
def generate_view(request, pk):
    p = get_object_or_404(Project, pk=pk)
    last = p.post_set.order_by("-scheduled_for").first()
    start = max(timezone.localdate(), last.scheduled_for + timedelta(days=1)) if last else timezone.localdate()
    services.generate(p, 7, start)
    messages.success(request, "7 nouveaux posts ajoutés au planning.")
    return redirect(request.POST.get("next") or reverse("today", args=[pk]))

def post_add(request, pk):
    p = get_object_or_404(Project, pk=pk)
    form = PostForm(request.POST or None, project=p, initial={"scheduled_for": timezone.localdate(), "text": "\n\n{link}"})
    if form.is_valid():
        x = form.save(commit=False)
        x.project = p
        x.save()
        messages.success(request, "Post ajouté au planning.")
        return redirect("calendar", pk)
    return render(request, "post_form.html", _ctx(p, "calendar", form=form, post=None))

def post_edit(request, pk):
    x = get_object_or_404(Post, pk=pk)
    form = PostForm(request.POST or None, instance=x, project=x.project)
    if form.is_valid():
        form.save()
        messages.success(request, "Modifications enregistrées.")
        return redirect("calendar", x.project_id)
    return render(request, "post_form.html", _ctx(x.project, "calendar", form=form, post=x))

@require_POST
def post_delete(request, pk):
    x = get_object_or_404(Post, pk=pk)
    x.delete()
    messages.success(request, "Post supprimé.")
    return redirect("calendar", x.project_id)

@require_POST
def publish(request, pk):
    x = get_object_or_404(Post, pk=pk)
    x.status, x.published_on = "published", timezone.localdate()
    x.save()
    messages.success(request, "Post marqué comme publié. Bien joué !")
    return redirect("today", x.project_id)

@require_POST
def regenerate(request, pk):
    x = get_object_or_404(Post, pk=pk)
    services.generate(x.project, 1, x.scheduled_for, [x.channel])
    x.delete()
    messages.success(request, "Post remplacé par une nouvelle version.")
    return redirect("today", x.project_id)

def go(request, code):
    x = get_object_or_404(Post, code=code)
    Click.objects.create(post=x)
    sep = "&" if "?" in x.project.url else "?"
    return redirect(x.project.url + sep + urlencode({"utm_source": x.channel, "utm_medium": "social",
                    "utm_campaign": "growth-copilot", "utm_content": x.code}))

def _limited(request):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "?")
    k = f"rl:{ip}:{int(time.time() // 60)}"
    cache.add(k, 0, 90)
    return cache.incr(k) > 120

def ping(request):
    """Vérifie une clé sans rien enregistrer (utilisé par le bouton « Tester la connexion » de Condimat)."""
    if _limited(request):
        return JsonResponse({"error": "trop de requêtes"}, status=429)
    p = Project.objects.filter(token=request.GET.get("key", "")).first()
    if not p:
        return JsonResponse({"error": "clé inconnue"}, status=403)
    return JsonResponse({"ok": True, "projet": p.name})

@csrf_exempt
@require_POST
def conversion(request):
    if _limited(request):
        return JsonResponse({"error": "trop de requêtes"}, status=429)
    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    except ValueError:
        return JsonResponse({"error": "json invalide"}, status=400)
    p = Project.objects.filter(token=data.get("key", "")).first()
    if not p:
        return JsonResponse({"error": "clé inconnue"}, status=403)
    try:
        value = max(0, int(float(data.get("value", 0) or 0)))
    except (TypeError, ValueError):
        return JsonResponse({"error": "value doit être un nombre"}, status=400)
    fields = {"kind": str(data.get("kind", "signup"))[:40], "value": value,
              "post": Post.objects.filter(project=p, code=data.get("code", "")).first()}
    event_id = str(data.get("event_id", ""))[:80]
    if event_id:  # idempotence : le même événement envoyé deux fois ne compte qu'une fois
        _, created = Conversion.objects.get_or_create(project=p, event_id=event_id, defaults=fields)
        return JsonResponse({"ok": True, "duplicate": not created})
    Conversion.objects.create(project=p, **fields)
    return JsonResponse({"ok": True})
