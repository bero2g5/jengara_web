# Jengara and Ribyos websites

This repository contains two independently deployable marketing websites:

| Website | Document root | Production domain |
| --- | --- | --- |
| Jengara | Repository root | `jengara.ai` |
| Ribyos | `ribyos-site/` | `ribyos.ai` |

Jengara includes the rebuilt homepage, Labs at `/labs/`, and the product introduction at `/ribyos/`. Existing advisory pages, articles, resources, PDF downloads and the PHP contact endpoint remain available. Shared navigation and visual styling connect the whole website.

Ribyos has its own visual identity, navigation, stylesheet, JavaScript, local fonts, social image, robots file and sitemap. Its assets use relative URLs so the folder can be deployed as a document root or reviewed at `/ribyos-site/` within this checkout.

## Development

No frontend installation or build is required. Jengara needs PHP 8.1 or newer; Ribyos needs only a static HTTP server. Use the existing checkout; a separate Git worktree is unnecessary.

The prepared Codex cloud environment provides PHP and a local-only mail transport:

```bash
export PATH="/workspace/.cloud-setup/jengara_web/bin:$PATH"
cd /workspace/jengara_web
bash /workspace/.cloud-setup/jengara_web/start.sh
```

The Jengara development server listens on port 8080. It captures contact submissions as `.eml` files outside the web root under `/workspace/.cloud-setup/jengara_web/runtime/mail`. No email is delivered by this development transport. `JENGARA_DEV_PORT`, `JENGARA_DEV_MAIL_DIR` and `JENGARA_MAIL_RATE_DIR` can override the local defaults.

To serve Ribyos independently:

```bash
python3 -m http.server 8081 --bind 127.0.0.1 --directory ribyos-site
```

Outside the prepared cloud environment, use PHP's development server for Jengara with a supported local email capture transport. A plain `php -S` command inherits the machine's mail configuration; the automated tests explicitly install their own temporary capture transport.

The PHP development server does not process `.htaccess`. Production redirects are a hosting check.

## What the product previews do

- Studio, Enterprise and Marketplace tabs switch between interactive product concepts, including arrow-key, Home and End navigation.
- The Studio walkthrough highlights the proposed steps of a research workflow. It does not execute agents, call models or process documents.
- Workflow filters select business-function or industry packs. Each detail dialog explains the business problem, inputs, agent roles, output, permissions, human review and proposed success criterion.
- Native FAQ disclosures and workflow dialogs support keyboard use. Escape closes a dialog and restores focus to its trigger.
- Animated graphics, entrance effects and scroll reveals respect reduced-motion preferences. Content remains available when JavaScript or motion support is absent.
- Ribyos contact links lead to Jengara's existing form with Labs collaboration preselected and a Ribyos-specific heading.

Ribyos is in product definition and development planning. Product previews are simulations. The website makes no production-platform, customer, certification, pricing or benchmark claims. Architecture, model providers, deployment and licensing decisions remain open.

## Checks

Install browser test tools in an isolated Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install --with-deps chromium
PHP_BINARY=/path/to/php .venv/bin/python -m unittest discover -s tests -v
```

In the prepared cloud environment, Python, Playwright and system Chromium are already available:

```bash
PHP_BINARY=/workspace/.cloud-setup/jengara_web/bin/php python3 -m unittest discover -s tests -v
node --check site.js
node --check ribyos-site/assets/site.js
/workspace/.cloud-setup/jengara_web/bin/php -l contact-submit.php
```

Tests start and stop their own Jengara and standalone Ribyos servers. They use temporary mail and rate-limit storage and never send real email. `TEST_CHROMIUM` can select a Chromium executable; otherwise the tests use system Chromium or Playwright's installed browser.

Coverage includes all HTML pages and linked local assets, PDF downloads, eight page layouts at five viewport widths, mobile menus, product tabs, animated and reduced-motion walkthroughs, six workflow dialogs, filters, FAQ interactions, metadata, self-hosted assets, contact prefilling, browser submission, endpoint validation and rate limiting. GitHub Actions runs the syntax and website checks on pushes and pull requests.

## Deployment

### Jengara

Deploy the website files from the repository root to the existing PHP-capable hosting document root. Keep `ribyos-site/`, `.github/`, `tests/`, Python environments, documentation and development dependencies out of that production document root. Retain the production mail transport and keep rate-limit storage and any mail configuration outside the web root. Do not deploy the cloud development capture transport as a production mail service.

The Jengara product links point to `https://ribyos.ai/`, including platform and workflow section anchors. Verify `/ribyos/`, the retained download URLs and the production contact journey after release.

### Ribyos

Publish **the contents of `ribyos-site/` as the document root** on a static hosting service. No build command is needed. Keep `assets/workflows.json` accessible because it supplies the workflow detail dialogs.

Add `ribyos.ai` to that hosting service and use the DNS records it supplies at the domain registrar. Apex A/ALIAS/CNAME requirements depend on the selected host; do not invent record values. Add `www.ribyos.ai` if wanted, redirect it to the apex, and enable HTTPS and HTTP-to-HTTPS redirects through the host. Canonical metadata, robots, sitemap and social URLs already use `https://ribyos.ai/`.

Before switching traffic, verify that the deployed site loads its fonts, CSS, JavaScript, workflow JSON and PNG social image; product tabs, filters, dialogs and the contact links work; and robots and sitemap are reachable. Ribyos uses no account service or data-collection backend. Enquiries are handled through Jengara's existing contact form.

This change prepares the websites and deployment instructions. It does not publish either site or modify DNS.

## Files to edit

- `index.html`, `labs/index.html`, `ribyos/index.html`: Jengara's primary new pages.
- `assets/jengara.css`: shared visual system and animation, also used by retained pages.
- `site.js`: Jengara navigation, reveals and contact handling.
- `ribyos-site/index.html`: standalone product site.
- `ribyos-site/assets/site.css` and `site.js`: Ribyos visual system and interactions.
- `ribyos-site/assets/workflows.json`: planned workflow descriptions.

Fonts are self-hosted Manrope and DM Sans from Fontsource, with the accompanying SIL Open Font License files in each site's fonts directory. No Google Fonts or other third-party runtime requests are needed.
