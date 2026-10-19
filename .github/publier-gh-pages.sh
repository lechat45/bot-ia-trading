#!/usr/bin/env bash
# Publie le dossier site/ (le tableau de bord en ligne) dans la branche gh-pages.
# GitHub Pages reste en « Deploy from a branch » : il sert la branche gh-pages, dossier racine.
# La branche est réécrite à chaque fois (un seul commit) pour rester légère.
set -euo pipefail
cd site
touch .nojekyll  # fichiers servis tels quels, sans passer par Jekyll
git init -q -b gh-pages
git config user.name "bot-ia-trading"
git config user.email "bot-ia-trading@users.noreply.github.com"
git add -A
git commit -q -m "Tableau de bord du $(date -u +'%Y-%m-%d %H:%M') UTC"
git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" gh-pages
echo "Site publié dans la branche gh-pages."
