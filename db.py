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

CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS personality_traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_interests (
    user_id INTEGER NOT NULL REFERENCES users(id),
    interest_id INTEGER NOT NULL REFERENCES interests(id),
    PRIMARY KEY (user_id, interest_id)
);

CREATE TABLE IF NOT EXISTS user_traits (
    user_id INTEGER NOT NULL REFERENCES users(id),
    trait_id INTEGER NOT NULL REFERENCES personality_traits(id),
    PRIMARY KEY (user_id, trait_id)
);

CREATE TABLE IF NOT EXISTS personality_scores (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    openness REAL NOT NULL,
    conscientiousness REAL NOT NULL,
    extraversion REAL NOT NULL,
    agreeableness REAL NOT NULL,
    stability REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS music_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_music_styles (
    user_id INTEGER NOT NULL REFERENCES users(id),
    music_style_id INTEGER NOT NULL REFERENCES music_styles(id),
    PRIMARY KEY (user_id, music_style_id)
);
"""

MUSIC_STYLES = [
    "New wave", "Electronica", "Pop", "Rock", "Reggaeton", "Indie",
    "Jazz", "Salsa", "Cumbia", "Hip hop / Rap", "House / Techno",
    "Balada", "Folclore", "Metal", "Funk / Soul", "Musica clasica",
]

PERSONALITY_DIMENSIONS = [
    "openness", "conscientiousness", "extraversion", "agreeableness", "stability",
]

PERSONALITY_QUESTIONS = [
    {"id": "q1", "dimension": "openness", "reverse": False,
     "text": "Me gusta explorar ideas, lugares o experiencias nuevas."},
    {"id": "q2", "dimension": "openness", "reverse": True,
     "text": "Prefiero quedarme con rutinas conocidas antes que probar algo distinto."},
    {"id": "q3", "dimension": "conscientiousness", "reverse": False,
     "text": "Suelo planificar las cosas con anticipacion."},
    {"id": "q4", "dimension": "conscientiousness", "reverse": True,
     "text": "Se me hace dificil mantener el orden en mis tareas."},
    {"id": "q5", "dimension": "extraversion", "reverse": False,
     "text": "Me energizo estando rodeado de gente."},
    {"id": "q6", "dimension": "extraversion", "reverse": True,
     "text": "Prefiero pasar tiempo a solas antes que en grupos grandes."},
    {"id": "q7", "dimension": "agreeableness", "reverse": False,
     "text": "Me resulta facil confiar en los demas."},
    {"id": "q8", "dimension": "agreeableness", "reverse": True,
     "text": "Suelo anteponer mis intereses antes que los de otros."},
    {"id": "q9", "dimension": "stability", "reverse": False,
     "text": "Mantengo la calma incluso en situaciones estresantes."},
    {"id": "q10", "dimension": "stability", "reverse": True,
     "text": "Me preocupo con facilidad por pequenos detalles."},
]

INTERESTS = [
    "Senderismo y naturaleza", "Cocina y gastronomia", "Cine y series",
    "Musica en vivo", "Viajar", "Lectura", "Deportes", "Arte y diseno",
    "Tecnologia", "Baile", "Yoga y meditacion", "Mascotas", "Fotografia",
    "Vino y cocteleria", "Juegos de mesa",
]

PERSONALITY_TRAITS = [
    "Extrovertido/a", "Introvertido/a", "Aventurero/a", "Tranquilo/a",
    "Creativo/a", "Organizado/a", "Espontaneo/a", "Detallista",
    "Optimista", "Analitico/a", "Sensible", "Independiente",
]

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


def _add_column_if_missing(conn, table, column, coltype):
    existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)

    _add_column_if_missing(conn, "users", "birth_date", "TEXT")
    _add_column_if_missing(conn, "users", "age_pref_min", "INTEGER")
    _add_column_if_missing(conn, "users", "age_pref_max", "INTEGER")
    conn.commit()

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

    interest_count = conn.execute("SELECT COUNT(*) AS c FROM interests").fetchone()["c"]
    if interest_count == 0:
        conn.executemany("INSERT INTO interests (name) VALUES (?)", [(i,) for i in INTERESTS])
        conn.commit()

    trait_count = conn.execute("SELECT COUNT(*) AS c FROM personality_traits").fetchone()["c"]
    if trait_count == 0:
        conn.executemany(
            "INSERT INTO personality_traits (name) VALUES (?)",
            [(t,) for t in PERSONALITY_TRAITS],
        )
        conn.commit()

    music_count = conn.execute("SELECT COUNT(*) AS c FROM music_styles").fetchone()["c"]
    if music_count == 0:
        conn.executemany("INSERT INTO music_styles (name) VALUES (?)", [(m,) for m in MUSIC_STYLES])
        conn.commit()

    conn.close()
