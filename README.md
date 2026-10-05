# Growth Copilot

Copilote de contenu : il écrit tes publications, tu publies en 2 clics, il mesure ce qui ramène des clients.

## Lancer en local
    pip install -r requirements.txt
    python manage.py migrate
    export ANTHROPIC_API_KEY=sk-ant-...   # sans clé, des posts modèles sont générés
    python manage.py runserver

## Variables d'environnement
- ANTHROPIC_API_KEY : génération par IA (modèle réglable avec ANTHROPIC_MODEL)
- APP_PASSWORD : protège l'interface par mot de passe (utilisateur libre). /go/ et /api/ restent publics
- BASE_URL : adresse publique (ex. https://growth.onrender.com), utilisée dans les liens suivis
- SECRET_KEY, DEBUG=0, CSRF_TRUSTED_ORIGINS=https://ton-domaine, DB_PATH (disque persistant)

## Déployer sur Render
Build : `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
Start : `gunicorn growth.wsgi`
Important : la base est SQLite. Sur l'offre gratuite de Render, le disque est effacé à chaque redémarrage :
ajoute un disque persistant (DB_PATH=/data/db.sqlite3) ou passe à PostgreSQL avant d'avoir de vrais clients.

## Mesurer les conversions
Chaque lien /go/<code> compte le clic puis redirige vers ton site avec utm_source, utm_medium, utm_campaign et utm_content.
Quand l'inscription a lieu sur ton site : POST /api/conversion/ avec {"key": <clé du projet>, "code": <utm_content>, "kind": "order"}.
La clé du projet est affichée sous « Mesurer les inscriptions » dans la page du projet.

## Interface
Quatre onglets par projet :
- Aujourd'hui : posts à publier (copier, partager, marquer publié), mini-courbes des clics et conversions, barre de régularité et points des 7 derniers jours.
- Calendrier : vue du mois avec points colorés par canal, puis liste des posts à modifier, déplacer, supprimer ou ajouter.
- Résultats : courbe clics et conversions, entonnoir post vers commande, anneau d'origine des clics, taux de conversion par canal,
  meilleures heures et meilleurs jours pour publier, comparaison avec la période précédente et conseils chiffrés.
- Réglages : modifier le projet, clé et adresse de l'API, suppression.
Les graphiques utilisent Chart.js chargé depuis cdnjs (connexion nécessaire) ; sans connexion, les chiffres restent affichés dans les cartes.

## Croissance (onglet 5)
- Page de capture publique /p/<id>/ : nom + téléphone, code promo affiché, lien de parrainage donné après inscription (?ref=CODE),
  piège anti-robots, balises SEO (titre, description, Open Graph, JSON-LD). Chaque prospect compte aussi comme conversion « prospect ».
- Prospects : liste, statut (nouveau, contacté, client) en un clic, bouton de relance WhatsApp avec message prêt.
- Parrainage et promos : codes promo, classement des meilleurs parrains.
- Blog SEO : génération d'un article par IA (ou modèle de secours), relecture, publication sur /blog/<id>/, sitemap.xml et robots.txt.
- Visuels : affiche carrée ou vertical avec couleur de marque et contact, téléchargement PNG ou SVG.
Dans Réglages, renseigne le numéro WhatsApp et la couleur de marque. Les pages /p/, /blog/, /sitemap.xml et /robots.txt restent
publiques même avec APP_PASSWORD. Pour Google : déclare https://ton-domaine/sitemap.xml dans la Search Console.

## Blog automatique (validation sous 1 heure)
Onglet Croissance, section Blog : choisis un rythme (de 1 article par semaine à 1 par jour) et, si tu veux, une liste de sujets
(un par ligne ; sans liste, l'IA choisit des sujets que ta cible cherche sur Google, sans répéter les titres déjà publiés).
Chaque article est d'abord un **brouillon** : tu as 1 heure pour Publier, Relire ou Rejeter. Sans action, il est publié seul.
Relire puis enregistrer annule la publication automatique (coche « Publié » pour le mettre en ligne).
La génération exige ANTHROPIC_API_KEY : sans clé, rien n'est créé (jamais de texte générique publié tout seul).

Variables : CRON_KEY (obligatoire pour l'automatisme), BLOG_HOUR (heure locale à partir de laquelle l'IA écrit, défaut 7),
BLOG_DELAY_MINUTES (délai avant publication auto, défaut 60), TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID (alerte quand un brouillon est prêt ;
BASE_URL ajoute le lien de relecture).

Déclenchement : un minuteur doit appeler toutes les 5 minutes `https://ton-domaine/api/cron/?key=TA_CLE_CRON`
(service gratuit cron-job.org, ou une tâche Render avec curl). L'appel répond tout de suite et travaille en arrière-plan.
En local, tu peux lancer à la main : `python manage.py blog_auto`.

## API de conversion : montant et doublons
POST /api/conversion/ avec {"key", "code", "kind", "value", "event_id"} :
- value : montant en FCFA (commande), pour le revenu et le ROI dans l'onglet Résultats.
- event_id : identifiant unique (ex. commande-123). Le même event_id envoyé deux fois ne crée qu'une conversion (réponse "duplicate": true).
- Limite : 120 requêtes par minute et par adresse IP.
- ROI = (revenu - coût) / coût, où le coût est le « coût mensuel de ta communication » saisi dans Réglages, ramené à la période affichée.

## Tout depuis l'interface
- Menu (en haut à droite) : tous les projets, nouveau projet, réglages du projet, Paramètres généraux.
- Paramètres généraux : clé Anthropic, modèle, Telegram (avec boutons de test), adresse publique, heure et délai du blog, et création de la clé
  du minuteur avec l'adresse prête à copier. Ces réglages passent avant les variables d'environnement, qui restent un repli.
- Onglets : Aujourd'hui (avec la liste « Pour bien démarrer »), Planning, Clients, Créer, Résultats. Sur ordinateur, le menu est à gauche.
- Chaque action affiche un message de confirmation.
Seuls APP_PASSWORD (mot de passe de l'outil), SECRET_KEY et DEBUG restent à définir sur le serveur.

## Guide d'utilisation et code couleur
Le bouton « Aide » (en haut, toujours visible) ouvre le guide : principe, démarrage en 5 étapes, explication de chaque écran, liens suivis, branchement
de Condimat, code couleur, questions fréquentes et glossaire. Chaque écran a aussi un bouton « Comment ça marche ? » qui ouvre la bonne section.
Couleurs : Aujourd'hui bleu indigo, Planning turquoise, Clients orange, Créer violet, Résultats vert. États : vert = réussi ou publié, or = à faire ou à valider,
rouge = en retard ou à rejeter, gris = prévu.
