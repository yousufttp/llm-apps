from playwright.sync_api import sync_playwright

# Change this to your ServiceNow instance URL (home page is fine)
SERVICENOW_URL = "https://service-now.com"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        # Use a persistent context so you can stay logged in
        context = browser.new_context()

        page = context.new_page()
        page.goto(SERVICENOW_URL)

        print("\nOpened ServiceNow. Please login manually in the browser window if needed.")
        input("After you're fully logged in and on the homepage, press Enter here to continue...")

        # Stop here for now (we'll navigate to 'Create New Incident' next)
        print("✅ Login confirmed. Next step: navigate to the incident creation form.")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()
