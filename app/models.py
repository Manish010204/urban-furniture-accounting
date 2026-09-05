import enum
from datetime import date as date_type, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
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
    confirmed = "confirmed"
    billed = "billed"
    cancelled = "cancelled"


class BillStatus(str, enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"


class SOStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    invoiced = "invoiced"
    cancelled = "cancelled"


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


class BudgetStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    revised = "revised"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    login_id: Mapped[str] = mapped_column(String(12), unique=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(15), nullable=True)
    profile_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    users: Mapped[list["User"]] = relationship(back_populates="contact")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[ProductType] = mapped_column(Enum(ProductType))
    sales_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    def total_debit(self) -> Decimal:
        return round(sum(l.debit for l in self.lines), 2)

    @property
    def total_credit(self) -> Decimal:
        return round(sum(l.credit for l in self.lines), 2)

    @property
    def partner(self) -> "Contact | None":
        for line in self.lines:
            if line.partner_contact_id:
                return line.partner_contact
        return None


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)
    partner_contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()
    partner_contact: Mapped["Contact | None"] = relationship()


class AnalyticAccount(Base):
    __tablename__ = "analytic_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[AnalyticType] = mapped_column(Enum(AnalyticType))


class Budget(Base):
    """A budget is a named period with one or more analytic-account lines
    (each carrying a committed amount). Confirming a budget freezes it for
    reporting; revising it clones a new confirmed budget with new committed
    amounts and freezes the original into "revised" state, linked via
    revises_budget_id."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    period_start: Mapped[date_type] = mapped_column(Date)
    period_end: Mapped[date_type] = mapped_column(Date)
    responsible_person: Mapped[str] = mapped_column(String(150))
    status: Mapped[BudgetStatus] = mapped_column(Enum(BudgetStatus), default=BudgetStatus.draft)
    revises_budget_id: Mapped[int | None] = mapped_column(ForeignKey("budgets.id"), nullable=True)

    revises_budget: Mapped["Budget | None"] = relationship(remote_side=[id])
    lines: Mapped[list["BudgetLine"]] = relationship(back_populates="budget", cascade="all, delete-orphan")

    @property
    def planned_amount(self) -> Decimal:
        return round(sum(l.committed_amount for l in self.lines), 2)


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"))
    analytic_account_id: Mapped[int] = mapped_column(ForeignKey("analytic_accounts.id"))
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    budget: Mapped["Budget"] = relationship(back_populates="lines")
    analytic_account: Mapped["AnalyticAccount"] = relationship()

    @property
    def type(self) -> AnalyticType:
        return self.analytic_account.type


# ---------------------------------------------------------------------------
# Purchase flow
# ---------------------------------------------------------------------------

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus), default=POStatus.draft)

    vendor: Mapped["Contact"] = relationship()
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="po", cascade="all, delete-orphan")
    bill: Mapped["VendorBill | None"] = relationship(back_populates="purchase_order", uselist=False)

    @property
    def number(self) -> str:
        return f"P{self.id:05d}"

    @property
    def total(self) -> Decimal:
        return round(sum(l.qty * l.unit_price for l in self.lines), 2)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)

    po: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()

    @property
    def total(self) -> Decimal:
        return round(self.qty * self.unit_price, 2)


class VendorBill(Base):
    __tablename__ = "vendor_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    invoice_date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    due_date: Mapped[date_type] = mapped_column(Date)
    status: Mapped[BillStatus] = mapped_column(Enum(BillStatus), default=BillStatus.unpaid)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    purchase_order: Mapped["PurchaseOrder | None"] = relationship(back_populates="bill")
    vendor: Mapped["Contact"] = relationship()
    journal_entry: Mapped["JournalEntry | None"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="vendor_bill")
    lines: Mapped[list["VendorBillLine"]] = relationship(back_populates="bill", cascade="all, delete-orphan")

    @property
    def number(self) -> str:
        return f"Bill/{self.invoice_date.year}/{self.id:04d}"

    @property
    def total(self) -> Decimal:
        return round(sum(l.total for l in self.lines), 2)

    @property
    def amount_paid(self) -> Decimal:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def amount_due(self) -> Decimal:
        return round(self.total - self.amount_paid, 2)

    @property
    def is_overdue(self) -> bool:
        return self.status != BillStatus.paid and self.due_date < date_type.today()


class VendorBillLine(Base):
    __tablename__ = "vendor_bill_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("vendor_bills.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    bill: Mapped["VendorBill"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    account: Mapped["Account | None"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()

    @property
    def total(self) -> Decimal:
        return round(self.qty * self.unit_price, 2)


# ---------------------------------------------------------------------------
# Sales flow
# ---------------------------------------------------------------------------

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    status: Mapped[SOStatus] = mapped_column(Enum(SOStatus), default=SOStatus.draft)

    customer: Mapped["Contact"] = relationship()
    lines: Mapped[list["SalesOrderLine"]] = relationship(back_populates="so", cascade="all, delete-orphan")
    invoice: Mapped["CustomerInvoice | None"] = relationship(back_populates="sales_order", uselist=False)

    @property
    def number(self) -> str:
        return f"S{self.id:05d}"

    @property
    def subtotal(self) -> Decimal:
        return round(sum(l.qty * l.unit_price for l in self.lines), 2)

    @property
    def tax_amount(self) -> Decimal:
        return round(sum(l.qty * l.unit_price * l.tax_percent / 100 for l in self.lines), 2)

    @property
    def total(self) -> Decimal:
        return round(self.subtotal + self.tax_amount, 2)


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    so_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)

    so: Mapped["SalesOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        return round(self.qty * self.unit_price, 2)

    @property
    def tax_amount(self) -> Decimal:
        return round(self.subtotal * self.tax_percent / 100, 2)

    @property
    def total(self) -> Decimal:
        return round(self.subtotal + self.tax_amount, 2)


class CustomerInvoice(Base):
    __tablename__ = "customer_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id"), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    invoice_date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    due_date: Mapped[date_type] = mapped_column(Date)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    sales_order: Mapped["SalesOrder | None"] = relationship(back_populates="invoice")
    customer: Mapped["Contact"] = relationship()
    journal_entry: Mapped["JournalEntry | None"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer_invoice")
    lines: Mapped[list["CustomerInvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")

    @property
    def number(self) -> str:
        return f"INV/{self.invoice_date.year}/{self.id:04d}"

    @property
    def subtotal(self) -> Decimal:
        return round(sum(l.subtotal for l in self.lines), 2)

    @property
    def tax_amount(self) -> Decimal:
        return round(sum(l.tax_amount for l in self.lines), 2)

    @property
    def total(self) -> Decimal:
        return round(self.subtotal + self.tax_amount, 2)

    @property
    def amount_paid(self) -> Decimal:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def amount_due(self) -> Decimal:
        return round(self.total - self.amount_paid, 2)

    @property
    def is_overdue(self) -> bool:
        return self.status != InvoiceStatus.paid and self.due_date < date_type.today()


class CustomerInvoiceLine(Base):
    __tablename__ = "customer_invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("customer_invoices.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    analytic_account_id: Mapped[int | None] = mapped_column(ForeignKey("analytic_accounts.id"), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    invoice: Mapped["CustomerInvoice"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()
    account: Mapped["Account | None"] = relationship()
    analytic_account: Mapped["AnalyticAccount | None"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        return round(self.qty * self.unit_price, 2)

    @property
    def tax_amount(self) -> Decimal:
        return round(self.subtotal * self.tax_percent / 100, 2)

    @property
    def total(self) -> Decimal:
        return round(self.subtotal + self.tax_amount, 2)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[PaymentDirection] = mapped_column(Enum(PaymentDirection))
    party_contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    date: Mapped[date_type] = mapped_column(Date, default=date_type.today)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_bill_id: Mapped[int | None] = mapped_column(ForeignKey("vendor_bills.id"), nullable=True)
    customer_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("customer_invoices.id"), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    party: Mapped["Contact"] = relationship()
    vendor_bill: Mapped["VendorBill | None"] = relationship(back_populates="payments")
    customer_invoice: Mapped["CustomerInvoice | None"] = relationship(back_populates="payments")
    journal_entry: Mapped["JournalEntry | None"] = relationship()
