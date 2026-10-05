import os
from .conf import conf
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
from . import services
from .models import Article, Project

_echec = {}

def run():
    """Publie les brouillons dont le délai est écoulé, puis crée les nouveaux selon le rythme de chaque projet."""
    log, now = [], timezone.now()
    for x in Article.objects.filter(published=False, publish_at__isnull=False, publish_at__lte=now):
        x.published, x.publish_at = True, None
        x.save()
        log.append(f"Publié : {x.title}")
    if timezone.localtime(now).hour < int(conf("BLOG_HOUR", "7")):
        return log
    delay = int(conf("BLOG_DELAY_MINUTES", "60"))
    for p in Project.objects.filter(blog_per_week__gt=0):
        last = p.article_set.order_by("-created").first()
        if last and now - last.created < timedelta(days=7 / p.blog_per_week) - timedelta(minutes=30):
            continue
        if p.pk in _echec and now - _echec[p.pk] < timedelta(minutes=60):
            continue
        used = set(p.article_set.values_list("topic", flat=True))
        topic = next((t.strip() for t in p.blog_topics.splitlines() if t.strip() and t.strip() not in used), "")
        d = services.article(p, topic, avoid=list(p.article_set.values_list("title", flat=True)[:30]), strict=True)
        if not d:
            _echec[p.pk] = now
            log.append(f"{p.name} : génération impossible (clé Anthropic absente ou erreur), aucun article créé.")
            continue
        a = Article.objects.create(project=p, topic=topic, publish_at=now + timedelta(minutes=delay), **d)
        a.slug = f"{slugify(a.title)[:70]}-{a.pk}"
        a.save()
        services.notify(p, a)
        log.append(f"Brouillon créé : {a.title}")
    return log
