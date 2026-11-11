# Application de pétition en ligne certifiée ProConnect et Grist

Composant unifié d'émargement nominatif, de suivi de mobilisation et de gestion des soutiens pour pétition officielle, hébergé sur GitHub Pages et adossé à l'infrastructure souveraine Grist (DINUM).

## Architecture et fonctionnement

Le système repose sur une séparation stricte des rôles :

1. **Portail public (GitHub Pages)** :
   * Consultation libre et immédiate de l'argumentaire, du compteur de mobilisation, de la jauge et du mur des soutiens publics sans nécessiter de compte préalable.
   * Authentification sécurisée via ProConnect dans une fenêtre surgissante dédiée sans recharger ni quitter la page principale.
   * Prise en compte immédiate de l'émargement, de la mise à jour des observations ou du retrait direct du soutien.
   * Affichage dynamique des mentions d'information RGPD issues de la base Grist.
   * Export CSV strictement réservé aux gestionnaires authentifiés.

2. **Base de données souveraine (Grist / DINUM)** :
   * Document de référence : `h7dMrfKpDEApR4qtufvo4i`.
   * Règles d'accès (ACL) garantissant la confidentialité des adresses de courriel, l'unicité de signature par agent, l'intégrité infalsifiable du nom et de la date d'émargement, et le droit à l'effacement direct (retrait de signature).

## Fichiers du projet

* `index.html` : application autonome unifiée (HTML, CSS et JavaScript) fonctionnant à la fois en mode portail GitHub Pages et en composant intégré dans Grist.
* Déploiement GitHub Pages : dépôt `https://github.com/a-maurin/grist-petition-widget` accessible publiquement sur `https://a-maurin.github.io/grist-petition-widget/`.
