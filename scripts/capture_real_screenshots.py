"""
capture_real_screenshots.py
Drives headless Microsoft Edge via Selenium to interact with the running ForensicLedger
application and capture genuine, high-resolution screenshots of every screen and state.
"""

import time
import subprocess
import urllib.request
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ROOT = Path("c:/Users/justf/Downloads/ForensicLedger_AutoDemo/ForensicLedger")
SCREENSHOTS_DIR = ROOT / "documentation" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def wait_for_server(url="http://127.0.0.1:5000/api/health", timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def capture_all_screens():
    server_proc = None
    if not wait_for_server(timeout=1):
        python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
        print("Starting background Flask server...")
        server_proc = subprocess.Popen(
            [str(python_exe), "backend/app.py"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        assert wait_for_server(timeout=10), "Flask failed to start"
        print("Flask server running at http://127.0.0.1:5000")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1600,1050")

    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        # Screen 1: Login Page
        print("[1/16] Capturing Login Page...")
        driver.get("http://127.0.0.1:5000/")
        wait.until(EC.presence_of_element_located((By.ID, "login-user")))
        time.sleep(1)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_01_login_page.png"))

        # Screen 2: Invalid Login Error Toast
        print("[2/16] Capturing Invalid Login Toast...")
        u_in = driver.find_element(By.ID, "login-user")
        p_in = driver.find_element(By.ID, "login-pass")
        u_in.clear(); u_in.send_keys("unauthorized_user")
        p_in.clear(); p_in.send_keys("wrong_password")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(1)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_02_login_invalid.png"))

        # Screen 3: Investigator Login & Main Dashboard
        print("[3/16] Capturing Investigator Dashboard...")
        u_in.clear(); u_in.send_keys("investigator_a")
        p_in.clear(); p_in.send_keys("password123")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.ID, "stat-total")))
        time.sleep(1.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_03_dashboard_investigator.png"))

        # Screen 4: Evidence Vault
        print("[4/16] Capturing Evidence Vault...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="evidence"]').click()
        time.sleep(1.5)
        wait.until(EC.presence_of_element_located((By.ID, "ev-table-wrap")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_04_evidence_vault.png"))

        # Screen 5: Evidence Upload Page
        print("[5/16] Capturing Evidence Upload Page...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="upload"]').click()
        time.sleep(1.5)
        wait.until(EC.presence_of_element_located((By.ID, "upload-actor")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_05_evidence_upload.png"))

        # Screen 6: Upload an Evidence Item & Capture Result
        print("[6/16] Uploading Live Evidence Item & Capturing Anchoring Result...")
        # Create small test file to upload
        test_file = ROOT / "documentation" / "test_sample_evidence.txt"
        test_file.write_text("ForensicLedger verified evidence payload for documentation demonstration.", encoding="utf-8")
        file_input = driver.find_element(By.ID, "file-input")
        file_input.send_keys(str(test_file))
        time.sleep(1.5)
        driver.find_element(By.ID, "upload-btn").click()
        time.sleep(2.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_06_upload_result.png"))

        # Screen 7: Evidence Detail View
        print("[7/16] Capturing Evidence Detail View...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="evidence"]').click()
        time.sleep(1.5)
        rows = driver.find_elements(By.CSS_SELECTOR, "#ev-tbody tr")
        if rows:
            view_btn = rows[0].find_element(By.TAG_NAME, "button")
            view_btn.click()
            time.sleep(2)
            wait.until(EC.presence_of_element_located((By.ID, "sha256-val")))
            driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_07_evidence_detail.png"))

            # Screen 8: Merkle Proof & Tree Path
            print("[8/16] Capturing Merkle Proof Section...")
            # Scroll to Merkle proof section
            driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)
            driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_08_merkle_proof.png"))

            # Screen 9: Live Integrity Verification Button Click
            print("[9/16] Capturing Live Cryptographic Verification Result...")
            verify_btn = driver.find_element(By.ID, "verify-btn")
            verify_btn.click()
            time.sleep(1.5)
            wait.until(EC.presence_of_element_located((By.ID, "verify-result")))
            driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_09_verify_success.png"))

            # Screen 10: Custody Transfer & History Timeline
            print("[10/16] Capturing Custody Transfer & History Timeline...")
            driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(1)
            driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_10_custody_transfer.png"))

        # Screen 11: Blockchain Explorer
        print("[11/16] Capturing Blockchain Ledger Explorer...")
        driver.execute_script("window.scrollTo(0, 0);")
        driver.find_element(By.CSS_SELECTOR, '[data-page="blockchain"]').click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.ID, "chain-valid-banner")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_11_blockchain_explorer.png"))

        # Screen 12: Audit Log Viewer
        print("[12/16] Capturing Audit Log Viewer...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="auditlog"]').click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.ID, "audit-count")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_12_audit_log.png"))

        # Screen 13: Reports & Downloads
        print("[13/16] Capturing Reports & Downloads Page...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="reports"]').click()
        time.sleep(2)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_13_reports_downloads.png"))

        # Screen 14: Experimental Benchmark Dashboard
        print("[14/16] Capturing Experimental Dashboard & Live Benchmark...")
        driver.find_element(By.CSS_SELECTOR, '[data-page="experiments"]').click()
        time.sleep(1.5)
        bench_btn = driver.find_element(By.ID, "bench-btn")
        bench_btn.click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#bench-results table")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_14_experiments_benchmark.png"))

        # Screen 15: Analyst Role Interface
        print("[15/16] Capturing Analyst Role Dashboard...")
        driver.execute_script("doLogout();")
        time.sleep(1)
        wait.until(EC.visibility_of_element_located((By.ID, "login-view")))
        driver.find_element(By.ID, "login-user").send_keys("analyst_a")
        driver.find_element(By.ID, "login-pass").send_keys("password123")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.ID, "topbar-user")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_15_dashboard_analyst.png"))

        # Screen 16: Supervisor Role Interface
        print("[16/16] Capturing Supervisor Role Dashboard...")
        driver.execute_script("doLogout();")
        time.sleep(1)
        wait.until(EC.visibility_of_element_located((By.ID, "login-view")))
        driver.find_element(By.ID, "login-user").send_keys("supervisor_a")
        driver.find_element(By.ID, "login-pass").send_keys("password123")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.ID, "topbar-user")))
        driver.save_screenshot(str(SCREENSHOTS_DIR / "screen_16_dashboard_supervisor.png"))

        print("\nAll 16 genuine application screenshots captured successfully!")

    finally:
        driver.quit()
        if server_proc:
            server_proc.terminate()
            print("Terminated Flask background process.")

if __name__ == "__main__":
    capture_all_screens()
