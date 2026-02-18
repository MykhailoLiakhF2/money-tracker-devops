from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

# --- ACCOUNTS ---
class AccountBase(BaseModel):
    name: str
    balance: float = 0.0
    account_type: str = "cash"      # cash | debit | credit
    credit_limit: float = 0.0       # credit accounts only

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    id: int

    class Config:
        from_attributes = True

# --- CATEGORIES ---
class CategoryBase(BaseModel):
    name: str
    type: Optional[str] = "expense"   # income | expense (None for subcategories)
    parent_id: Optional[int] = None   # NULL = root category

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True

class CategoryWithChildren(Category):
    """Category with subcategories for GET /categories/tree"""
    children: List[Category] = []

# --- TRANSACTIONS ---
class TransactionBase(BaseModel):
    amount: float
    description: Optional[str] = None
    account_id: int
    category_id: Optional[int] = None
    is_transfer: bool = False
    transfer_pair_id: Optional[int] = None

class TransactionCreate(TransactionBase):
    created_at: Optional[datetime] = None  # if not provided — current time

class TransactionUpdate(BaseModel):
    """For PUT — all fields optional"""
    amount: Optional[float] = None
    description: Optional[str] = None
    account_id: Optional[int] = None
    category_id: Optional[int] = None
    created_at: Optional[datetime] = None

class Transaction(TransactionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionResponse(Transaction):
    """Extended response with account and category names"""
    account_name: str = ""
    category_name: str = ""
    category_type: str = ""    # income | expense | transfer

# --- TRANSFERS ---
class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
