"""Seed a fresh database with a starter set of expense categories.

Idempotent: skips any category whose name already exists. Safe to re-run.

    python scripts/seed_categorias.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa
from app.database import create_db, get_session
from app.modules.finanzas.models import Category
from sqlmodel import select

# (name, type, monthly_estimate) — estimates are starting points; the app
# recalibrates them against real spending once there is history.
CATEGORIES = [
    ("Supermercado",         "variable", 200.0),
    ("Restaurantes",         "variable", 100.0),
    ("Ocio",                 "variable",  50.0),
    ("Deporte",              "variable",  40.0),
    ("Gasolina / Transporte", "variable",  70.0),
    ("Casa",                 "variable",  50.0),
    ("Salud",                "variable",  30.0),
    ("Viajes",               "variable",   0.0),
    ("Varios",               "variable",   0.0),
    ("Luz",                  "fixed",      60.0),
    ("Agua",                 "fixed",      15.0),
    ("Internet + Tlf",       "fixed",      30.0),
    ("Gimnasio",             "fixed",      25.0),
    ("Suscripciones",        "fixed",      15.0),
]

create_db()
session = next(get_session())

existing = {c.name.lower() for c in session.exec(select(Category)).all()}
inserted = 0

for name, type_, estimate in CATEGORIES:
    if name.lower() in existing:
        print(f"  skip (ya existe): {name}")
        continue
    session.add(Category(name=name, type=type_, monthly_estimate=estimate))
    print(f"  + {name} ({type_}, {estimate}€)")
    inserted += 1

session.commit()
print(f"\nListo. {inserted} categorías insertadas.")
