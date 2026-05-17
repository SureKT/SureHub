from datetime import datetime, timezone
import xlrd
from sqlmodel import Session
from app.modules.finanzas.service import listar_categorias

SKIP_CATEGORIES = {
    "Movimientos excluidos",
    "Nómina y otras prestaciones",
    "Otros ingresos",
    "Nómina y otras prestaciones",  # encoding variant
}

ING_CAT_MAP = {
    "Alimentación": ["alimenta", "mercadona", "consum", "supermercado", "lidl", "aldi", "carrefour", "dia", "eroski", "bm ", "ahorramas"],
    "Compras": ["amazon", "zara", "primark", "mango", "h&m", "ikea", "mediamark", "pccomponentes"],
    "Educación y salud": ["farmacia", "medico", "médico", "dentista", "clinica", "clínica", "decathlon", "padel", "pádel", "gimnasio", "sport"],
    "Hogar": ["vodafone", "movistar", "orange", "masmovil", "netflix", "spotify", "amazon prime", "luz ", "gas ", "agua", "comunidad"],
    "Ocio y viajes": ["restaurante", "bar ", "cafeteria", "cafetería", "hotel", "airbnb", "vueling", "ryanair", "renfe"],
    "Otros gastos": [],
    "Vehículo y transporte": ["gasolina", "parking", "peaje", "repsol", "cepsa", "bp ", "metro", "emt ", "movilidad", "cabify", "uber"],
}


def _excel_serial_to_datetime(serial: float) -> datetime:
    tup = xlrd.xldate_as_tuple(serial, 0)
    return datetime(tup[0], tup[1], tup[2], tzinfo=timezone.utc)


def _guess_categoria_id(session: Session, ing_cat: str, descripcion: str) -> int | None:
    cats = listar_categorias(session)
    desc_lower = descripcion.lower()

    # Direct name match in description
    for cat in cats:
        if cat.nombre.lower() in desc_lower:
            return cat.id

    # ING category keyword hints
    keywords = ING_CAT_MAP.get(ing_cat, [])
    for kw in keywords:
        if kw in desc_lower:
            for cat in cats:
                cat_lower = cat.nombre.lower()
                if any(k in cat_lower for k in ["alimenta", "mercado", "super"]) and ing_cat == "Alimentación":
                    return cat.id
                if any(k in cat_lower for k in ["salud", "farmacia", "médico", "medico"]) and ing_cat == "Educación y salud":
                    return cat.id
                if any(k in cat_lower for k in ["hogar", "casa", "suministro"]) and ing_cat == "Hogar":
                    return cat.id
                if any(k in cat_lower for k in ["ocio", "restaur", "viaje"]) and ing_cat == "Ocio y viajes":
                    return cat.id
                if any(k in cat_lower for k in ["transport", "coche", "gasolina"]) and ing_cat == "Vehículo y transporte":
                    return cat.id

    return None


def parse_ing_xls(file_bytes: bytes, session: Session) -> list[dict]:
    wb = xlrd.open_workbook(file_contents=file_bytes)
    ws = wb.sheet_by_index(0)

    result = []
    for i in range(4, ws.nrows):
        ing_cat = ws.cell_value(i, 1)
        descripcion = str(ws.cell_value(i, 3)).strip()
        importe = ws.cell_value(i, 5)
        fecha_serial = ws.cell_value(i, 0)

        if not isinstance(fecha_serial, float) or fecha_serial == 0:
            continue
        if importe >= 0:
            continue
        if ing_cat in SKIP_CATEGORIES:
            continue

        fecha = _excel_serial_to_datetime(fecha_serial)
        categoria_id = _guess_categoria_id(session, ing_cat, descripcion)

        result.append({
            "fecha": fecha.isoformat(),
            "descripcion": descripcion,
            "cantidad": round(abs(importe), 2),
            "categoria_id": categoria_id,
            "ing_categoria": ing_cat,
        })

    return result
