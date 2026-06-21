import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedExpense:
    description: str
    amount: float
    category_hint: Optional[str] = None


# Patterns: "café 2.50", "2.50 café", "café 2,50€", "supermercado mercadona 44"
PATTERN = re.compile(
    r'^(?P<desc>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s/]+?)\s+(?P<amt>\d+[.,]?\d{0,2})[€$]?$'
    r'|^(?P<amt2>\d+[.,]?\d{0,2})[€$]?\s+(?P<desc2>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s/]+)$'
)

# Keywords → category name (must match Category.name in DB)
KEYWORDS: dict[str, list[str]] = {
    "Supermercado": ["mercadona", "lidl", "carrefour", "aldi", "consum", "supermercado", "compra", "family"],
    "Restaurantes": ["restaurante", "bar", "bravas", "buffalo", "almuerzo", "cena", "kebab", "ramen", "fuji", "sushi", "chino", "indio", "nepalí"],
    "Ocio": ["cine", "teatro", "billar", "ocio", "helado", "horchata", "bolera", "concierto"],
    "Padel / Deporte": ["pádel", "padel", "pcv", "fullpadel", "climb", "roco", "benaguacil", "escalada", "deporte"],
    "Psicólogo": ["terapia", "psicólogo"],
    "Gasolina / Transporte": ["gasolina", "gasolinera", "ballenoil", "plenoil", "bus", "metro", "fgv", "emt", "taxi", "uber", "parking"],
    "Suplementos": ["creatina", "proteína", "suplemento", "magnesio"],
    "Gimnasio": ["gym", "gimnasio"],
    "Viajes": ["viaje", "vuelo", "hotel", "cumple"],
}


def infer_category(description: str) -> Optional[str]:
    desc_lower = description.lower()
    for category, keywords in KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return None


def parse_expense(text: str) -> Optional[ParsedExpense]:
    text = text.strip()
    m = PATTERN.match(text)
    if not m:
        return None

    if m.group("desc"):
        desc = m.group("desc").strip()
        amt = m.group("amt").replace(",", ".")
    else:
        desc = m.group("desc2").strip()
        amt = m.group("amt2").replace(",", ".")

    if not amt or amt == ".":
        return None

    return ParsedExpense(
        description=desc,
        amount=float(amt),
        category_hint=infer_category(desc),
    )
