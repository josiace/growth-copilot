from django import forms
from .models import Article, Post, Project, Promo

FIELD = "field"

def _style(form):
    for f in form.fields.values():
        f.widget.attrs["class"] = FIELD

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "audience", "offer", "tone", "url", "channels", "whatsapp", "monthly_cost", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"}),
                   "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Ex. : livraison d'ingrédients de cuisine à domicile"}),
                   "audience": forms.TextInput(attrs={"placeholder": "Ex. : familles de Bamako"}),
                   "offer": forms.TextInput(attrs={"placeholder": "Ex. : livraison en 1 heure"}),
                   "url": forms.URLInput(attrs={"placeholder": "https://..."})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["channel", "scheduled_for", "text"]
        labels = {"channel": "Canal", "scheduled_for": "Date de publication", "text": "Texte du post"}
        widgets = {"scheduled_for": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "text": forms.Textarea(attrs={"rows": 9})}

    def __init__(self, *a, project=None, **k):
        super().__init__(*a, **k)
        choices = list(project.channel_list()) if project else []
        if self.instance.channel and self.instance.channel not in choices:
            choices.append(self.instance.channel)
        self.fields["channel"] = forms.ChoiceField(label="Canal", choices=[(c, c) for c in choices])
        self.fields["text"].help_text = "Garde {link} là où le lien suivi doit apparaître (il est ajouté à la fin si tu l'oublies)."
        _style(self)

    def clean_text(self):
        t = self.cleaned_data["text"].strip()
        return t if "{link}" in t else t + "\n\n{link}"

class PromoForm(forms.ModelForm):
    class Meta:
        model = Promo
        fields = ["code", "label"]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper().replace(" ", "")

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["title", "keywords", "body", "published"]
        widgets = {"body": forms.Textarea(attrs={"rows": 14})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)
        self.fields["published"].widget.attrs["class"] = "w-5 h-5"

class BlogForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["blog_per_week", "blog_topics"]
        widgets = {"blog_topics": forms.Textarea(attrs={"rows": 5, "placeholder": "Un sujet par ligne. Laisse vide pour que l'IA choisisse."})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)
