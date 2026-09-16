#!/usr/bin/env python3
"""
Capture REAL browser screenshots + a screen-recorded video of the NAFDAC/SON
verification workflow through Odoo's actual web UI.

Run this on your own machine (niyidpv), where a normal Chromium install and
network access are available - it can't run inside Claude's sandboxed
container (no route to download a browser there).

Setup (one-time):
    pip install playwright
    playwright install chromium

Usage:
    python3 playwright_browser_capture.py \
        --url http://localhost:8069 \
        --db odoo_demo \
        --user admin \
        --password admin \
        --vendor "Lagos Pharma Distributors Ltd" \
        --product "Paracetamol 500mg Tablets (100-pack)" \
        --reg-number A4-1234 \
        --outdir ./capture

This assumes the vendor/product above already exist (e.g. from
workflow_demo.py, run once via `odoo-bin shell` against the same database)
OR that you've created them yourself - the script only drives the UI, it
does not seed data.

Output:
    <outdir>/screenshots/NN_description.png  - one per workflow step
    <outdir>/video/*.webm                    - full session recording
      (re-encode to mp4 with: ffmpeg -i input.webm output.mp4)
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def shot(page, outdir, n, name):
    path = Path(outdir) / "screenshots" / f"{n:02d}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [screenshot] {path}")


def run(args):
    outdir = Path(args.outdir)
    (outdir / "screenshots").mkdir(parents=True, exist_ok=True)
    (outdir / "video").mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(outdir / "video"),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()

        # --- 1. Log in ---
        page.goto(f"{args.url}/odoo/login")
        page.fill("input[name='login']", args.user)
        page.fill("input[name='password']", args.password)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 1, "login")

        # --- 2. Open Purchase app, create + confirm a PO ---
        page.goto(f"{args.url}/odoo/purchase")
        page.wait_for_load_state("networkidle")
        page.click(".o_list_button_add, .o-kanban-button-new")
        page.wait_for_timeout(500)
        page.fill("input[placeholder='Vendor']", args.vendor)
        page.wait_for_timeout(800)
        page.keyboard.press("Enter")
        page.click("a:has-text('Add a product')")
        page.fill("input[placeholder='Search a product']", args.product)
        page.wait_for_timeout(800)
        page.keyboard.press("Enter")
        shot(page, outdir, 2, "purchase_order_draft")
        page.click("button:has-text('Confirm Order')")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 3, "purchase_order_confirmed")

        # --- 3. Open the generated receipt and validate it ---
        page.click("button:has-text('Receipt')")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 4, "receipt_before_validate")
        # Assign/confirm the lot number if the UI prompts for it, then validate.
        page.click("button:has-text('Validate')")
        page.wait_for_timeout(500)
        if page.locator("button:has-text('Apply')").count():
            page.click("button:has-text('Apply')")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 5, "receipt_validated")

        # --- 4. Run NAFDAC/SON verification from the product or lot record ---
        page.goto(f"{args.url}/odoo/inventory")
        page.wait_for_load_state("networkidle")
        page.click("a:has-text('Lots/Serial Numbers')")
        page.wait_for_load_state("networkidle")
        page.click(f"td:has-text('{args.reg_number}')")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 6, "lot_before_verification")
        page.click("button:has-text('Verify Now')")
        page.wait_for_load_state("networkidle")
        shot(page, outdir, 7, "lot_after_verification")

        # --- 5. Open/print the verification certificate report ---
        page.click("button:has-text('Print'), .fa-print")
        page.wait_for_timeout(500)
        if page.locator("a:has-text('Verification Certificate')").count():
            with context.expect_page() as new_page_info:
                page.click("a:has-text('Verification Certificate')")
            report_page = new_page_info.value
            report_page.wait_for_load_state("networkidle")
            shot(report_page, outdir, 8, "verification_certificate")

        context.close()
        browser.close()
        print(f"\nDone. Screenshots in {outdir}/screenshots/, video in {outdir}/video/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Base URL of your Odoo instance, e.g. http://localhost:8069")
    parser.add_argument("--db", required=True, help="Database name (selected on the login screen if prompted)")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--vendor", default="Lagos Pharma Distributors Ltd")
    parser.add_argument("--product", default="Paracetamol 500mg Tablets (100-pack)")
    parser.add_argument("--reg-number", default="A4-1234")
    parser.add_argument("--outdir", default="./capture")
    parser.add_argument("--headless", action="store_true", default=False,
                         help="Run headless (default: headed, so you can watch/debug the run)")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        print(f"\nFAILED at some step: {exc}", file=sys.stderr)
        print("Selectors above target Odoo 19's standard web client markup and "
              "may need small tweaks for menu labels/customizations in your "
              "instance - run with --headless left off to watch it live and "
              "adjust the failing selector.", file=sys.stderr)
        sys.exit(1)
