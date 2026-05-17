import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GastoParsed:
    descripcion: str
    cantidad: float
    categoria: Optional[str] = None


# Patrones: "café 2.50", "2.50 café", "café 2,50€"
PATTERN = re.compile(
    r'^(?P<desc1>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s]+?)\s+(?P<amt1>\d+[.,]\d{1,2})[€$]?$'
    r'|^(?P<amt2>\d+[.,]\d{1,2})[€$]?\s+(?P<desc2>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s]+)$'
    r'|^(?P<desc3>[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s]+?)\s+(?P<amt3>\d+)[€$]?$'
)

CATEGORIAS = {
    "comida": ["café", "cafeteria", "restaurante", "bar", "menu", "almuerzo", "cena", "desayuno", "pizza", "burger"],
    "transporte": ["gasolina", "gasolinera", "bus", "metro", "taxi", "uber", "parking", "tren"],
    "supermercado": ["mercadona", "lidl", "carrefour", "aldi", "supermercado", "compra"],
    "ocio": ["cine", "teatro", "concierto", "netflix", "spotify", "juego"],
    "salud": ["farmacia", "medico", "dentista", "gym", "gimnasio"],
}


def inferir_categoria(descripcion: str) -> Optional[str]:
    desc_lower = descripcion.lower()
    for categoria, keywords in CATEGORIAS.items():
        if any(kw in desc_lower for kw in keywords):
            return categoria
    return None


def parsear_gasto(texto: str) -> Optional[GastoParsed]:
    texto = texto.strip()
    m = PATTERN.match(texto)
    if not m:
        return None

    if m.group("desc1"):
        desc = m.group("desc1").strip()
        amt = m.group("amt1").replace(",", ".")
    elif m.group("desc2"):
        desc = m.group("desc2").strip()
        amt = m.group("amt2").replace(",", ".")
    else:
        desc = m.group("desc3").strip()
        amt = m.group("amt3")

    return GastoParsed(
        descripcion=desc,
        cantidad=float(amt),
        categoria=inferir_categoria(desc),
    )
