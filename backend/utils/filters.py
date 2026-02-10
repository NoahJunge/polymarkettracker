"""Trump keyword matching and binary market detection utilities."""

DEFAULT_TRUMP_KEYWORDS = [
    "trump",
    "donald trump",
    "djt",
    "maga",
    "potus",
    "president trump",
]


def is_trump_related(question: str, keywords: list[str] | None = None) -> bool:
    """Check if a market question contains any Trump-related keyword (case-insensitive)."""
    if not question:
        return False
    kws = keywords or DEFAULT_TRUMP_KEYWORDS
    question_lower = question.lower()
    return any(kw.lower() in question_lower for kw in kws)


def is_binary_yes_no(outcomes: list[str] | None, outcome_prices: list | None = None) -> bool:
    """Check if a market is a binary Yes/No market with prices present."""
    if not outcomes or len(outcomes) != 2:
        return False
    labels = {o.strip().lower() for o in outcomes}
    if labels != {"yes", "no"}:
        return False
    if outcome_prices is not None and len(outcome_prices) != 2:
        return False
    return True


def normalize_yes_no_prices(
    outcomes: list[str], outcome_prices: list[str | float]
) -> tuple[float, float]:
    """Return (yes_price, no_price) regardless of outcome order in the API response."""
    prices = [float(p) for p in outcome_prices]
    if outcomes[0].strip().lower() == "yes":
        return prices[0], prices[1]
    return prices[1], prices[0]
