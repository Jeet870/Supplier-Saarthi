"""Record shapes agreed on 19 Nov 2026.

Rule: if the shopkeeper did not say it, the field is None (null). Never guess.
"""
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------- Allowed values ----------

class DeliveryStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISPUTED = "DISPUTED"


class PromiseStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    PARTLY_FULFILLED = "PARTLY_FULFILLED"
    NOT_FULFILLED = "NOT_FULFILLED"
    CANCELLED = "CANCELLED"


class DeliveryIssue(str, Enum):
    MISSING_QTY = "MISSING_QTY"
    DAMAGED = "DAMAGED"
    QUALITY = "QUALITY"  # insects, fungus, bad smell, stale, expired
    WRONG_SKU = "WRONG_SKU"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    INVOICE_MISMATCH = "INVOICE_MISMATCH"
    OTHER = "OTHER"  # anything else; the shopkeeper's words go in "note"


class PromiseType(str, Enum):
    DISCOUNT = "DISCOUNT"
    REPLACEMENT = "REPLACEMENT"
    CREDIT_NOTE = "CREDIT_NOTE"
    FREE_GOODS = "FREE_GOODS"
    CREDIT_PERIOD = "CREDIT_PERIOD"
    PRICE_LOCK = "PRICE_LOCK"
    OTHER = "OTHER"


class ValueType(str, Enum):
    PERCENT = "PERCENT"
    AMOUNT_RS = "AMOUNT_RS"
    QUANTITY = "QUANTITY"
    DAYS = "DAYS"


class AppliesTo(str, Enum):
    NEXT_ORDER = "NEXT_ORDER"
    DATE = "DATE"
    NONE = "NONE"


# The categories we know in advance. The AI may also make up a new category for a problem
# that fits none of these (see IssueItem.custom).
PREDEFINED_ISSUES = tuple(i.value for i in DeliveryIssue)


# ---------- One problem found with a product ----------

class IssueItem(BaseModel):
    type: str  # one of PREDEFINED_ISSUES, or a new UPPER_SNAKE_CASE category made by the AI
    detail: Optional[str] = None  # the shopkeeper's own words, e.g. "ghun lag gaya"
    qty: Optional[float] = None  # how many were affected, only if said
    custom: bool = False  # True when the AI made up the category


# ---------- One product line inside a delivery record ----------

class DeliveryLine(BaseModel):
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    unit: Optional[str] = None  # carton, packet, kg ...
    expected_qty: Optional[float] = None  # ordered, or on the bill
    received_qty: Optional[float] = None  # what actually came
    damaged_qty: Optional[float] = None
    shortage_qty: Optional[float] = None  # how much is missing
    issue: str  # the MAIN problem (first in issues). Kept so older code that reads "issue" still works
    issues: list[IssueItem] = Field(default_factory=list)  # EVERY problem for this product
    amount_diff_rs: Optional[float] = None  # rupees too much or too little
    note: Optional[str] = None


# ---------- Fields shared by BOTH record types ----------

class RecordBase(BaseModel):
    id: Optional[int] = None  # made by the database
    supplier_id: Optional[int] = None  # matched from the supplier list
    supplier_name: Optional[str] = None  # e.g. Sharma Distributors
    event_date: Optional[date] = None  # YYYY-MM-DD, the day it happened
    transcript: str = ""  # the words that were heard
    photos: list[str] = Field(default_factory=list)  # links to pictures
    summary_text: Optional[str] = None  # the message that goes to WhatsApp
    confirmed: bool = False  # True only after the person says Haan
    created_at: Optional[datetime] = None  # made by the database


# ---------- The two record types ----------

class DeliveryDiscrepancy(RecordBase):
    record_type: Literal["DELIVERY_DISCREPANCY"] = "DELIVERY_DISCREPANCY"
    status: DeliveryStatus = DeliveryStatus.DRAFT  # DRAFT -> OPEN on Haan
    lines: list[DeliveryLine] = Field(default_factory=list)


class SupplierPromise(RecordBase):
    record_type: Literal["SUPPLIER_PROMISE"] = "SUPPLIER_PROMISE"
    status: PromiseStatus = PromiseStatus.DRAFT  # DRAFT -> OPEN on Haan
    promise_type: PromiseType
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    value: Optional[float] = None
    value_type: Optional[ValueType] = None
    unit: Optional[str] = None
    applies_to: AppliesTo = AppliesTo.NONE
    follow_up_date: Optional[date] = None


# Use this when a record can be either type; record_type decides which one.
Record = Annotated[
    Union[DeliveryDiscrepancy, SupplierPromise],
    Field(discriminator="record_type"),
]