import json
import dspy
from datetime import date
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# ── Enums ─────────────────────────────────────────────────────────────────────

class AccountType(str, Enum):
    MINIMUM_CHEQUING = "minimum_chequing"
    EVERYDAY_CHEQUING = "everyday_chequing"
    UNLIMITED_CHEQUING = "unlimited_chequing"
    ALL_INCLUSIVE_CHEQUING = "all_inclusive_chequing"
    EVERYDAY_SAVINGS = "everyday_savings"
    HIGH_INTEREST_TFSA = "high_interest_tfsa"
    EPREMIUM = "epremium"


class InvestmentType(str, Enum):
    GIC = "GIC"
    MUTUAL_FUND = "MUTUAL_FUND"


class InvestmentWrapper(str, Enum):
    TFSA = "TFSA"
    RRSP = "RRSP"
    FHSA = "FHSA"
    NON_REG = "NON_REG"


class LiabilityType(str, Enum):
    VISA = "VISA"
    LOC = "LOC"
    HELOC = "HELOC"
    MORTGAGE = "MORTGAGE"
    LOAN = "LOAN"


class PreapprovalProduct(str, Enum):
    VISA = "VISA"
    LOC = "LOC"


# ── Asset dataclasses ─────────────────────────────────────────────────────────

@dataclass
class BankAccount:
    account_number: str
    transit_number: str
    type: AccountType
    balance: float


@dataclass
class GICDetails:
    maturity_date: date
    interest_rate: float


@dataclass
class MutualFundDetails:
    mer: float
    units: float
    nav: float


@dataclass
class Investment:
    account_number: str
    type: InvestmentType
    wrapper: InvestmentWrapper
    start_date: date
    principal: float
    current_value: float
    details: Optional[GICDetails | MutualFundDetails] = None


@dataclass
class Liability:
    account_number: str
    balance: float
    type: LiabilityType
    credit_limit: int
    interest_rate: float
    renewal_date: Optional[date] = None  # HELOC / MORTGAGE only


@dataclass
class Preapproval:
    product: PreapprovalProduct
    credit_limit: int
    expiry_date: date


# ── Top-level client profile ──────────────────────────────────────────────────

@dataclass
class ClientProfile:
    name: str
    age: int
    birthday: date
    phone: str
    email: str
    accounts: list[BankAccount] = field(default_factory=list)
    investments: list[Investment] = field(default_factory=list)
    liabilities: list[Liability] = field(default_factory=list)
    preapprovals: list[Preapproval] = field(default_factory=list)

    def to_prompt_string(self) -> str:
        parts = [
            f"Client: {self.name}, age {self.age}",
        ]

        if self.accounts:
            acc_str = ", ".join(
                f"{a.type.value.replace('_', ' ').title()} ${a.balance:,.2f}"
                for a in self.accounts
            )
            parts.append(f"Banking accounts: {acc_str}")

        if self.investments:
            inv_str = ", ".join(
                f"{i.type.value} ({i.wrapper.value}) current value ${i.current_value:,.2f}"
                for i in self.investments
            )
            parts.append(f"Investments: {inv_str}")

        if self.liabilities:
            lib_str = ", ".join(
                f"{l.type.value} balance ${l.balance:,.2f} at {l.interest_rate:.2f}% "
                f"(limit ${l.credit_limit:,})"
                + (f" renews {l.renewal_date}" if l.renewal_date else "")
                for l in self.liabilities
            )
            parts.append(f"Liabilities: {lib_str}")

        if self.preapprovals:
            pre_str = ", ".join(
                f"{p.product.value} up to ${p.credit_limit:,} (expires {p.expiry_date})"
                for p in self.preapprovals
            )
            parts.append(f"Pre-approvals: {pre_str}")

        return " | ".join(parts)


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _parse_account(raw: dict) -> BankAccount:
    return BankAccount(
        account_number=raw["account_number"],
        transit_number=raw["transit_number"],
        type=AccountType(raw["type"]),
        balance=float(raw["balance"]),
    )


def _parse_investment(raw: dict) -> Investment:
    inv_type = InvestmentType(raw["type"])
    details_raw = raw.get("details", {})

    if inv_type == InvestmentType.GIC:
        details = GICDetails(
            maturity_date=_parse_date(details_raw["maturity_date"]),
            interest_rate=float(details_raw["interest_rate"]),
        )
    elif inv_type == InvestmentType.MUTUAL_FUND:
        details = MutualFundDetails(
            mer=float(details_raw["mer"]),
            units=float(details_raw["units"]),
            nav=float(details_raw["nav"]),
        )
    else:
        details = None

    return Investment(
        account_number=raw["account_number"],
        type=inv_type,
        wrapper=InvestmentWrapper(raw["wrapper"]),
        start_date=_parse_date(raw["start_date"]),
        principal=float(raw["principal"]),
        current_value=float(raw["current_value"]),
        details=details,
    )


def _parse_liability(raw: dict) -> Liability:
    lib_type = LiabilityType(raw["type"])
    renewal_date = None
    if lib_type in (LiabilityType.HELOC, LiabilityType.MORTGAGE):
        renewal_date = _parse_date(raw["details"]["renewal_date"])

    return Liability(
        account_number=raw["account_number"],
        balance=float(raw["balance"]),
        type=lib_type,
        credit_limit=int(raw["credit_limit"]),
        interest_rate=float(raw["interest_rate"]),
        renewal_date=renewal_date,
    )


def _parse_preapproval(raw: dict) -> Preapproval:
    return Preapproval(
        product=PreapprovalProduct(raw["product"]),
        credit_limit=int(raw["credit_limit"]),
        expiry_date=_parse_date(raw["expiry_date"]),
    )


# ── Main loader ───────────────────────────────────────────────────────────────

def load_client(path: str) -> ClientProfile:
    """Load and parse a ClientProfile from a JSON file."""
    data = json.loads(Path(path).read_text())
    assets = data.get("assets", {})

    return ClientProfile(
        name=data["name"],
        age=int(data["age"]),
        birthday=_parse_date(data["birthday"]),
        phone=data["phone"],
        email=data["email"],
        accounts=[
            _parse_account(a)
            for a in assets.get("core_banking", [])
        ],
        investments=[
            _parse_investment(i)
            for i in assets.get("investments", [])
        ],
        liabilities=[
            _parse_liability(l)
            for l in data.get("liabilities", [])
        ],
        preapprovals=[
            _parse_preapproval(p)
            for p in data.get("preapprovals", [])
        ],
    )


# ── DSPy Signatures ───────────────────────────────────────────────────────────

class GenerateConversationPrompts(dspy.Signature):
    """
    You are a senior bank relationship manager coaching a teller.
    Given a client's profile, generate open-ended questions the teller can
    ask naturally during the interaction to uncover needs and create value.
    Focus on life events, goals, and pain points — not product pitching.
    Questions must feel warm, genuine, and conversational.

    Value is generated through increasing a customer's business with the bank. Business is increase when
    a customer opens a new account, makes investments either through a financial planner (over $100k total balance)
    or a personal banker (under $100k), and, opens up new credit cards.

    If a client has multiple credit cards, you can frame the question around having a smaller credit limit card
    in case of fraud and having a backup for travelling. If a client is missing a standard product (chequing account,
    saving account, tfsa/rrsp/fhsa) then ask an open-ended question surrounding those.
    """
    client_profile: str = dspy.InputField(
        desc="Client context: name, age, accounts, investments, liabilities, pre-approvals")
    num_questions: int = dspy.InputField(desc="Number of questions to generate")
    conversation_prompts: str = dspy.OutputField(
        desc="Numbered list of open-ended questions. Each on its own line. "
             "Format: 1. [question]  Opportunity: [brief note on what this might uncover]"
    )


class RankAndRefinePrompts(dspy.Signature):
    """
    Review a set of conversation prompts and select the top ones most likely
    to naturally lead to sales units for the bank. Rewrite them to
    sound more natural and empathetic if needed.

    The bank gets sales through: opening up new accounts, making investments using large sums of idle cash,
    opening up new credit cards and gaining primacy (set up direct deposit into the account). Make sure to
    ask questions that help the bank while being natural and empathetic.
    """
    raw_prompts: str = dspy.InputField(desc="Initial list of conversation prompts")
    client_context: str = dspy.InputField(desc="Client profile summary")
    refined_prompts: str = dspy.OutputField(
        desc="Top 3 refined prompts, ranked by relevance. "
             "Format: RANK [n] | QUESTION: [question] | REVEALS: [what need this surfaces]"
    )


# ── DSPy Module ───────────────────────────────────────────────────────────────

class BankingAssistantModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateConversationPrompts)
        self.refine = dspy.ChainOfThought(RankAndRefinePrompts)

    def forward(self, client_profile: str, num_questions: int = 5):
        gen = self.generate(client_profile=client_profile, num_questions=num_questions)
        refined = self.refine(raw_prompts=gen.conversation_prompts, client_context=client_profile)
        return dspy.Prediction(
            raw_prompts=gen.conversation_prompts,
            refined_prompts=refined.refined_prompts,
        )


# ── LM Setup ──────────────────────────────────────────────────────────────────

def setup_lm(model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
    lm = dspy.LM(f"ollama/{model}", api_base=base_url, max_tokens=1024, temperature=0.7)
    dspy.configure(lm=lm)