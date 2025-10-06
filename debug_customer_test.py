"""Debug script to test customer creation"""
import sys
import os

# Set test environment
os.environ["FLASK_ENV"] = "testing"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_S3_BUCKET"] = "testing"

from app import create_app
from config import TestingConfig
from extensions import db
from models.user import User
from models.source import Source
from models.customer import Customer
from werkzeug.security import generate_password_hash

# Create app
app = create_app(config_class=TestingConfig)

with app.app_context():
    # Create tables
    db.create_all()

    # Create sources
    sources = [Source(SSource=s) for s in ["SRC1", "SRC2", "SRC3"]]
    db.session.add_all(sources)

    # Create admin user
    admin = User(
        username="admin",
        email="admin@example.com",
        role="admin",
        password_hash=generate_password_hash("password")
    )
    db.session.add(admin)
    db.session.commit()

    print("✓ Database setup complete")
    print(f"✓ Sources created: {[s.SSource for s in Source.query.all()]}")

    # Create test client
    client = app.test_client()

    # Login
    login_response = client.post("/login", data={"username": "admin", "password": "password"})
    print(f"✓ Login status: {login_response.status_code}")

    # Try to create customer WITHOUT redirect
    print("\n--- Testing customer creation WITHOUT follow_redirects ---")
    response = client.post(
        "/customers/new",
        data={"Name": "New Customer", "Source": "SRC1"},
        follow_redirects=False
    )
    print(f"Status code: {response.status_code}")
    print(f"Location header: {response.headers.get('Location')}")

    if response.status_code == 200:
        print("⚠ ERROR: Got 200 instead of redirect!")
        # Check for error messages
        if b"Error" in response.data or b"error" in response.data:
            print("Error found in response:")
            # Find error messages
            data_str = response.data.decode('utf-8')
            if 'alert' in data_str:
                import re
                alerts = re.findall(r'<div class="alert[^"]*"[^>]*>(.*?)</div>', data_str, re.DOTALL)
                for alert in alerts:
                    print(f"  - {alert.strip()}")

    # Check if customer was created
    new_customer = Customer.query.filter_by(Name="New Customer").first()
    if new_customer:
        print(f"✓ Customer created: ID={new_customer.CustID}, Name={new_customer.Name}")
    else:
        print("✗ Customer was NOT created in database")

    # Try WITH redirect
    print("\n--- Testing customer creation WITH follow_redirects ---")
    response2 = client.post(
        "/customers/new",
        data={"Name": "Another Customer", "Source": "SRC2"},
        follow_redirects=True
    )
    print(f"Status code: {response2.status_code}")

    # Check for flash message
    if b"Customer created successfully" in response2.data:
        print("✓ Flash message found in response")
    else:
        print("✗ Flash message NOT found in response")

    # Check page title
    if b"Add New Customer" in response2.data:
        print("⚠ Still on form page (not redirected)")
    elif b"Another Customer" in response2.data:
        print("✓ On detail page with customer name")

    print("\n--- Final database state ---")
    all_customers = Customer.query.all()
    print(f"Total customers: {len(all_customers)}")
    for c in all_customers:
        print(f"  - {c.CustID}: {c.Name} (Source: {c.Source})")