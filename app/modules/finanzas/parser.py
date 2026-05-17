import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GastoParsed:
    descripcion: str
    cantidad: float
    categoria_hint: Optional[str] = None  # nombre aproximado, se resuelve en handler


# Patrones: "café 2.50", "2.50 café", "café 2,50€", "supermercado mercadona 44"
PATTERN = re.compile(
    r'^(?P<desc>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s/]+?)\s+(?P<amt>\d+[.,]?\d{0,2})[€$]?$'
    r'|^(?P<amt2>\d+[.,]?\d{0,2})[€$]?\s+(?P<desc2>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s/]+)$'
)

# Palabras clave → nombre de categoría (debe coincidir con Categoria.nombre en DB)
KEYWORDS: dict[str, list[str]] = {
    "Supermercado": ["mercadona", "lidl", "carrefour", "aldi", "consum", "supermercado", "compra", "family"],
    "Restaurantes": ["restaurante", "bar", "fanta", "bravas", "buffalo", "terra", "ibérica", "almuerzo", "cena"],
    "Ocio": ["cine", "teatro", "billar", "ocio"],
    "Padel / Deporte": ["pádel", "padel", "pcv", "climb", "deporte"],
    "Gasolina / Transporte": ["gasolina", "gasolinera", "bus", "metro", "taxi", "uber", "parking"],
    "Suplementos": ["creatina", "proteína", "suplemento"],
    "Gimnasio": ["gym", "gimnasio"],
    "Viajes": ["viaje", "vuelo", "hotel", "cumple"],
}


def inferir_categoria(descripcion: str) -> Optional[str]:
    desc_lower = descripcion.lower()
    for categoria, keywords in KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return categoria
    return None


def parsear_gasto(texto: str) -> Optional[GastoParsed]:
    texto = texto.strip()
    m = PATTERN.match(texto)
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

    return GastoParsed(
        descripcion=desc,
        cantidad=float(amt),
        categoria_hint=inferir_categoria(desc),
    )
