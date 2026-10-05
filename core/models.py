import uuid
from django.db import models

def new_token():
    return uuid.uuid4().hex

def new_code():
    return uuid.uuid4().hex[:8]

class Project(models.Model):
    name = models.CharField("Nom du projet", max_length=80)
    description = models.TextField("Ce que fait le produit")
    audience = models.CharField("Cible", max_length=200)
    offer = models.CharField("Offre / promesse", max_length=200, blank=True)
    tone = models.CharField("Ton", max_length=80, default="chaleureux et direct")
    url = models.URLField("Lien de destination (site, WhatsApp, Telegram…)")
    channels = models.CharField("Canaux (séparés par des virgules)", max_length=120,
                                default="whatsapp,facebook,tiktok,telegram")
    monthly_cost = models.PositiveIntegerField("Coût mensuel de ta communication en FCFA (publicité, data, temps payé)", default=0)
    blog_per_week = models.PositiveSmallIntegerField("Rythme du blog automatique", default=0,
        choices=[(0, "Désactivé"), (1, "1 article par semaine"), (2, "2 par semaine"), (3, "3 par semaine"), (5, "5 par semaine"), (7, "1 article par jour")])
    blog_topics = models.TextField("Sujets à traiter (un par ligne)", blank=True)
    color = models.CharField("Couleur de marque", max_length=7, default="#2b3fa0")
    whatsapp = models.CharField("Numéro WhatsApp (avec indicatif, ex. 22370000000)", max_length=20, blank=True)
    token = models.CharField(max_length=32, default=new_token, editable=False)

    def channel_list(self):
        return [c.strip() for c in self.channels.split(",") if c.strip()] or ["whatsapp"]

    def __str__(self):
        return self.name

class Post(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    channel = models.CharField(max_length=20)
    text = models.TextField()
    scheduled_for = models.DateField()
    status = models.CharField(max_length=10, default="planned")
    published_on = models.DateField(null=True, blank=True)
    code = models.CharField(max_length=8, unique=True, default=new_code)

    class Meta:
        ordering = ["scheduled_for", "id"]

class Click(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    at = models.DateTimeField(auto_now_add=True)

class Conversion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=40, default="signup")
    value = models.PositiveIntegerField(default=0)
    event_id = models.CharField(max_length=80, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "event_id"], condition=~models.Q(event_id=""), name="uniq_event")]

class Lead(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    status = models.CharField(max_length=10, default="nouveau")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL)
    referrer = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals")
    code = models.CharField(max_length=8, unique=True, default=new_code)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

class Promo(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    code = models.CharField("Code promo", max_length=20)
    label = models.CharField("Offre (ex. -10 % sur la 1re commande)", max_length=120)

class Article(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    title = models.CharField("Titre", max_length=150)
    slug = models.SlugField(max_length=90, blank=True)
    keywords = models.CharField("Mots-clés (séparés par des virgules)", max_length=200, blank=True)
    body = models.TextField("Texte (une ligne vide entre les paragraphes)")
    published = models.BooleanField("Publié sur le blog", default=False)
    topic = models.CharField(max_length=150, blank=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

class Setting(models.Model):
    key = models.CharField(max_length=60, unique=True)
    value = models.TextField(blank=True)
