import json
import dspy
from datetime import date
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from rag import HybridRetriever, format_context

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


# ── Opportunity analysis (drives retrieval) ───────────────────────────────────

# Which product families a client already holds map into these retrieval
# categories; gaps map to the families we want the teller to explore.
_CHEQUING_TYPES = {
    AccountType.MINIMUM_CHEQUING, AccountType.EVERYDAY_CHEQUING,
    AccountType.UNLIMITED_CHEQUING, AccountType.ALL_INCLUSIVE_CHEQUING,
}
_SAVINGS_TYPES = {AccountType.EVERYDAY_SAVINGS, AccountType.HIGH_INTEREST_TFSA, AccountType.EPREMIUM}
_REGISTERED_WRAPPERS = {InvestmentWrapper.TFSA, InvestmentWrapper.RRSP, InvestmentWrapper.FHSA}

# Only flag idle cash for an investment conversation once deposit balances reach
# roughly this level — small everyday balances are not an investment opportunity.
IDLE_CASH_THRESHOLD = 20_000


def analyze_opportunities(client: "ClientProfile") -> tuple[list[str], list[str]]:
    """Return (human-readable opportunity notes, retrieval category filter).

    Deterministic, profile-driven signal that (a) tells the LLM what to focus on
    and (b) restricts retrieval to the relevant product families — the metadata
    pre-filter that keeps hybrid search focused.
    """
    notes: list[str] = []
    categories: set[str] = set()

    account_types = {a.type for a in client.accounts}
    wrappers = {i.wrapper for i in client.investments}
    liability_types = {l.type for l in client.liabilities}

    # Gaps in standard products.
    if not (account_types & _CHEQUING_TYPES):
        notes.append("No chequing account on file — core banking / primacy opportunity.")
        categories.add("core_banking")
    if not (account_types & _SAVINGS_TYPES):
        notes.append("No savings account on file — savings opportunity.")
        categories.add("core_banking")
    if not (wrappers & _REGISTERED_WRAPPERS):
        notes.append("No registered investment (TFSA/RRSP/FHSA) — investment opportunity.")
        categories.add("investments")
    if LiabilityType.VISA not in liability_types:
        notes.append("No credit card on file — credit product opportunity.")
        categories.add("credit_cards")

    # Cross-sell signals on existing holdings.
    idle_cash = sum(a.balance for a in client.accounts)
    if idle_cash >= IDLE_CASH_THRESHOLD:
        notes.append(f"~${idle_cash:,.0f} idle cash in deposit accounts — investment conversation.")
        categories.add("investments")
    if any(l.type == LiabilityType.VISA for l in client.liabilities):
        notes.append("Holds a credit card — backup/travel card or limit conversation possible.")
        categories.add("credit_cards")
    if any(l.type in (LiabilityType.MORTGAGE, LiabilityType.HELOC) for l in client.liabilities):
        categories.add("mortgages")

    # If nothing flagged, let retrieval range over the whole corpus.
    return notes, sorted(categories)


def build_retrieval_query(client: "ClientProfile", notes: list[str]) -> str:
    """Compose the natural-language retrieval query from profile + opportunities."""
    parts = [client.to_prompt_string()]
    if notes:
        parts.append("Opportunities to explore: " + " ".join(notes))
    return " ".join(parts)


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
    Given a client's profile and a list of concrete opportunities, generate
    DIRECT questions the teller can ask — each one names something specific you
    observe about this client's holdings (or gaps) and creates a reason for
    them to grow their business with the bank.

    Every question MUST:
      • Lead with a specific observation about THIS client — reference the real
        product they hold or the gap they have, by name (their one credit card,
        their idle cash, their missing savings account, a maturing GIC, an
        unused pre-approval, an upcoming mortgage renewal).
      • Follow with a pointed question that surfaces a need or risk they haven't
        acted on (fraud exposure with a single card, cash that isn't earning,
        a missing core product, a pre-approval about to expire).
      • Stay warm and conversational — direct is not pushy — but do NOT fall
        back on generic "what are your financial goals?" phrasing.

    Value is generated by increasing the customer's business: opening a new
    account, moving idle cash into investments (a financial planner if total
    balance is over $100k, a personal banker if under), opening a new credit
    card, or gaining primacy (getting direct deposit into a chequing account).

    Be this direct:
      • Missing a savings account →
        "I see you don't have a savings account with us — where are you keeping
         the money you set aside right now?"
      • Holds only one credit card →
        "Looks like you've got just the one card — is that the one you use
         everywhere? If it ever got compromised you'd be left without a backup.
         Worth looking at a second card for travel or fraud protection?"
      • An unused pre-approval →
        "You're actually pre-approved for a line of credit — want me to get
         that set up while it's available?"

    Raise idle cash / "put your money to work" ONLY when an idle-cash line
    appears in the opportunities list — never for a small everyday balance.
    Do not invent opportunities that are not in the opportunities list or
    clearly supported by the profile (e.g. don't claim a client has no
    investments when their profile lists some).

    Ground every product reference in the retrieved product context — do not
    invent rates, fees, or terms.
    """
    client_profile: str = dspy.InputField(
        desc="Client context: name, age, accounts, investments, liabilities, pre-approvals")
    opportunities: str = dspy.InputField(
        desc="Concrete, profile-derived opportunities and gaps for this client. "
             "Anchor each question to one of these — name the specific product or gap.")
    product_context: str = dspy.InputField(
        desc="Retrieved product documents (rates, fees, eligibility, fit). "
             "Ground every product reference in these — do not invent rates or terms.")
    num_questions: int = dspy.InputField(desc="Number of questions to generate")
    conversation_prompts: str = dspy.OutputField(
        desc="Numbered list of open-ended questions. Each on its own line. "
             "Format: 1. [question]  Opportunity: [brief note on what this might uncover]"
    )


class RankAndRefinePrompts(dspy.Signature):
    """
    Review a set of conversation prompts and select the top ones most likely
    to lead to new business for the bank. Keep them DIRECT and specific — each
    should name what you observe about the client and give a concrete reason to
    act. Tighten the wording so it sounds natural and empathetic, but never
    soften a pointed, observation-led question back into a generic one.

    The bank gets new business through: opening new accounts, moving large sums
    of idle cash into investments, opening new credit cards, and gaining primacy
    (direct deposit into the account). Favour questions that make one of these
    the obvious next step for the client.
    """
    raw_prompts: str = dspy.InputField(desc="Initial list of conversation prompts")
    client_context: str = dspy.InputField(desc="Client profile summary")
    refined_prompts: str = dspy.OutputField(
        desc="Top 3 refined prompts, ranked by relevance. "
             "Format: RANK [n] | QUESTION: [question] | REVEALS: [what need this surfaces]"
    )


# ── DSPy Module ───────────────────────────────────────────────────────────────

class BankingAssistantModule(dspy.Module):
    def __init__(self, retriever: Optional[HybridRetriever] = None, top_n: int = 4):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateConversationPrompts)
        self.refine = dspy.ChainOfThought(RankAndRefinePrompts)
        self.retriever = retriever
        self.top_n = top_n

    def forward(self, client: "ClientProfile", num_questions: int = 5):
        profile_str = client.to_prompt_string()

        # Deterministic opportunity analysis drives BOTH retrieval steering and
        # the generation prompt, so questions can name the specific gap/holding.
        notes, categories = analyze_opportunities(client)
        opportunities = (
            "\n".join(f"- {n}" for n in notes)
            if notes
            else "(no standout gaps flagged; explore primacy, idle cash, and growth)"
        )

        # Retrieval: filter categories → hybrid + rerank.
        product_context = "(retrieval disabled)"
        retrieved = []
        if self.retriever is not None:
            query = build_retrieval_query(client, notes)
            retrieved = self.retriever.retrieve(
                query, categories=categories or None, top_n=self.top_n
            )
            product_context = format_context(retrieved)

        gen = self.generate(
            client_profile=profile_str,
            opportunities=opportunities,
            product_context=product_context,
            num_questions=num_questions,
        )
        refined = self.refine(raw_prompts=gen.conversation_prompts, client_context=profile_str)
        return dspy.Prediction(
            raw_prompts=gen.conversation_prompts,
            refined_prompts=refined.refined_prompts,
            product_context=product_context,
            retrieved=retrieved,
        )


# ── LM Setup ──────────────────────────────────────────────────────────────────

def setup_lm(model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
    lm = dspy.LM(f"ollama/{model}", api_base=base_url, max_tokens=1024, temperature=0.7)
    dspy.configure(lm=lm)