import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).parent / "healthyrecord.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    description TEXT NOT NULL,
    activities TEXT NOT NULL,
    emoji TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    date_start TEXT NOT NULL,
    date_end TEXT NOT NULL,
    description TEXT NOT NULL,
    price_clp INTEGER NOT NULL,
    capacity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS event_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(event_id, user_id)
);
"""

LOCATIONS = [
    ("Refugio Cajon del Maipo", "Cajon del Maipo, a 1h de Santiago",
     "Cabanas de montana junto al rio, rodeadas de cordillera. Ideal para desconectarse y conocer gente en un ambiente relajado.",
     "Caminata, fogata nocturna, sesion de asado, juegos de integracion", "🏔️"),
    ("Termas de Colina", "Colina, a 40 min de Santiago",
     "Piscinas termales al aire libre con vista a la cordillera, perfectas para el invierno.",
     "Baños termales, sauna, cena grupal, ronda de preguntas para conocerse", "♨️"),
    ("Centro de Ski Farellones", "Farellones, a 1h de Santiago",
     "Fin de semana en la nieve para quienes buscan aventura y adrenalina en compania.",
     "Clases de ski/snowboard, chocolate caliente, noche de juegos en el refugio", "⛷️"),
    ("Valle de Pomaire", "Pomaire, a 1h de Santiago",
     "Pueblo tradicional rodeado de campo, ideal para un plan mas tranquilo y cultural.",
     "Taller de ceramica en pareja, degustacion de vinos, cena campestre", "🍷"),
]

EVENTS = [
    ("Escapada de Invierno: Montana y Fogata", 1, "2026-08-22", "2026-08-23",
     "Un fin de semana en la montana con actividades de integracion pensadas para romper el hielo desde el primer momento: caminata guiada, juegos grupales y una fogata nocturna para cerrar el dia conversando.",
     89990, 24),
    ("Relax Termal para Solteros", 2, "2026-08-29", "2026-08-29",
     "Dia completo en piscinas termales con dinamicas de integracion suaves, cena grupal y buena musica. Ideal si prefieres un plan de un solo dia.",
     54990, 30),
    ("Aventura en la Nieve", 3, "2026-09-05", "2026-09-06",
     "Clases de ski/snowboard para todo nivel, chocolate caliente y noche de juegos de mesa en el refugio. Perfecto para los mas aventureros.",
     129990, 20),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    count = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()["c"]
    if count == 0:
        conn.executemany(
            "INSERT INTO locations (name, area, description, activities, emoji) VALUES (?,?,?,?,?)",
            LOCATIONS,
        )
        conn.executemany(
            "INSERT INTO events (title, location_id, date_start, date_end, description, price_clp, capacity) VALUES (?,?,?,?,?,?,?)",
            EVENTS,
        )
        conn.commit()
    conn.close()
