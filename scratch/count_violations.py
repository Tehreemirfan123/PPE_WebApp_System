import requests

try:
    login_data = {"email": "admin@ppe.com", "password": "admin123"}
    response = requests.post("http://127.0.0.1:8000/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get("http://127.0.0.1:8000/violations/", headers=headers)
    violations = response.json()
    print(f"Total Violations: {len(violations)}")
    
    # Check timestamps of the last few
    if violations:
        print("Last 5 violations:")
        for v in violations[-5:]:
            print(f"- ID: {v['id']}, Item: {v['missing_item']}, Time: {v['timestamp']}")

except Exception as e:
    print(f"Error: {e}")
