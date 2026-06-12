import pytest

from app.modules.finanzas.parser import infer_category, parse_expense


class TestDescriptionFirst:
    def test_integer_amount(self):
        p = parse_expense("mercadona 44")
        assert p is not None
        assert p.description == "mercadona"
        assert p.amount == 44.0
        assert p.category_hint == "Supermercado"

    def test_decimal_with_dot(self):
        p = parse_expense("café 2.50")
        assert p.description == "café"
        assert p.amount == 2.5

    def test_decimal_with_comma(self):
        p = parse_expense("café 2,50")
        assert p.amount == 2.5

    def test_single_decimal_digit(self):
        p = parse_expense("taxi 10.5")
        assert p.amount == 10.5
        assert p.category_hint == "Gasolina / Transporte"

    def test_euro_symbol(self):
        p = parse_expense("café 2,50€")
        assert p.amount == 2.5

    def test_dollar_symbol(self):
        p = parse_expense("café 2.50$")
        assert p.amount == 2.5

    def test_multiword_description(self):
        p = parse_expense("cena con amigos 32.50")
        assert p.description == "cena con amigos"
        assert p.amount == 32.5
        assert p.category_hint == "Restaurantes"

    def test_uppercase_description(self):
        p = parse_expense("MERCADONA 44")
        assert p.description == "MERCADONA"
        assert p.category_hint == "Supermercado"

    def test_accented_description(self):
        p = parse_expense("pádel 15")
        assert p.description == "pádel"
        assert p.category_hint == "Padel / Deporte"

    def test_slash_in_description(self):
        p = parse_expense("gym 30")
        assert p.category_hint == "Gimnasio"

    def test_surrounding_whitespace_stripped(self):
        p = parse_expense("  mercadona 44  ")
        assert p is not None
        assert p.description == "mercadona"
        assert p.amount == 44.0


class TestAmountFirst:
    def test_integer_amount(self):
        p = parse_expense("44 mercadona")
        assert p is not None
        assert p.description == "mercadona"
        assert p.amount == 44.0
        assert p.category_hint == "Supermercado"

    def test_decimal_with_dot(self):
        p = parse_expense("2.50 café")
        assert p.description == "café"
        assert p.amount == 2.5

    def test_decimal_with_comma(self):
        p = parse_expense("2,50 café")
        assert p.amount == 2.5

    def test_euro_symbol_after_amount(self):
        p = parse_expense("44€ mercadona")
        assert p.amount == 44.0
        assert p.description == "mercadona"

    def test_multiword_description(self):
        p = parse_expense("32.50 cena con amigos")
        assert p.description == "cena con amigos"
        assert p.category_hint == "Restaurantes"


class TestInvalidInputs:
    @pytest.mark.parametrize("text", [
        "",
        "   ",
        "hola qué tal",
        "44",
        "2.50",
        "mercadona",
        "café 2.505",       # three decimal digits not allowed
        "viaje 1.200",      # thousands separator not supported
        "12 34",            # two numbers, no description
        "mercadona2 44",    # digits not allowed in description
    ])
    def test_returns_none(self, text):
        assert parse_expense(text) is None


class TestInferCategory:
    @pytest.mark.parametrize("description,expected", [
        ("mercadona", "Supermercado"),
        ("compra semanal LIDL", "Supermercado"),
        ("almuerzo", "Restaurantes"),
        ("cine con sara", "Ocio"),
        ("padel", "Padel / Deporte"),
        ("gasolinera repsol", "Gasolina / Transporte"),
        ("creatina", "Suplementos"),
        ("gimnasio", "Gimnasio"),
        ("vuelo a roma", "Viajes"),
        ("farmacia", None),
        ("", None),
    ])
    def test_keyword_inference(self, description, expected):
        assert infer_category(description) == expected

    def test_case_insensitive(self):
        assert infer_category("MERCADONA") == "Supermercado"

    def test_hint_is_none_for_unknown_description(self):
        p = parse_expense("farmacia 12")
        assert p is not None
        assert p.category_hint is None
