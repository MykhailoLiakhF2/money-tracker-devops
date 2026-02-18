from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, desc
from typing import List, Optional
from datetime import datetime
import logging
import os

import database
import schemas
import redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Money Tracker API")

# Cache key constants
CACHE_CATEGORIES_ALL = "categories:all"
CACHE_CATEGORIES_TREE = "categories:tree"
CACHE_ACCOUNTS_ALL = "accounts:all"
CACHE_TTL = 900  # 15 minutes
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))  # requests per minute


# On startup, automatically create tables if they don't exist
@app.on_event("startup")
def on_startup():
    database.init_db()
    # Log Redis connectivity
    if redis_client.is_healthy():
        logger.info("✅ Redis connected")
    else:
        logger.warning("⚠️ Redis unavailable — running without cache")


# ---------------------------------------------------------------------------
# Rate Limiting Middleware
# ---------------------------------------------------------------------------
# Runs BEFORE every request. Checks Redis counter for client IP.
# Returns 429 if limit exceeded. Adds rate limit headers to response.
#
# INTERVIEW NOTE:
#   Middleware pattern: intercepts all requests without modifying endpoints.
#   In large-scale systems, rate limiting is at API Gateway level (Kong/Envoy),
#   not in application code. But understanding the pattern is key.
# ---------------------------------------------------------------------------

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks (Kubernetes probes)
    if request.url.path in ("/health", "/ready"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    result = redis_client.check_rate_limit(client_ip, max_requests=RATE_LIMIT_MAX, window_seconds=60)

    if not result["allowed"]:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Try again later."},
            headers={
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": "0",
                "Retry-After": "60",
            },
        )

    response = await call_next(request)

    # Add rate limit headers to every response (standard practice)
    response.headers["X-RateLimit-Limit"] = str(result["limit"])
    response.headers["X-RateLimit-Remaining"] = str(result["remaining"])

    return response


# Get database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper: determine category type (considering parent) ---
def get_category_type(category: database.Category) -> str:
    """Returns category type. If None — inherits from parent."""
    if category.type:
        return category.type
    if category.parent:
        return category.parent.type or "expense"
    return "expense"

# --- Helper: invalidate categories cache ---
def invalidate_categories_cache():
    """Delete all category caches. Called after any category mutation."""
    redis_client.cache_delete(CACHE_CATEGORIES_ALL)
    redis_client.cache_delete(CACHE_CATEGORIES_TREE)


# --- Helper: invalidate accounts cache ---
def invalidate_accounts_cache():
    """Delete accounts cache. Called after any account mutation."""
    redis_client.cache_delete(CACHE_ACCOUNTS_ALL)


# --- HEALTH CHECKS (Kubernetes probes) ---
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.1.0"}

@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe checks ALL dependencies.
    If PostgreSQL is down → pod is not ready → no traffic routed.
    Redis status is reported but doesn't affect readiness
    (graceful degradation — app works without cache).
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    redis_ok = redis_client.is_healthy()
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected" if redis_ok else "unavailable (degraded mode)",
    }

# ========================================
# ACCOUNT MANAGEMENT
# ========================================

@app.post("/accounts/", response_model=schemas.Account)
def create_account(account: schemas.AccountCreate, db: Session = Depends(get_db)):
    if account.account_type not in ("cash", "debit", "credit"):
        raise HTTPException(status_code=400, detail="Account type must be: cash, debit, or credit")
    if account.account_type == "credit" and account.credit_limit <= 0:
        raise HTTPException(status_code=400, detail="Credit limit must be greater than 0")

    db_account = database.Account(
        name=account.name,
        balance=account.balance,
        account_type=account.account_type,
        credit_limit=account.credit_limit,
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    invalidate_accounts_cache()

    return db_account

@app.get("/accounts/", response_model=List[schemas.Account])
def read_accounts(db: Session = Depends(get_db)):
    """Cache-aside pattern: same as categories — check Redis first."""
    cached = redis_client.cache_get(CACHE_ACCOUNTS_ALL)
    if cached is not None:
        logger.debug("Cache HIT: accounts:all")
        return cached

    logger.debug("Cache MISS: accounts:all")
    accounts = db.query(database.Account).all()

    accounts_data = [schemas.Account.model_validate(a).model_dump() for a in accounts]
    redis_client.cache_set(CACHE_ACCOUNTS_ALL, accounts_data, CACHE_TTL)

    return accounts

@app.put("/accounts/{account_id}", response_model=schemas.Account)
def update_account(account_id: int, account_update: schemas.AccountCreate, db: Session = Depends(get_db)):
    db_account = db.query(database.Account).filter(database.Account.id == account_id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account_update.account_type not in ("cash", "debit", "credit"):
        raise HTTPException(status_code=400, detail="Account type must be: cash, debit, or credit")

    db_account.name = account_update.name
    db_account.balance = account_update.balance
    db_account.account_type = account_update.account_type
    db_account.credit_limit = account_update.credit_limit

    db.commit()
    db.refresh(db_account)

    invalidate_accounts_cache()

    return db_account

# ========================================
# CATEGORY MANAGEMENT (with Redis cache)
# ========================================

@app.post("/categories/", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    if category.parent_id:
        parent = db.query(database.Category).filter(database.Category.id == category.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")
        if parent.parent_id:
            raise HTTPException(status_code=400, detail="Subcategories can only be 1 level deep")
        cat_type = None
    else:
        cat_type = category.type

    db_category = database.Category(
        name=category.name,
        type=cat_type,
        parent_id=category.parent_id,
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)

    # Invalidate cache — next GET will read fresh data from DB
    invalidate_categories_cache()

    return db_category

@app.get("/categories/", response_model=List[schemas.Category])
def read_categories(db: Session = Depends(get_db)):
    """
    Cache-aside pattern:
    1. Check Redis → if HIT, return cached data (skip DB entirely)
    2. If MISS → query PostgreSQL → store in Redis with TTL → return
    """
    # Try cache first
    cached = redis_client.cache_get(CACHE_CATEGORIES_ALL)
    if cached is not None:
        logger.debug("Cache HIT: categories:all")
        return cached

    # Cache miss — query DB
    logger.debug("Cache MISS: categories:all")
    categories = db.query(database.Category).all()

    # Serialize and cache
    categories_data = [schemas.Category.model_validate(c).model_dump() for c in categories]
    redis_client.cache_set(CACHE_CATEGORIES_ALL, categories_data, CACHE_TTL)

    return categories

@app.get("/categories/tree", response_model=List[schemas.CategoryWithChildren])
def read_categories_tree(db: Session = Depends(get_db)):
    """Cache-aside for category tree (frequently read, rarely changed)."""
    cached = redis_client.cache_get(CACHE_CATEGORIES_TREE)
    if cached is not None:
        return cached

    categories = db.query(database.Category).filter(
        database.Category.parent_id == None
    ).options(joinedload(database.Category.children)).all()

    tree_data = [schemas.CategoryWithChildren.model_validate(c).model_dump() for c in categories]
    redis_client.cache_set(CACHE_CATEGORIES_TREE, tree_data, CACHE_TTL)

    return categories

@app.put("/categories/{category_id}", response_model=schemas.Category)
def update_category(category_id: int, category_update: schemas.CategoryCreate, db: Session = Depends(get_db)):
    db_category = db.query(database.Category).filter(database.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    db_category.name = category_update.name
    if not db_category.parent_id:
        db_category.type = category_update.type

    db.commit()
    db.refresh(db_category)

    invalidate_categories_cache()

    return db_category

# ========================================
# TRANSACTIONS (Expenses and Income)
# ========================================

@app.post("/transactions/", response_model=schemas.Transaction)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    account = db.query(database.Account).filter(database.Account.id == transaction.account_id).first()
    category = db.query(database.Category).filter(database.Category.id == transaction.category_id).first()

    if not account or not category:
        raise HTTPException(status_code=404, detail="Account or Category not found")

    cat_type = get_category_type(category)

    if cat_type == "expense":
        new_balance = account.balance - transaction.amount
        if account.account_type == "credit":
            if abs(new_balance) > account.credit_limit:
                raise HTTPException(status_code=400, detail="Credit limit exceeded")
        elif new_balance < 0:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        account.balance = new_balance
    elif cat_type == "income":
        account.balance += transaction.amount

    db_transaction = database.Transaction(
        amount=transaction.amount,
        description=transaction.description,
        account_id=transaction.account_id,
        category_id=transaction.category_id,
        created_at=transaction.created_at or datetime.utcnow(),
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.get("/transactions/", response_model=List[schemas.TransactionResponse])
def read_transactions(
    account_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Returns transactions with filters, sorted by date (newest first)."""
    query = db.query(database.Transaction).options(
        joinedload(database.Transaction.account),
        joinedload(database.Transaction.category).joinedload(database.Category.parent),
    )

    if account_id:
        query = query.filter(database.Transaction.account_id == account_id)
    if category_id:
        cat = db.query(database.Category).filter(database.Category.id == category_id).first()
        if cat and not cat.parent_id:
            child_ids = [c.id for c in db.query(database.Category).filter(
                database.Category.parent_id == category_id
            ).all()]
            all_ids = [category_id] + child_ids
            query = query.filter(database.Transaction.category_id.in_(all_ids))
        else:
            query = query.filter(database.Transaction.category_id == category_id)
    if date_from:
        query = query.filter(database.Transaction.created_at >= date_from)
    if date_to:
        query = query.filter(database.Transaction.created_at <= date_to)

    total = query.count()
    transactions = query.order_by(desc(database.Transaction.created_at)).offset(offset).limit(limit).all()

    result = []
    for t in transactions:
        if t.is_transfer:
            cat_type = "transfer"
            cat_name = "Transfer"
        elif t.category:
            cat_type = get_category_type(t.category)
            cat_name = t.category.name
        else:
            cat_type = "expense"
            cat_name = ""

        result.append(schemas.TransactionResponse(
            id=t.id,
            amount=t.amount,
            description=t.description,
            account_id=t.account_id,
            category_id=t.category_id,
            created_at=t.created_at,
            account_name=t.account.name if t.account else "",
            category_name=cat_name,
            category_type=cat_type,
            is_transfer=t.is_transfer,
            transfer_pair_id=t.transfer_pair_id,
        ))

    return result

@app.put("/transactions/{transaction_id}", response_model=schemas.Transaction)
def update_transaction(
    transaction_id: int,
    update: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
):
    """Edit transaction with balance recalculation."""
    txn = db.query(database.Transaction).filter(database.Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    old_account = db.query(database.Account).filter(database.Account.id == txn.account_id).first()
    old_category = db.query(database.Category).filter(database.Category.id == txn.category_id).first()
    old_type = get_category_type(old_category) if old_category else "expense"

    if old_type == "expense":
        old_account.balance += txn.amount
    elif old_type == "income":
        old_account.balance -= txn.amount

    if update.amount is not None:
        txn.amount = update.amount
    if update.description is not None:
        txn.description = update.description
    if update.created_at is not None:
        txn.created_at = update.created_at
    if update.account_id is not None:
        txn.account_id = update.account_id
    if update.category_id is not None:
        txn.category_id = update.category_id

    new_account = db.query(database.Account).filter(database.Account.id == txn.account_id).first()
    new_category = db.query(database.Category).filter(database.Category.id == txn.category_id).first()
    if not new_account or not new_category:
        db.rollback()
        raise HTTPException(status_code=404, detail="Account or Category not found")

    new_type = get_category_type(new_category)

    if new_type == "expense":
        new_balance = new_account.balance - txn.amount
        if new_account.account_type == "credit":
            if abs(new_balance) > new_account.credit_limit:
                db.rollback()
                raise HTTPException(status_code=400, detail="Credit limit exceeded")
        elif new_balance < 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="Insufficient funds")
        new_account.balance = new_balance
    elif new_type == "income":
        new_account.balance += txn.amount

    db.commit()
    db.refresh(txn)
    return txn

@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Delete transaction with balance rollback. For transfers — deletes both transactions."""
    txn = db.query(database.Transaction).filter(database.Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if txn.is_transfer:
        pair = db.query(database.Transaction).filter(
            database.Transaction.id == txn.transfer_pair_id
        ).first()

        if "→" in (txn.description or ""):
            from_acc = db.query(database.Account).filter(database.Account.id == txn.account_id).first()
            to_acc = db.query(database.Account).filter(database.Account.id == pair.account_id).first() if pair else None
        else:
            to_acc = db.query(database.Account).filter(database.Account.id == txn.account_id).first()
            from_acc = db.query(database.Account).filter(database.Account.id == pair.account_id).first() if pair else None

        if from_acc:
            from_acc.balance += txn.amount
        if to_acc:
            to_acc.balance -= txn.amount

        db.delete(txn)
        if pair:
            db.delete(pair)
    else:
        account = db.query(database.Account).filter(database.Account.id == txn.account_id).first()
        category = db.query(database.Category).filter(database.Category.id == txn.category_id).first()
        cat_type = get_category_type(category) if category else "expense"

        if cat_type == "expense":
            account.balance += txn.amount
        elif cat_type == "income":
            account.balance -= txn.amount

        db.delete(txn)

    db.commit()
    return {"status": "deleted", "id": transaction_id}

# ========================================
# TRANSFERS
# ========================================

@app.post("/transfers/")
def make_transfer(transfer: schemas.TransferCreate, db: Session = Depends(get_db)):
    from_acc = db.query(database.Account).filter(database.Account.id == transfer.from_account_id).first()
    to_acc = db.query(database.Account).filter(database.Account.id == transfer.to_account_id).first()

    if not from_acc or not to_acc:
        raise HTTPException(status_code=404, detail="One of the accounts not found")

    new_balance = from_acc.balance - transfer.amount
    if from_acc.account_type == "credit":
        if abs(new_balance) > from_acc.credit_limit:
            raise HTTPException(status_code=400, detail="Credit limit exceeded")
    elif new_balance < 0:
        raise HTTPException(status_code=400, detail="Insufficient funds in sender account")

    try:
        from_acc.balance = new_balance
        to_acc.balance += transfer.amount

        now = datetime.utcnow()

        txn_out = database.Transaction(
            amount=transfer.amount,
            description=f"Transfer → {to_acc.name}",
            account_id=from_acc.id,
            category_id=None,
            is_transfer=True,
            created_at=now,
        )
        db.add(txn_out)
        db.flush()

        txn_in = database.Transaction(
            amount=transfer.amount,
            description=f"Transfer ← {from_acc.name}",
            account_id=to_acc.id,
            category_id=None,
            is_transfer=True,
            transfer_pair_id=txn_out.id,
            created_at=now,
        )
        db.add(txn_in)
        db.flush()

        txn_out.transfer_pair_id = txn_in.id

        db.commit()
        return {"status": "success", "from_balance": from_acc.balance, "to_balance": to_acc.balance}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error executing transfer")
