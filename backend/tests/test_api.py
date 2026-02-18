import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import fakeredis

from database import Base
from main import app, get_db

# ===========================================================================
# Test Setup
# ===========================================================================
# SQLite in-memory for database (no PostgreSQL needed)
# fakeredis for Redis (no Redis server needed)
#
# INTERVIEW NOTE:
#   fakeredis implements the full Redis protocol in Python memory.
#   Tests are fast, isolated, and don't need Docker or external services.
#   In CI pipeline (Jenkins), tests run in a Python container — no Redis pod.
# ===========================================================================

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Mock Redis with fakeredis — all redis_client functions use this instead
fake_redis = fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def setup_database():
    """Reset DB and Redis before each test."""
    Base.metadata.create_all(bind=engine)
    fake_redis.flushall()
    with patch("redis_client.get_redis", return_value=fake_redis):
        yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    """TestClient with mocked Redis."""
    with patch("redis_client.get_redis", return_value=fake_redis):
        yield TestClient(app)


# --- HEALTH CHECK ---
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
    assert "redis" in response.json()


# ========================================
# ACCOUNTS
# ========================================

def test_create_account(client):
    response = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cash"
    assert data["balance"] == 1000.0
    assert data["account_type"] == "cash"
    assert "id" in data


def test_create_credit_account(client):
    response = client.post("/accounts/", json={
        "name": "Credit Card",
        "balance": 0.0,
        "account_type": "credit",
        "credit_limit": 20000.0,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["account_type"] == "credit"
    assert data["credit_limit"] == 20000.0


def test_create_credit_account_no_limit(client):
    response = client.post("/accounts/", json={
        "name": "BadCredit",
        "account_type": "credit",
        "credit_limit": 0,
    })
    assert response.status_code == 400


def test_get_accounts(client):
    client.post("/accounts/", json={"name": "Card", "balance": 500.0})
    response = client.get("/accounts/")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_account(client):
    acc = client.post("/accounts/", json={"name": "Cash", "balance": 100.0}).json()
    response = client.put(f"/accounts/{acc['id']}", json={
        "name": "Cash USD",
        "balance": 200.0,
        "account_type": "cash",
        "credit_limit": 0.0,
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Cash USD"
    assert response.json()["balance"] == 200.0


# ========================================
# CATEGORIES (with caching)
# ========================================

def test_create_category(client):
    response = client.post("/categories/", json={"name": "Food", "type": "expense"})
    assert response.status_code == 200
    assert response.json()["name"] == "Food"
    assert response.json()["type"] == "expense"


def test_create_subcategory(client):
    parent = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()
    child = client.post("/categories/", json={
        "name": "Restaurants",
        "parent_id": parent["id"],
    }).json()
    assert child["parent_id"] == parent["id"]


def test_subcategory_max_depth(client):
    """Subcategories are limited to 1 level — cannot create sub-sub-categories."""
    parent = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()
    child = client.post("/categories/", json={"name": "Restaurants", "parent_id": parent["id"]}).json()
    response = client.post("/categories/", json={"name": "Fast Food", "parent_id": child["id"]})
    assert response.status_code == 400


def test_categories_tree(client):
    parent = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()
    client.post("/categories/", json={"name": "Restaurants", "parent_id": parent["id"]})
    client.post("/categories/", json={"name": "Groceries", "parent_id": parent["id"]})

    response = client.get("/categories/tree")
    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    assert len(tree[0]["children"]) == 2


def test_categories_cache(client):
    """Verify cache-aside: second call should use Redis cache."""
    client.post("/categories/", json={"name": "Food", "type": "expense"})

    # First call — cache MISS → reads from DB → stores in Redis
    resp1 = client.get("/categories/")
    assert resp1.status_code == 200

    # Verify data is now in Redis cache
    assert fake_redis.exists("categories:all")

    # Second call — cache HIT → reads from Redis (no DB query)
    resp2 = client.get("/categories/")
    assert resp2.status_code == 200
    assert len(resp2.json()) == len(resp1.json())


def test_categories_cache_invalidation(client):
    """Creating a new category should invalidate the cache."""
    client.post("/categories/", json={"name": "Food", "type": "expense"})
    client.get("/categories/")  # Populate cache
    assert fake_redis.exists("categories:all")

    # Create new category — should invalidate
    client.post("/categories/", json={"name": "Transport", "type": "expense"})
    assert not fake_redis.exists("categories:all")

    # Next GET reads fresh data from DB
    resp = client.get("/categories/")
    assert len(resp.json()) == 2


# ========================================
# TRANSACTIONS — CRUD
# ========================================

def test_create_transaction_expense(client):
    account = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    category = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()

    response = client.post("/transactions/", json={
        "amount": 200.0,
        "description": "Lunch",
        "account_id": account["id"],
        "category_id": category["id"],
    })
    assert response.status_code == 200

    accounts = client.get("/accounts/").json()
    assert accounts[0]["balance"] == 800.0


def test_create_transaction_income(client):
    account = client.post("/accounts/", json={"name": "Card", "balance": 500.0}).json()
    category = client.post("/categories/", json={"name": "Salary", "type": "income"}).json()

    response = client.post("/transactions/", json={
        "amount": 3000.0,
        "description": "Salary",
        "account_id": account["id"],
        "category_id": category["id"],
    })
    assert response.status_code == 200

    accounts = client.get("/accounts/").json()
    assert accounts[0]["balance"] == 3500.0


def test_create_transaction_with_custom_date(client):
    account = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    category = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()

    response = client.post("/transactions/", json={
        "amount": 50.0,
        "description": "Yesterday's lunch",
        "account_id": account["id"],
        "category_id": category["id"],
        "created_at": "2025-02-09T12:00:00",
    })
    assert response.status_code == 200
    assert "2025-02-09" in response.json()["created_at"]


def test_create_transaction_subcategory(client):
    """Transaction with subcategory inherits type from parent."""
    account = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    parent = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()
    child = client.post("/categories/", json={"name": "Restaurants", "parent_id": parent["id"]}).json()

    client.post("/transactions/", json={
        "amount": 300.0,
        "account_id": account["id"],
        "category_id": child["id"],
    })

    accounts = client.get("/accounts/").json()
    assert accounts[0]["balance"] == 700.0


def test_get_transactions(client):
    account = client.post("/accounts/", json={"name": "Cash", "balance": 5000.0}).json()
    cat_exp = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()
    cat_inc = client.post("/categories/", json={"name": "Income", "type": "income"}).json()

    client.post("/transactions/", json={"amount": 100.0, "account_id": account["id"], "category_id": cat_exp["id"]})
    client.post("/transactions/", json={"amount": 200.0, "account_id": account["id"], "category_id": cat_inc["id"]})

    response = client.get("/transactions/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert "account_name" in data[0]
    assert "category_name" in data[0]
    assert "category_type" in data[0]


def test_get_transactions_filter_by_account(client):
    acc1 = client.post("/accounts/", json={"name": "Cash", "balance": 5000.0}).json()
    acc2 = client.post("/accounts/", json={"name": "Card", "balance": 5000.0}).json()
    cat = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()

    client.post("/transactions/", json={"amount": 100.0, "account_id": acc1["id"], "category_id": cat["id"]})
    client.post("/transactions/", json={"amount": 200.0, "account_id": acc2["id"], "category_id": cat["id"]})

    response = client.get(f"/transactions/?account_id={acc1['id']}")
    assert len(response.json()) == 1
    assert response.json()[0]["account_name"] == "Cash"


def test_update_transaction(client):
    account = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    category = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()

    txn = client.post("/transactions/", json={
        "amount": 200.0,
        "description": "Lunch",
        "account_id": account["id"],
        "category_id": category["id"],
    }).json()

    response = client.put(f"/transactions/{txn['id']}", json={"amount": 300.0})
    assert response.status_code == 200

    accounts = client.get("/accounts/").json()
    assert accounts[0]["balance"] == 700.0


def test_delete_transaction(client):
    account = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    category = client.post("/categories/", json={"name": "Food", "type": "expense"}).json()

    txn = client.post("/transactions/", json={
        "amount": 200.0,
        "account_id": account["id"],
        "category_id": category["id"],
    }).json()

    response = client.delete(f"/transactions/{txn['id']}")
    assert response.status_code == 200

    accounts = client.get("/accounts/").json()
    assert accounts[0]["balance"] == 1000.0


# ========================================
# CREDIT CARDS
# ========================================

def test_credit_card_expense(client):
    credit = client.post("/accounts/", json={
        "name": "Credit Card",
        "balance": 0.0,
        "account_type": "credit",
        "credit_limit": 20000.0,
    }).json()
    category = client.post("/categories/", json={"name": "Shopping", "type": "expense"}).json()

    client.post("/transactions/", json={
        "amount": 5000.0,
        "account_id": credit["id"],
        "category_id": category["id"],
    })

    accounts = client.get("/accounts/").json()
    acc = next(a for a in accounts if a["id"] == credit["id"])
    assert acc["balance"] == -5000.0


def test_credit_card_over_limit(client):
    credit = client.post("/accounts/", json={
        "name": "Credit Card",
        "balance": 0.0,
        "account_type": "credit",
        "credit_limit": 1000.0,
    }).json()
    category = client.post("/categories/", json={"name": "Shopping", "type": "expense"}).json()

    response = client.post("/transactions/", json={
        "amount": 1500.0,
        "account_id": credit["id"],
        "category_id": category["id"],
    })
    assert response.status_code == 400


def test_cash_account_no_negative(client):
    """Cash/debit accounts cannot go negative."""
    cash = client.post("/accounts/", json={"name": "Cash", "balance": 100.0}).json()
    category = client.post("/categories/", json={"name": "Shopping", "type": "expense"}).json()

    response = client.post("/transactions/", json={
        "amount": 500.0,
        "account_id": cash["id"],
        "category_id": category["id"],
    })
    assert response.status_code == 400


# ========================================
# TRANSFERS
# ========================================

def test_transfer(client):
    acc1 = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    acc2 = client.post("/accounts/", json={"name": "Card", "balance": 500.0}).json()

    response = client.post("/transfers/", json={
        "from_account_id": acc1["id"],
        "to_account_id": acc2["id"],
        "amount": 300.0,
    })
    assert response.status_code == 200
    assert response.json()["from_balance"] == 700.0
    assert response.json()["to_balance"] == 800.0


def test_transfer_insufficient_funds(client):
    acc1 = client.post("/accounts/", json={"name": "Cash", "balance": 100.0}).json()
    acc2 = client.post("/accounts/", json={"name": "Card", "balance": 0.0}).json()

    response = client.post("/transfers/", json={
        "from_account_id": acc1["id"],
        "to_account_id": acc2["id"],
        "amount": 500.0,
    })
    assert response.status_code == 400


def test_transfer_creates_transactions(client):
    """Transfer creates 2 transaction records."""
    acc1 = client.post("/accounts/", json={"name": "Cash", "balance": 1000.0}).json()
    acc2 = client.post("/accounts/", json={"name": "Card", "balance": 500.0}).json()

    client.post("/transfers/", json={
        "from_account_id": acc1["id"],
        "to_account_id": acc2["id"],
        "amount": 300.0,
    })

    txns = client.get("/transactions/").json()
    assert len(txns) == 2
    assert all(t["is_transfer"] for t in txns)
    descs = [t["description"] for t in txns]
    assert any("→" in d for d in descs)
    assert any("←" in d for d in descs)
    assert txns[0]["transfer_pair_id"] == txns[1]["id"]
    assert txns[1]["transfer_pair_id"] == txns[0]["id"]


def test_transfer_from_credit(client):
    """Transfer from credit card — works within limit."""
    credit = client.post("/accounts/", json={
        "name": "Credit Card",
        "balance": 0.0,
        "account_type": "credit",
        "credit_limit": 5000.0,
    }).json()
    cash = client.post("/accounts/", json={"name": "Cash", "balance": 0.0}).json()

    response = client.post("/transfers/", json={
        "from_account_id": credit["id"],
        "to_account_id": cash["id"],
        "amount": 3000.0,
    })
    assert response.status_code == 200
    assert response.json()["from_balance"] == -3000.0
    assert response.json()["to_balance"] == 3000.0


# ========================================
# RATE LIMITING
# ========================================

def test_rate_limiting(client):
    """Verify rate limiter returns 429 after exceeding limit."""
    # Create test data
    client.post("/accounts/", json={"name": "Test", "balance": 100.0})

    # Simulate exceeding rate limit by pre-setting counter
    fake_redis.set("ratelimit:testclient", 101)
    fake_redis.expire("ratelimit:testclient", 60)

    response = client.get("/accounts/")
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]


def test_rate_limit_headers(client):
    """Verify rate limit headers are present in responses."""
    response = client.post("/accounts/", json={"name": "Test", "balance": 100.0})
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
