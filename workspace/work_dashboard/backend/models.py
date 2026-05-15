"""Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import Optional


# --- Properties ---
class PropertyCreate(BaseModel):
    address: str
    owner_name: str = "Jake"
    tenant_url_slug: Optional[str] = None
    access_notes: Optional[str] = None


class PropertyOut(PropertyCreate):
    id: int


# --- Jobs ---
class JobCreate(BaseModel):
    property_id: int
    description: str
    cost: float = 0
    billing_type: str = "flat"
    hours: float = 0
    status: str = "pending"
    work_order_id: Optional[int] = None


class JobUpdate(BaseModel):
    property_id: Optional[int] = None
    description: Optional[str] = None
    cost: Optional[float] = None
    billing_type: Optional[str] = None
    hours: Optional[float] = None
    status: Optional[str] = None


class JobOut(BaseModel):
    id: int
    property_id: int
    property_address: Optional[str] = None
    work_order_id: Optional[int] = None
    description: str
    cost: float
    billing_type: str
    hours: float
    status: str


# --- Payments ---
class PaymentCreate(BaseModel):
    amount: float
    date: str
    note: str = ""


class PaymentOut(PaymentCreate):
    id: int


# --- Work Orders ---
class WorkOrderCreate(BaseModel):
    property_id: int
    description: str
    urgency: str = "medium"


class WorkOrderOut(BaseModel):
    id: int
    property_id: int
    property_address: Optional[str] = None
    description: str
    urgency: str
    status: str
    submitted_at: Optional[str] = None


# --- Dashboard bulk shape (backward compat with existing JSON) ---
class DashboardData(BaseModel):
    completed: list[list[str]] = []  # [address, description, cost]
    scheduled: list[list[str]] = []
    pending: list[list[str]] = []
    payments: list[list[str]] = []  # [date, amount, note]
