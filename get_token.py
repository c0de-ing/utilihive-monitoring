#!/usr/bin/env python3
"""
Token Extractor - Automatically get authentication token from browser
Run: python get_token.py
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import os

# Configuration
LOGIN_URL = "https://console.ch.utilihive.io/login"
TOKEN_FILE = "token.json"
WAIT_TIMEOUT = 300  # 5 minutes for user to log in


def setup_browser():
    """Set up Chrome browser with options"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Uncomment to run in background
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # Try to use existing Chrome profile (optional)
    # This can help if you're already logged in
    # chrome_options.add_argument(r"user-data-dir=C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data")

    # Auto-download and use correct ChromeDriver version
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def debug_show_storage(driver):
    """Debug: Show all localStorage and sessionStorage keys"""
    try:
        storage_info = driver.execute_script("""
            const info = {
                localStorage: [],
                sessionStorage: []
            };

            // Get all localStorage keys
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const value = localStorage.getItem(key);
                info.localStorage.push({
                    key: key,
                    valuePreview: value.substring(0, 50) + (value.length > 50 ? '...' : '')
                });
            }

            // Get all sessionStorage keys
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const value = sessionStorage.getItem(key);
                info.sessionStorage.push({
                    key: key,
                    valuePreview: value.substring(0, 50) + (value.length > 50 ? '...' : '')
                });
            }

            return info;
        """)

        print("\n[DEBUG] localStorage keys:")
        for item in storage_info.get('localStorage', []):
            print(f"  - {item['key']}: {item['valuePreview']}")

        print("\n[DEBUG] sessionStorage keys:")
        for item in storage_info.get('sessionStorage', []):
            print(f"  - {item['key']}: {item['valuePreview']}")

    except Exception as e:
        print(f"Could not get storage info: {e}")


def extract_token_from_browser(driver):
    """Extract JWT token from browser storage - UtiliHive specific"""
    print("\n[Checking localStorage for UtiliHive token...]")

    # Method 1: Try UtiliHive specific key (JWT_MIDDLEWARE:authToken)
    try:
        token_data = driver.execute_script("""
            // Check for UtiliHive specific key
            const authData = localStorage.getItem('JWT_MIDDLEWARE:authToken');
            if (authData) {
                try {
                    const parsed = JSON.parse(authData);
                    if (parsed.token) {
                        return {
                            token: parsed.token,
                            refreshToken: parsed.refreshToken || null,
                            expires: parsed.expires || null
                        };
                    }
                } catch (e) {
                    console.error('Error parsing auth data:', e);
                }
            }
            return null;
        """)

        if token_data and token_data.get('token'):
            print(f"OK Token found in localStorage (JWT_MIDDLEWARE:authToken)!")
            if token_data.get('expires'):
                print(f"   Expires: {token_data['expires']}")
            return token_data['token']
    except Exception as e:
        print(f"Could not access localStorage: {e}")

    # Method 2: Fallback - Try common localStorage keys
    print("\n[Checking other localStorage keys...]")
    try:
        token = driver.execute_script("""
            // Try common keys
            const keys = ['token', 'jwt', 'auth_token', 'authToken', 'access_token', 'accessToken'];
            for (let key of keys) {
                const value = localStorage.getItem(key);
                if (value) {
                    // Check if it's a direct token
                    if (value.startsWith('eyJ')) {
                        return value;
                    }
                    // Check if it's a JSON with token
                    try {
                        const parsed = JSON.parse(value);
                        if (parsed.token && parsed.token.startsWith('eyJ')) {
                            return parsed.token;
                        }
                    } catch (e) {}
                }
            }

            // Try to find any JWT-like token in localStorage
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const value = localStorage.getItem(key);
                if (value && typeof value === 'string') {
                    // Direct JWT
                    if (value.startsWith('eyJ')) {
                        return value;
                    }
                    // JSON with token
                    try {
                        const parsed = JSON.parse(value);
                        if (parsed.token && parsed.token.startsWith('eyJ')) {
                            return parsed.token;
                        }
                    } catch (e) {}
                }
            }

            return null;
        """)

        if token:
            print(f"OK Token found in localStorage!")
            return token
    except Exception as e:
        print(f"Could not access localStorage: {e}")

    # Method 3: Try sessionStorage
    print("\n[Checking sessionStorage...]")
    try:
        token = driver.execute_script("""
            // Check JWT_MIDDLEWARE:authToken in sessionStorage
            const authData = sessionStorage.getItem('JWT_MIDDLEWARE:authToken');
            if (authData) {
                try {
                    const parsed = JSON.parse(authData);
                    if (parsed.token) {
                        return parsed.token;
                    }
                } catch (e) {}
            }

            // Try other keys
            const keys = ['token', 'jwt', 'auth_token', 'authToken'];
            for (let key of keys) {
                const value = sessionStorage.getItem(key);
                if (value) {
                    if (value.startsWith('eyJ')) {
                        return value;
                    }
                    try {
                        const parsed = JSON.parse(value);
                        if (parsed.token) {
                            return parsed.token;
                        }
                    } catch (e) {}
                }
            }

            return null;
        """)

        if token:
            print(f"OK Token found in sessionStorage!")
            return token
    except Exception as e:
        print(f"Could not access sessionStorage: {e}")

    # Method 4: Try cookies as last resort
    print("\n[Checking cookies...]")
    try:
        cookies = driver.get_cookies()
        for cookie in cookies:
            if 'token' in cookie['name'].lower() or 'jwt' in cookie['name'].lower():
                value = cookie['value']
                if value.startsWith('eyJ'):
                    print(f"OK Token found in cookie: {cookie['name']}")
                    return value
    except Exception as e:
        print(f"Could not access cookies: {e}")

    return None


def decode_token_info(token):
    """Decode JWT token to get expiration info"""
    try:
        import base64
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        decoded = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded)

        return payload_data
    except Exception as e:
        print(f"Could not decode token: {e}")
        return None


def save_token(token):
    """Save token to file"""
    token_data = {
        'token': token,
        'retrieved_at': datetime.now().isoformat(),
        'retrieved_by': 'get_token.py'
    }

    # Try to get token expiration
    payload = decode_token_info(token)
    if payload:
        if 'exp' in payload:
            exp_timestamp = payload['exp']
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            token_data['expires_at'] = exp_datetime.isoformat()
            print(f"\n[Token expires at: {exp_datetime}]")

        if 'sub' in payload:
            token_data['user'] = payload['sub']
            print(f"[Token user: {payload['sub']}]")

    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✓ Token saved to: {TOKEN_FILE}")


def main():
    print("=" * 70)
    print("UtiliHive Token Extractor")
    print("=" * 70)
    print("\nThis script will:")
    print("1. Open your browser to the UtiliHive login page")
    print("2. Wait for you to log in")
    print("3. Extract the authentication token")
    print("4. Save it for use in the data collection script")
    print("\n" + "=" * 70)

    driver = None

    try:
        # Set up browser
        print("\n[Opening browser...]")
        driver = setup_browser()

        # Navigate to login page
        print(f"[Navigating to: {LOGIN_URL}]")
        driver.get(LOGIN_URL)

        print("\n" + "=" * 70)
        print("PLEASE LOG IN TO UTILIHIVE IN THE BROWSER WINDOW")
        print("=" * 70)
        print("\nWaiting for you to log in...")
        print("(The script will automatically detect when you're logged in)")

        # Wait for successful login (check for URL change or specific element)
        start_time = time.time()
        token = None

        while time.time() - start_time < WAIT_TIMEOUT:
            current_url = driver.current_url

            # Check if we're no longer on the login page
            if 'login' not in current_url.lower():
                print(f"\n✓ Login detected! Current URL: {current_url}")

                # Wait a bit for the token to be stored
                time.sleep(2)

                # Try to extract token
                token = extract_token_from_browser(driver)

                if token:
                    break
                else:
                    print("\n[Token not found yet, waiting...]")

            time.sleep(2)  # Check every 2 seconds

        if not token:
            print("\n✗ Could not find token after login.")
            print("\nTrying one more time to extract token...")
            token = extract_token_from_browser(driver)

        if token:
            print("\n" + "=" * 70)
            print("TOKEN FOUND!")
            print("=" * 70)
            print(f"\nToken (first 50 chars): {token[:50]}...")

            # Save token
            save_token(token)

            print("\n" + "=" * 70)
            print("SUCCESS!")
            print("=" * 70)
            print(f"\nToken saved to: {TOKEN_FILE}")
            print("\nYou can now run the data collection script:")
            print("  python script.py")
            print("\nThe script will automatically use the saved token.")

        else:
            print("\n" + "=" * 70)
            print("TOKEN NOT FOUND")
            print("=" * 70)
            print("\nCould not automatically extract the token.")

            # Show debug info
            print("\nShowing all storage keys for debugging:")
            debug_show_storage(driver)

            print("\n" + "=" * 70)
            print("Manual extraction:")
            print("1. Open browser DevTools (F12)")
            print("2. Go to Application/Storage → Local Storage → console.ch.utilihive.io")
            print("3. Look for key: JWT_MIDDLEWARE:authToken")
            print("4. Copy the 'token' value from the JSON")
            print("5. Or paste the entire value into token.json")
            print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            print("\n[Closing browser in 5 seconds...]")
            time.sleep(5)
            driver.quit()


if __name__ == "__main__":
    main()
