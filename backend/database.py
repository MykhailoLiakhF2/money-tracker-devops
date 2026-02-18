import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# 1. Load environment variables from .env
load_dotenv()

# 2. Base class for models (does not require DB connection)
Base = declarative_base()

# 3. Lazy initialization of engine and session (not created on import)
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        USER = os.getenv("POSTGRES_USER")
        PASS = os.getenv("POSTGRES_PASSWORD")
        DB = os.getenv("POSTGRES_DB")
        HOST = os.getenv("IP_INT")
        PORT = os.getenv("PORT")
        DATABASE_URL = f"postgresql://{USER}:{PASS}@{HOST}:{PORT}/{DB}"
        # ---------------------------------------------------------------
        # Connection pool tuning — critical for multi-pod deployments.
        # With HPA scaling to 16 pods, each pod opens its own pool.
        # Total DB connections = pool_size × num_pods = 5 × 16 = 80
        # Max burst = (pool_size + max_overflow) × num_pods = 8 × 16 = 128
        #
        # INTERVIEW NOTE:
        #   At Revolut scale, use PgBouncer between app and DB to
        #   multiplex thousands of app connections into ~50 real DB conns.
        # ---------------------------------------------------------------
        _engine = create_engine(
            DATABASE_URL,
            pool_size=5,           # Persistent connections per pod
            max_overflow=3,        # Extra connections under burst (temporary)
            pool_timeout=30,       # Seconds to wait for a free connection
            pool_recycle=1800,     # Recreate connections every 30 min (avoid stale)
            pool_pre_ping=True,    # Verify connection is alive before using
        )
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


# --- MODELS ---

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    balance = Column(Float, default=0.0)
    # Account type: "cash", "debit", "credit"
    account_type = Column(String, default="cash")
    # Credit limit (credit accounts only)
    credit_limit = Column(Float, default=0.0)

    # Relationship: one account has many transactions
    transactions = relationship("Transaction", back_populates="account")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    # Type: "income" or "expense"
    # For subcategories — None (inherited from parent)
    type = Column(String, nullable=True, default="expense")
    # Parent category (NULL = root category)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Relationships
    transactions = relationship("Transaction", back_populates="category")
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Category", back_populates="children", remote_side=[id])

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Foreign Keys — link to account and category IDs
    account_id = Column(Integer, ForeignKey("accounts.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Transfer: flag + paired transaction ID
    is_transfer = Column(Boolean, default=False)
    transfer_pair_id = Column(Integer, nullable=True)

    # Back-references for convenient access in code
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

# 4. Initialization function
def init_db():
    try:
        Base.metadata.create_all(bind=get_engine())
        print("✅ Database updated successfully!")
        print("✅ Tables: Accounts, Categories, Transactions ready.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    init_db()
