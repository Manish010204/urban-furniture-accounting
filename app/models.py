import enum
from datetime import date as date_type, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    admin = "admin"
    accountant = "accountant"
    contact = "contact"


class ContactType(str, enum.Enum):
    customer = "customer"
    vendor = "vendor"
    both = "both"


class ProductType(str, enum.Enum):
    goods = "goods"
    service = "service"
    combo = "combo"


class AccountType(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    income = "income"
    expense = "expense"
    capital = "capital"


class JournalType(str, enum.Enum):
    sales = "sales"
    purchase = "purchase"
    bank = "bank"
    cash = "cash"


class AnalyticType(str, enum.Enum):
    income = "income"
    expense = "expense"


class POStatus(str, enum.Enum):
    draft = "draft"
    billed = "billed"


class BillStatus(str, enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"


class SOStatus(str, enum.Enum):
    draft = "draft"
    invoiced = "invoiced"


class InvoiceStatus(str, enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    bank = "bank"


class PaymentDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)

    contact: Mapped["Contact"] = relationship(back_populates="users")


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[ContactType] = mapped_column(Enum(ContactType))
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(15), nullable=True)
    profile_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="contact")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[ProductType] = mapped_column(Enum(ProductType))
    sales_price: Mapped[float] = mapped_column(Float, default=0)
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)


class Journal(Base):
    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[JournalType] = mapped_column(Enum(JournalType))
    default_debit_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    default_credit_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    default_debit_account: Mapped["Account | None"] = relationship(foreign_keys=[default_debit_account_id])
    default_credit_account: Mapped["Account | None"] = relationship(foreign_keys=[default_credit_account_id])


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_id: Mapped[int] = mapped_column(ForeignKey("journals.id"))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    journal: Mapped["Journal"] = relationship()
    lines: Mapped[list["JournalEntryLine"]] = relationship(back_populates="entry", cascade="all, delete-orphan")

    @property
    def total_debit(self) -> float:
        return round(sum(l.debit for l in self.lines), 2)

    @property
    def total_credit(self) -> float:
        return round(sum(l.credit for l in self.lines), 2)


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[float] = mapped_column(Float, default=0)
    credit: Mapped[float] = mapped_column(Float, default=0)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()


class AnalyticAccount(Base):
    __tablename__ = "analytic_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[AnalyticType] = mapped_column(Enum(AnalyticType))


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    period_start: Mapped[date_type] = mapped_column(Date)
    period_end: Mapped[date_type] = mapped_column(Date)
    responsible_person: Mapped[str] = mapped_column(String(150))
    planned_amount: Mapped[float] = mapped_column(Float, default=0)
    analytic_account_id: Mapped[int] = mapped_column(ForeignKey("analytic_accounts.id"))

    analytic_account: Mapped["AnalyticAccount"] = relationship()


# ---------------------------------------------------------------------------
# Purchase flow
# ---------------------------------------------------------------------------

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus), default=POStatus.draft)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)

    vendor: Mapped["Contact"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="po", cascade="all, delete-orphan")
    bill: Mapped["VendorBill | None"] = relationship(back_populates="purchase_order", uselist=False)

    @property
    def total(self) -> float:
        return round(sum(l.qty * l.unit_price for l in self.lines), 2)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)

    po: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

    @property
    def total(self) -> float:
        return round(self.qty * self.unit_price, 2)


class VendorBill(Base):
    __tablename__ = "vendor_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    vendor_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    invoice_date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    due_date: Mapped[date_type] = mapped_column(Date)
    total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[BillStatus] = mapped_column(Enum(BillStatus), default=BillStatus.unpaid)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="bill")
    vendor: Mapped["Contact"] = relationship()
    journal_entry: Mapped["JournalEntry | None"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="vendor_bill")

    @property
    def amount_paid(self) -> float:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def amount_due(self) -> float:
        return round(self.total - self.amount_paid, 2)


# ---------------------------------------------------------------------------
# Sales flow
# ---------------------------------------------------------------------------

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    status: Mapped[SOStatus] = mapped_column(Enum(SOStatus), default=SOStatus.draft)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)

    customer: Mapped["Contact"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()
    lines: Mapped[list["SalesOrderLine"]] = relationship(back_populates="so", cascade="all, delete-orphan")
    invoice: Mapped["CustomerInvoice | None"] = relationship(back_populates="sales_order", uselist=False)

    @property
    def subtotal(self) -> float:
        return round(sum(l.qty * l.unit_price for l in self.lines), 2)

    @property
    def tax_amount(self) -> float:
        return round(sum(l.qty * l.unit_price * l.tax_percent / 100 for l in self.lines), 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax_amount, 2)


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    so_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    tax_percent: Mapped[float] = mapped_column(Float, default=0)

    so: Mapped["SalesOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

    @property
    def subtotal(self) -> float:
        return round(self.qty * self.unit_price, 2)

    @property
    def tax_amount(self) -> float:
        return round(self.subtotal * self.tax_percent / 100, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax_amount, 2)


class CustomerInvoice(Base):
    __tablename__ = "customer_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    invoice_date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    due_date: Mapped[date_type] = mapped_column(Date)
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    sales_order: Mapped["SalesOrder"] = relationship(back_populates="invoice")
    customer: Mapped["Contact"] = relationship()
    journal_entry: Mapped["JournalEntry | None"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer_invoice")

    @property
    def amount_paid(self) -> float:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def amount_due(self) -> float:
        return round(self.total - self.amount_paid, 2)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[PaymentDirection] = mapped_column(Enum(PaymentDirection))
    party_contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    amount: Mapped[float] = mapped_column(Float)
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    vendor_bill_id: Mapped[int | None] = mapped_column(ForeignKey("vendor_bills.id"), nullable=True)
    customer_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("customer_invoices.id"), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    party: Mapped["Contact"] = relationship()
    vendor_bill: Mapped["VendorBill | None"] = relationship(back_populates="payments")
    customer_invoice: Mapped["CustomerInvoice | None"] = relationship(back_populates="payments")
    journal_entry: Mapped["JournalEntry | None"] = relationship()
