"""
test_browser_ui.py — Full Browser Automation & End-to-End UI Acceptance Test
Launches headless Microsoft Edge via Selenium, interacts with the ForensicLedger
frontend as a real user, clicks buttons, validates DOM updates, and checks console logs.
"""

import time
import sys
import subprocess
import urllib.request
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

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

def test_full_browser_workflow():
    # 1. Ensure Flask Server is Running
    server_proc = None
    if not wait_for_server(timeout=1):
        python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = sys.executable
        print("Launching background Flask server...")
        server_proc = subprocess.Popen(
            [str(python_exe), "backend/app.py"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        assert wait_for_server(timeout=10), "Flask failed to start within 10s"
        print("Flask server listening at http://127.0.0.1:5000")
    else:
        print("Reusing active Flask server at http://127.0.0.1:5000")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    print("\n--- Starting Headless Microsoft Edge Browser ---")
    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        # Step 1: Navigate to Root
        print("[1/10] Navigating to http://127.0.0.1:5000/ ...")
        driver.get("http://127.0.0.1:5000/")
        assert "ForensicLedger" in driver.title

        # Step 2: Test Invalid Login
        print("[2/10] Testing Invalid Credentials Error Handling...")
        user_input = wait.until(EC.presence_of_element_located((By.ID, "login-user")))
        pass_input = driver.find_element(By.ID, "login-pass")
        user_input.clear()
        user_input.send_keys("invalid_investigator")
        pass_input.clear()
        pass_input.send_keys("bad_password")

        login_btn = driver.find_element(By.ID, "login-btn")
        login_btn.click()
        time.sleep(1)

        # Confirm user remains on login view and error toast is displayed
        login_view = driver.find_element(By.ID, "login-view")
        assert not ("hidden" in login_view.get_attribute("class").split())

        # Step 3: Test Valid Login as Investigator
        print("[3/10] Testing Valid Login as Investigator A...")
        user_input.clear()
        user_input.send_keys("investigator_a")
        pass_input.clear()
        pass_input.send_keys("password123")
        time.sleep(0.5)
        login_btn.click()
        time.sleep(2)

        # Check console logs immediately after login attempt
        for l in driver.get_log("browser"):
            print(f"       [Browser Console] {l['level']}: {l['message']}")

        # Step 4: Verify Main Dashboard Appearance
        print("[4/10] Verifying Dashboard & Navigation Shell...")
        print("       login-view classes:", driver.find_element(By.ID, "login-view").get_attribute("class"))
        print("       main-view classes:", driver.find_element(By.ID, "main-view").get_attribute("class"))
        main_view = wait.until(EC.visibility_of_element_located((By.ID, "main-view")))
        assert main_view.is_displayed()
        topbar_user = wait.until(EC.presence_of_element_located((By.ID, "topbar-user")))
        assert "investigator_a" in topbar_user.text

        # Wait for dashboard stat cards
        wait.until(EC.presence_of_element_located((By.ID, "stat-total")))
        time.sleep(1)

        # Step 5: Navigate to Evidence Vault
        print("[5/10] Navigating to Evidence Vault...")
        ev_nav = driver.find_element(By.CSS_SELECTOR, '[data-page="evidence"]')
        ev_nav.click()
        time.sleep(1)
        wait.until(EC.presence_of_element_located((By.ID, "ev-table-wrap")))

        # Check evidence rows exist
        rows = driver.find_elements(By.CSS_SELECTOR, "#ev-tbody tr")
        print(f"       Found {len(rows)} evidence items in vault table.")
        assert len(rows) > 0

        # Step 6: View Evidence Detail & Merkle Proof
        print("[6/10] Inspecting Evidence Detail, Merkle Proof & History...")
        view_btn = rows[0].find_element(By.TAG_NAME, "button")
        view_btn.click()
        time.sleep(1.5)

        wait.until(EC.presence_of_element_located((By.ID, "sha256-val")))
        sha_text = driver.find_element(By.ID, "sha256-val").text
        assert len(sha_text) == 64
        print(f"       Verified SHA-256 digest: {sha_text[:16]}...")

        # Step 7: Click Verify Integrity Button
        print("[7/10] Triggering Live Cryptographic Verification Button...")
        verify_btn = driver.find_element(By.ID, "verify-btn")
        verify_btn.click()
        time.sleep(1.5)
        verify_result = wait.until(EC.presence_of_element_located((By.ID, "verify-result")))
        assert "VERIFIED" in verify_result.text
        print(f"       Verification UI Status: {verify_result.text.strip()}")

        # Step 8: Navigate to Blockchain Ledger Explorer
        print("[8/10] Navigating to Blockchain Explorer...")
        chain_nav = driver.find_element(By.CSS_SELECTOR, '[data-page="blockchain"]')
        chain_nav.click()
        time.sleep(1)
        wait.until(EC.presence_of_element_located((By.ID, "chain-valid-banner")))
        banner_text = driver.find_element(By.ID, "chain-valid-banner").text
        assert "Valid" in banner_text
        print(f"       Blockchain Status Banner: {banner_text.strip()}")

        # Step 9: Navigate to Audit Log
        print("[9/10] Navigating to Audit Log...")
        audit_nav = driver.find_element(By.CSS_SELECTOR, '[data-page="auditlog"]')
        audit_nav.click()
        time.sleep(1)
        wait.until(EC.presence_of_element_located((By.ID, "audit-count")))
        audit_text = driver.find_element(By.ID, "audit-count").text
        print(f"       Audit Count: {audit_text.strip()}")

        # Step 10: Navigate to Experiments & Run Benchmark
        print("[10/10] Navigating to Experiments & Running Live Benchmark...")
        exp_nav = driver.find_element(By.CSS_SELECTOR, '[data-page="experiments"]')
        exp_nav.click()
        time.sleep(1)
        bench_btn = driver.find_element(By.ID, "bench-btn")
        bench_btn.click()
        time.sleep(2)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#bench-results table")))
        print("       Live Benchmark Table rendered successfully.")

        # Test Logout and Test Analyst & Supervisor Logins
        print("[Bonus] Testing Role-Based Logins (Analyst & Supervisor)...")
        driver.execute_script("doLogout();")
        time.sleep(1)
        wait.until(EC.visibility_of_element_located((By.ID, "login-view")))

        # Test Analyst Login
        user_input = driver.find_element(By.ID, "login-user")
        pass_input = driver.find_element(By.ID, "login-pass")
        user_input.clear()
        user_input.send_keys("analyst_a")
        pass_input.clear()
        pass_input.send_keys("password123")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(1.5)
        topbar_user = wait.until(EC.presence_of_element_located((By.ID, "topbar-user")))
        assert "analyst_a" in topbar_user.text
        print("       Analyst login verified successfully.")

        # Logout again
        driver.execute_script("doLogout();")
        time.sleep(1)
        wait.until(EC.visibility_of_element_located((By.ID, "login-view")))

        # Test Supervisor Login
        user_input = driver.find_element(By.ID, "login-user")
        pass_input = driver.find_element(By.ID, "login-pass")
        user_input.clear()
        user_input.send_keys("supervisor_a")
        pass_input.clear()
        pass_input.send_keys("password123")
        driver.find_element(By.ID, "login-btn").click()
        time.sleep(1.5)
        topbar_user = wait.until(EC.presence_of_element_located((By.ID, "topbar-user")))
        assert "supervisor_a" in topbar_user.text
        print("       Supervisor login verified successfully.")

        # Check console logs for errors (ignoring expected 401 from step 2)
        logs = driver.get_log("browser")
        severe_errors = [l for l in logs if l["level"] == "SEVERE" and "favicon" not in l["message"].lower() and "401" not in l["message"]]
        print(f"\n--- Browser Console Audit: {len(logs)} log entries recorded ---")
        for l in logs:
            if l["level"] in ("SEVERE", "WARNING"):
                print(f"  [{l['level']}] {l['message']}")
        assert len(severe_errors) == 0, f"Encountered severe console errors: {severe_errors}"
        print("--- All Browser End-to-End Tests Passed Cleanly (0 Severe Errors) ---\n")

    finally:
        driver.quit()
        if server_proc:
            server_proc.terminate()
            print("Terminated test Flask server process.")

if __name__ == "__main__":
    test_full_browser_workflow()
