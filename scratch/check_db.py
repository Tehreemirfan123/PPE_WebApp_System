import requests

try:
    # 1. Authenticate
    print("Authenticating...")
    login_data = {"email": "admin@ppe.com", "password": "admin123"}
    response = requests.post("http://127.0.0.1:8000/auth/login", json=login_data)
    response.raise_for_status()
    token = response.json()["access_token"]
    print("Authenticated successfully.")

    # 2. List Sites
    print("Listing sites...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://127.0.0.1:8000/sites/", headers=headers)
    response.raise_for_status()
    sites = response.json()
    print(f"Found {len(sites)} sites:")
    for site in sites:
        print(f"- {site['name']} (ID: {site['id']})")

except Exception as e:
    print(f"Error: {e}")
