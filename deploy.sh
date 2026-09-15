#!/usr/bin/env bash
# Deploys this repo to GitHub and publishes it via GitHub Pages so that
# https://niyid.github.io/nafdac-son-verification/linkedin-article.html
# resolves to the article in this folder.
#
# Prerequisites (on niyidpv):
#   - git, and the GitHub CLI (`gh`) installed and authenticated: gh auth login
#   - run this script from inside the repo root (the folder this file is in)

set -euo pipefail

REPO_NAME="nafdac-son-verification"
GH_USER="niyid"

echo "==> Initialising git repository"
git init -b main
git add -A
git commit -m "Initial commit: NAFDAC/SON verification Odoo modules + LinkedIn article

- nafdac_son_verification.zip: core Inventory verification module
  (product/lot regulatory fields, pluggable provider architecture,
  audit log, transfer-blocking policy, scheduled re-checks, wizard,
  printable certificate report) - downloadable as-is, not exploded
- website_sale_nafdac_son_verification.zip: eCommerce checkout
  integration (live re-verification, cart/checkout badges, self-service
  check endpoint, payment blocking) - downloadable as-is, not exploded
- linkedin-article.html: published article documenting the build and
  the Scan2Verify verification test, with download links for both
  module zips
- assets/: header image and Scan2Verify test screenshots referenced by
  the article
- README.md: module docs, download table, and install instructions"

echo "==> Creating GitHub repository ${GH_USER}/${REPO_NAME} and pushing"
gh repo create "${GH_USER}/${REPO_NAME}" \
  --public \
  --source=. \
  --remote=origin \
  --description "Odoo 19 modules for NAFDAC/SON product verification at checkout, and the article documenting the build" \
  --push

echo "==> Enabling GitHub Pages (serving from main branch, repo root)"
gh api -X POST "repos/${GH_USER}/${REPO_NAME}/pages" \
  -f "source[branch]=main" \
  -f "source[path]=/" \
  || gh api -X PUT "repos/${GH_USER}/${REPO_NAME}/pages" \
       -f "source[branch]=main" \
       -f "source[path]=/"

echo "==> Done."
echo "    Repo:  https://github.com/${GH_USER}/${REPO_NAME}"
echo "    Pages: https://${GH_USER}.github.io/${REPO_NAME}/linkedin-article.html"
echo "    (Pages can take a minute or two to build after first enable — check"
echo "     the Actions tab or Settings > Pages on the repo if it 404s at first.)"
