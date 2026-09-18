"""
Selenium-driven, fully automated capture of the NAFDAC/SON verification
workflow through Odoo's real web UI: login, Purchase Orders list, an
inventory receipt, the Lots/Serial Numbers list showing a real mix of
Verified/Failed results across a bulk data set, a verified lot's detail,
the printed verification certificate, and a failed lot's detail.

Screenshots are captured at every step via Selenium itself
(driver.save_screenshot). For a continuous, real-time screen-recorded
video (not just a slideshow of these screenshots), run this under a real
X display - e.g. `xvfb-run -a --server-args="-screen 0 1440x900x24"
python3 selenium_capture.py` on Linux, while a separate `ffmpeg -f x11grab
...` process records that display - with `headless` left False and a full
desktop Chrome/Chromium installed (NOT a headless-only build such as
chrome-headless-shell, which has no window to record at all).
See build_video_from_screenshots.py for turning the screenshots alone into
a video when a live screen recording isn't available.
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
OUTDIR = Path("./selenium_screenshots")
OUTDIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR = Path("./selenium_downloads")

# Point this at a real Chrome/Chromium binary if it's not on PATH or not the
# default `google-chrome`/`chromium` Selenium Manager finds automatically.
# Leave as None on a normal desktop/CI machine with Chrome installed -
# Selenium 4.6+ resolves the browser and a matching chromedriver for you.
CHROMIUM_BIN = None


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
    # Selenium Manager (built into selenium>=4.6) resolves a matching
    # chromedriver automatically - no Service(executable_path=...) needed
    # on a normal machine with Chrome/Chromium installed.
    driver = webdriver.Chrome(options=opts)
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
    try:
        print("STEP 1: Log in")
        driver.get(f"{BASE_URL}/odoo/login")
        wait.until(EC.visibility_of_element_located((By.NAME, "login"))).send_keys("admin")
        driver.find_element(By.NAME, "password").send_keys("admin")
        shot(driver, 1, "login_form")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        wait.until(lambda d: "/odoo/login" not in d.current_url)
        time.sleep(2)
        shot(driver, 2, "home_after_login")

        print("STEP 2: Purchase Orders list (bulk data - multiple POs)")
        driver.get(f"{BASE_URL}/odoo/purchase")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, 3, "purchase_orders_list")

        print("STEP 3: Open first Purchase Order (confirmed, with receipt)")
        driver.find_elements(By.CSS_SELECTOR, ".o_data_row")[0].click()
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, 4, "purchase_order_detail")

        print("STEP 4: Open the receipt from this PO")
        try:
            driver.find_element(By.XPATH, "//button[contains(., 'Receipt')]").click()
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
            time.sleep(1.5)
            shot(driver, 5, "inventory_receipt_detail")
        except Exception as exc:
            print(f"  (could not open receipt smart button: {exc})")

        print("STEP 5: Lots/Serial Numbers list - the bulk verification results")
        driver.get(f"{BASE_URL}/odoo/inventory/lots")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o_content")))
        time.sleep(1.5)
        shot(driver, 6, "lots_list_bulk_results")

        print("STEP 6: Filter to Verified lots")
        try:
            driver.find_element(By.CSS_SELECTOR, ".o_searchview_input").send_keys("Verified")
            time.sleep(1)
            shot(driver, 7, "lots_search_verified")
            driver.find_element(By.CSS_SELECTOR, ".o_searchview_input").send_keys(
                webdriver.common.keys.Keys.ESCAPE)
        except Exception as exc:
            print(f"  (search skipped: {exc})")

        print("STEP 7: Open a verified lot")
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
        shot(driver, 8, "verified_lot_detail")

        print("STEP 8: Print the verification certificate")
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            driver.find_element(By.CSS_SELECTOR, "button[aria-label='Actions menu']").click()
            time.sleep(0.8)
            print_item = driver.find_element(By.XPATH, "//*[contains(@class,'dropdown-item')][.//text()='Print' or text()='Print']")
            ActionChains(driver).move_to_element(print_item).perform()
            time.sleep(0.8)
            shot(driver, 9, "print_menu")
            cert_item = driver.find_element(By.XPATH, "//*[contains(text(),'Verification Certificate')]")
            cert_item.click()
            time.sleep(2.5)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(1.5)
                shot(driver, 10, "verification_certificate_report")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            else:
                # Odoo 19 triggers a PDF download rather than an in-page
                # render; wait for the file to land, then note its path
                # (converted to PNG afterwards for the screenshot set).
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

        print("STEP 9: Back to Lots list, open a failed lot for contrast")
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
            shot(driver, 11, "failed_lot_detail")

        print("\nCapture complete.")
    finally:
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    run(headless)
