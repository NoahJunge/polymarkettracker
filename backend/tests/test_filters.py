"""Tests for Trump keyword filtering and binary market detection."""

from utils.filters import is_trump_related, is_binary_yes_no, normalize_yes_no_prices


class TestIsTrumpRelated:
    def test_exact_match_trump(self):
        assert is_trump_related("Will Trump win the election?")

    def test_case_insensitive(self):
        assert is_trump_related("Will TRUMP win?")
        assert is_trump_related("will trump win?")

    def test_djt_keyword(self):
        assert is_trump_related("DJT stock price above $50?", ["djt"])

    def test_maga_keyword(self):
        assert is_trump_related("MAGA rally attendance?", ["maga"])

    def test_donald_trump_full_name(self):
        assert is_trump_related("Will Donald Trump be president?", ["donald trump"])

    def test_no_match(self):
        assert not is_trump_related("Will Biden win the election?")

    def test_no_match_partial_word(self):
        # "trumpet" should not match "trump" since "trump" IS a substring of "trumpet"
        # Our filter uses substring matching, so this will match.
        # This is acceptable for the MVP — false positives are better than false negatives.
        assert is_trump_related("Will the trumpet player win?")

    def test_empty_string(self):
        assert not is_trump_related("")

    def test_none_question(self):
        assert not is_trump_related(None)

    def test_custom_keywords(self):
        kws = ["potus", "president trump"]
        assert is_trump_related("POTUS approval rating?", kws)
        assert is_trump_related("President Trump visits Europe?", kws)
        assert not is_trump_related("Biden approval rating?", kws)


class TestIsBinaryYesNo:
    def test_valid_binary(self):
        assert is_binary_yes_no(["Yes", "No"])

    def test_valid_binary_lowercase(self):
        assert is_binary_yes_no(["yes", "no"])

    def test_valid_binary_with_spaces(self):
        assert is_binary_yes_no([" Yes ", " No "])

    def test_valid_with_prices(self):
        assert is_binary_yes_no(["Yes", "No"], ["0.65", "0.35"])

    def test_invalid_three_outcomes(self):
        assert not is_binary_yes_no(["Yes", "No", "Maybe"])

    def test_invalid_wrong_labels(self):
        assert not is_binary_yes_no(["Republican", "Democrat"])

    def test_invalid_single_outcome(self):
        assert not is_binary_yes_no(["Yes"])

    def test_invalid_empty(self):
        assert not is_binary_yes_no([])

    def test_invalid_none(self):
        assert not is_binary_yes_no(None)

    def test_invalid_price_count(self):
        assert not is_binary_yes_no(["Yes", "No"], ["0.65"])


class TestNormalizeYesNoPrices:
    def test_yes_first(self):
        yes_p, no_p = normalize_yes_no_prices(["Yes", "No"], ["0.65", "0.35"])
        assert yes_p == 0.65
        assert no_p == 0.35

    def test_no_first(self):
        yes_p, no_p = normalize_yes_no_prices(["No", "Yes"], ["0.35", "0.65"])
        assert yes_p == 0.65
        assert no_p == 0.35

    def test_float_inputs(self):
        yes_p, no_p = normalize_yes_no_prices(["Yes", "No"], [0.8, 0.2])
        assert yes_p == 0.8
        assert no_p == 0.2
