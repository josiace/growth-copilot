from django.contrib import admin
from .models import Project, Post, Click, Conversion
for m in (Project, Post, Click, Conversion):
    admin.site.register(m)
