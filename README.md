# NAFDAC / SON Product Verification for Odoo

Two Odoo 19 modules that check a product's NAFDAC and SON regulatory status
automatically — in Inventory, and again at the moment a customer checks out
on an Odoo website store — and can block a sale or a warehouse transfer when
a regulated product fails or has never been checked.

📖 **Full write-up:** [The Verification Gap](https://niyid.github.io/nafdac-son-verification/linkedin-article.html)

🎥 **See it run:** a bulk end-to-end test — 25 regulated products, 5 Purchase Orders, one
verification pass, real result 11 verified / 14 failed — captured through Odoo's actual web UI via
Selenium in [`assets/demo/selenium-capture-video.mp4`](assets/demo/selenium-capture-video.mp4) and
[`assets/demo/`](assets/demo/), alongside the data-generating script
([`demo/bulk_e2e_workflow.py`](demo/bulk_e2e_workflow.py)) and the Selenium capture script
([`demo/selenium_capture.py`](demo/selenium_capture.py)). `demo/test_run_output.log` shows the
automated test suite this scenario is also asserted on: 29/29 passing.

## Download

| Module | Download |
|---|---|
| `nafdac_son_verification` — core Inventory module | [nafdac_son_verification.zip](nafdac_son_verification.zip) |
| `website_sale_nafdac_son_verification` — checkout integration | [website_sale_nafdac_son_verification.zip](website_sale_nafdac_son_verification.zip) |

Both are plain, self-contained Odoo addon zips — no build step, no extra
Python packages beyond what a standard Odoo 19 install already has.

## What each module does

### `nafdac_son_verification`
Extends `product.template`, `stock.lot`, and `stock.move.line` with
NAFDAC/SON registration fields, a pluggable verification-provider
architecture (`services/`), a full audit log
(`nafdac.son.verification.log`), configurable blocking policy on transfer
validation, a scheduled re-check cron for expired verifications, a bulk
"Verify Now" wizard, and a printable verification certificate report.

- **Depends:** `stock`, `product`, `product_expiry`, `mail`
- **Installable / not an application** — install it from Apps like any
  backend extension.

### `website_sale_nafdac_son_verification`
Bridges the core module into eCommerce checkout: live re-verification when a
shopper opens the cart or moves through checkout, a status badge on cart and
checkout order lines, a self-service "Check Authenticity" endpoint, and
payment blocking (reusing `website_sale`'s own error banner) when the
company's policy says a failed/unchecked product shouldn't be sold online.

- **Depends:** `nafdac_son_verification`, `website_sale`
- **Auto-installs** the moment both dependencies are present in a database.

## Installing

```bash
# unzip both modules into your addons path, e.g. ~/git/odoo19/addons
unzip nafdac_son_verification.zip -d /path/to/odoo/addons/
unzip website_sale_nafdac_son_verification.zip -d /path/to/odoo/addons/

# restart Odoo, then in the UI:
# Settings > Apps > Update Apps List
# search "NAFDAC", remove the "Apps" filter, install
```

Verification providers currently ship as **demo providers**: they validate
that a NAFDAC/SON registration number is well-formed, not that it is a real,
currently-registered number — neither agency currently publishes a public
real-time lookup API. Swap `services/nafdac_provider.py` /
`services/son_provider.py` for a real implementation the moment you have
credentials from NAFDAC, SON, or a licensed data partner; nothing else in
either module needs to change.

## Why this exists

Testing NAFDAC's own consumer-facing Scan2Verify app against a real product
returned no usable result — consistent with independent testing by the
[Foundation for Investigative Journalism](https://fij.ng/article/reporters-diary-i-tested-4-nafdac-drug-verification-tools-two-were-useless/).
The full article covers that test, the enforcement numbers behind Nigeria's
counterfeit-product problem, and an open invitation to NAFDAC and SON to
explain the gap.

## License

Both modules are LGPL-3, consistent with Odoo's own addon licensing.
