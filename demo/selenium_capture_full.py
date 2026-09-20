"""
Selenium-driven, fully automated capture of the COMPLETE NAFDAC/SON loop
through Odoo's real web UI:

  MANUFACTURE (mrp_nafdac_son_registration)
      -> Manufacturing Orders list -> a produced order -> its captured
         evidence (photo, batch/lot, product snapshot) -> the regulator
         submission queue showing the real (stubbed) failure state
  INVENTORY (nafdac_son_verification)
      -> Purchase Orders -> receipt -> Lots/Serial Numbers bulk results
         -> a verified lot -> printed certificate -> a failed lot

Screenshots are captured at every step via Selenium itself
(driver.save_screenshot). See build_video_from_screenshots.py for turning
them into a video, and selenium_capture.py for the original
(pre-manufacturing) version of this script.
"""
import time
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://localhost:8069"
OUTDIR = Path("./selenium_screenshots_full")
OUTDIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR = Path("./selenium_downloads_full")

# Real Chrome-for-Testing binary + exact-matching chromedriver, resolved
# locally because Selenium Manager's default download host
# (googlechromelabs.github.io) isn't reachable from this network.
CHROMIUM_BIN = "/opt/google/chrome/chrome"
from chromedriver_py import binary_path as CHROMEDRIVER_BIN  # noqa: E402


def build_driver(headless: bool):
    opts = Options()
    if CHROMIUM_BIN:
        opts.binary_location = CHROMIUM_BIN
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--window-position=0,0")
    service = Service(executable_path=CHROMEDRIVER_BIN)
    driver = webdriver.Chrome(service=service, options=opts)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": str(DOWNLOAD_DIR.resolve()),
    })
    return driver


def shot(driver, n, name):
    path = OUTDIR / f"{n:02d}_{name}.png"
    driver.save_screenshot(str(path))
    print(f"  [screenshot] {path.name}")
    time.sleep(1.0)


def run(headless: bool):
    driver = build_driver(headless)
    wait = WebDriverWait(driver, 20)
    n = 0

    def next_n():
        nonlocal n
        n += 1
        return n

    try:
        print("STEP 1: Log in")
        driver.get(f"{BASE_URL}/odoo/login")
        wait.until(EC.visibility_of_element_located((By.NAME, "login"))).send_keys("admin")
        driver.find_element(By.NAME, "password").send_keys("admin")
        shot(driver, next_n(), "login_form")
        driver.find_element(By.CSS_SELECTOR, "button.btn-primary[type='submit']").click()
        wait.until(lambda d: "/odoo/login" not in d.current_url)
        time.sleep(2)
        shot(driver, next_n(), "home_after_login")

        # ------------------------------------------------------------------
        # MANUFACTURING STAGE
        # ------------------------------------------------------------------
        print("STEP 2: Manufacturing Orders list (produced batches)")
        driver.get(f"{BASE_URL}/odoo/manufacturing")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        # The default view filters to "To Do" (open) orders only, which hides
        # every order we've already finished producing - clear it so the real
        # completed batches (not the empty-state sample placeholder rows) show.
        try:
            for facet_remove in driver.find_elements(By.CSS_SELECTOR, ".o_facet_remove"):
                facet_remove.click()
                time.sleep(0.5)
        except Exception as exc:
            print(f"  (could not clear default filter: {exc})")
        time.sleep(1)
        shot(driver, next_n(), "manufacturing_orders_list")

        print("STEP 3: Open a completed Manufacturing Order")
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, ".o_data_row")
            target_row = None
            for row in rows:
                if "Done" in row.text:
                    target_row = row
                    break
            target_row = target_row or (rows[0] if rows else None)
            if target_row is not None:
                cell = target_row.find_elements(By.CSS_SELECTOR, ".o_data_cell")[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cell)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", cell)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, next_n(), "manufacturing_order_detail")
        except Exception as exc:
            print(f"  (could not open MO: {exc})")

        print("STEP 4: Open its NAFDAC/SON Evidence smart button")
        try:
            driver.find_element(
                By.XPATH,
                "//button[@name='action_view_nafdac_son_evidence']",
            ).click()
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, next_n(), "mo_evidence_smart_button_list")

            print("STEP 5: Open the evidence record itself")
            evidence_rows = driver.find_elements(By.CSS_SELECTOR, ".o_data_row")
            if evidence_rows:
                evidence_rows[0].click()
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
                time.sleep(1.5)
                shot(driver, next_n(), "manufacturing_evidence_detail")

                print("STEP 6: Open the Product Record Snapshot tab")
                try:
                    driver.find_element(
                        By.XPATH, "//a[contains(., 'Product Record Snapshot')]"
                    ).click()
                    time.sleep(1)
                    shot(driver, next_n(), "manufacturing_evidence_snapshot")
                except Exception as exc:
                    print(f"  (snapshot tab skipped: {exc})")
        except Exception as exc:
            print(f"  (evidence smart button skipped: {exc})")

        print("STEP 7: Regulatory Submission Queue - the real stub-failure state")
        try:
            driver.get(f"{BASE_URL}/odoo/manufacturing")
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1)
            driver.find_element(
                By.CSS_SELECTOR, "button[data-menu-xmlid='mrp.menu_mrp_manufacturing']"
            ).click()
            time.sleep(0.8)
            for item in driver.find_elements(By.CSS_SELECTOR, ".dropdown-item, .o-dropdown-item"):
                if item.text.strip() == "Submission Queue":
                    item.click()
                    break
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, next_n(), "regulatory_submission_queue")
        except Exception as exc:
            print(f"  (submission queue skipped: {exc})")

        # ------------------------------------------------------------------
        # INVENTORY / CHECKOUT-SIDE STAGE (as in the original capture)
        # ------------------------------------------------------------------
        print("STEP 8: Purchase Orders list (bulk data - multiple POs)")
        driver.get(f"{BASE_URL}/odoo/purchase")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, next_n(), "purchase_orders_list")

        print("STEP 9: Open first Purchase Order (confirmed, with receipt)")
        driver.find_elements(By.CSS_SELECTOR, ".o_data_row")[0].click()
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, next_n(), "purchase_order_detail")

        print("STEP 10: Open the receipt from this PO")
        try:
            driver.find_element(By.XPATH, "//button[contains(., 'Receipt')]").click()
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, next_n(), "inventory_receipt_detail")
        except Exception as exc:
            print(f"  (could not open receipt smart button: {exc})")

        print("STEP 11: Lots/Serial Numbers list - the bulk verification results")
        driver.get(f"{BASE_URL}/odoo/inventory/lots")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, next_n(), "lots_list_bulk_results")

        print("STEP 12: Filter to Verified lots")
        try:
            driver.find_element(By.CSS_SELECTOR, ".o_searchview_input").send_keys("Verified")
            time.sleep(1)
            shot(driver, next_n(), "lots_search_verified")
            driver.find_element(By.CSS_SELECTOR, ".o_searchview_input").send_keys(
                webdriver.common.keys.Keys.ESCAPE)
        except Exception as exc:
            print(f"  (search skipped: {exc})")

        print("STEP 13: Open a verified lot")
        rows = driver.find_elements(By.CSS_SELECTOR, ".o_data_row")
        opened_verified = False
        for row in rows:
            if "Verified" in row.text:
                row.click()
                opened_verified = True
                break
        if not opened_verified and rows:
            rows[0].click()
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, next_n(), "verified_lot_detail")

        print("STEP 14: Print the verification certificate")
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            driver.find_element(By.CSS_SELECTOR, "button[aria-label='Actions menu']").click()
            time.sleep(0.8)
            print_item = driver.find_element(By.XPATH, "//*[contains(@class,'dropdown-item')][.//text()='Print' or text()='Print']")
            ActionChains(driver).move_to_element(print_item).perform()
            time.sleep(0.8)
            shot(driver, next_n(), "print_menu")
            cert_item = driver.find_element(By.XPATH, "//*[contains(text(),'Verification Certificate')]")
            cert_item.click()
            time.sleep(2.5)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(1.5)
                shot(driver, next_n(), "verification_certificate_report")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            else:
                for _ in range(20):
                    pdfs = list(DOWNLOAD_DIR.glob("*.pdf"))
                    if pdfs:
                        break
                    time.sleep(0.5)
                pdfs = list(DOWNLOAD_DIR.glob("*.pdf"))
                if pdfs:
                    print(f"  Certificate downloaded: {pdfs[0].name}")
                else:
                    print("  (no PDF appeared in download dir)")
        except Exception as exc:
            print(f"  (certificate print skipped: {exc})")

        print("STEP 15: Back to Lots list, open a failed lot for contrast")
        driver.get(f"{BASE_URL}/odoo/inventory/lots")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        rows = driver.find_elements(By.CSS_SELECTOR, ".o_data_row")
        opened_failed = False
        for row in rows:
            if "Failed" in row.text:
                row.click()
                opened_failed = True
                break
        if opened_failed:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, next_n(), "failed_lot_detail")

        print("\nCapture complete.")
    finally:
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    headless = "--headless" in sys.argv or True  # this environment has no X display
    run(headless)
