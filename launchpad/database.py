import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from launchpad.config import APP_DATA_DIR, DB_PATH, DEFAULT_CATEGORY, DEFAULT_GLOW_COLOR
from launchpad.ui.colors import normalize_color


@dataclass
class Card:
    id: int
    name: str
    card_type: str
    host: str
    port: int | None
    username: str
    encrypted_password: str
    encrypted_key: str
    url: str
    icon: str
    category: str
    sort_order: int
    glow_color: str
    key_file_path: str


class Database:
    def __init__(self, path=DB_PATH) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    card_type TEXT NOT NULL,
                    host TEXT NOT NULL DEFAULT '',
                    port INTEGER,
                    username TEXT DEFAULT '',
                    encrypted_password TEXT DEFAULT '',
                    encrypted_key TEXT DEFAULT '',
                    url TEXT DEFAULT '',
                    icon TEXT DEFAULT 'default',
                    category TEXT DEFAULT 'General',
                    sort_order INTEGER DEFAULT 0,
                    glow_color TEXT DEFAULT '#FF6B00',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            try:
                conn.execute("ALTER TABLE cards ADD COLUMN key_file_path TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def is_initialized(self) -> bool:
        return self.get_setting("initialized") == "true"

    def list_cards(self, category: str | None = None) -> list[Card]:
        query = "SELECT * FROM cards"
        params: tuple = ()
        if category and category != "All":
            query += " WHERE category = ?"
            params = (category,)
        query += " ORDER BY sort_order ASC, name ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_card(row) for row in rows]

    def list_categories(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM cards ORDER BY category ASC"
            ).fetchall()
        categories = [row["category"] for row in rows]
        return ["All", *categories] if categories else ["All"]

    def get_card(self, card_id: int) -> Card | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return self._row_to_card(row) if row else None

    def add_card(self, data: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cards (
                    name, card_type, host, port, username,
                    encrypted_password, encrypted_key, url,
                    icon, category, sort_order, glow_color, key_file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["card_type"],
                    data.get("host", ""),
                    data.get("port"),
                    data.get("username", ""),
                    data.get("encrypted_password", ""),
                    data.get("encrypted_key", ""),
                    data.get("url", ""),
                    data.get("icon", "default"),
                    data.get("category", DEFAULT_CATEGORY),
                    data.get("sort_order", 0),
                    data.get("glow_color", DEFAULT_GLOW_COLOR),
                    data.get("key_file_path", ""),
                ),
            )
            return int(cursor.lastrowid)

    def update_card(self, card_id: int, data: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE cards SET
                    name = ?, card_type = ?, host = ?, port = ?, username = ?,
                    encrypted_password = ?, encrypted_key = ?, url = ?,
                    icon = ?, category = ?, sort_order = ?, glow_color = ?,
                    key_file_path = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["card_type"],
                    data.get("host", ""),
                    data.get("port"),
                    data.get("username", ""),
                    data.get("encrypted_password", ""),
                    data.get("encrypted_key", ""),
                    data.get("url", ""),
                    data.get("icon", "default"),
                    data.get("category", DEFAULT_CATEGORY),
                    data.get("sort_order", 0),
                    data.get("glow_color", DEFAULT_GLOW_COLOR),
                    data.get("key_file_path", ""),
                    card_id,
                ),
            )

    def delete_card(self, card_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def update_sort_orders(self, ordered_ids: list[int]) -> None:
        with self._connect() as conn:
            for index, card_id in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE cards SET sort_order = ? WHERE id = ?",
                    (index, card_id),
                )

    def export_cards_raw(self) -> list[dict]:
        cards = self.list_cards()
        return [
            {
                "name": card.name,
                "card_type": card.card_type,
                "host": card.host,
                "port": card.port,
                "username": card.username,
                "encrypted_password": card.encrypted_password,
                "encrypted_key": card.encrypted_key,
                "url": card.url,
                "icon": card.icon,
                "category": card.category,
                "sort_order": card.sort_order,
                "glow_color": card.glow_color,
            }
            for card in cards
        ]

    def import_cards(self, cards: list[dict], mode: str = "merge") -> int:
        if mode == "replace":
            with self._connect() as conn:
                conn.execute("DELETE FROM cards")

        imported = 0
        for entry in cards:
            self.add_card(
                {
                    "name": entry.get("name", "Imported"),
                    "card_type": entry.get("card_type", "ssh"),
                    "host": entry.get("host", ""),
                    "port": entry.get("port"),
                    "username": entry.get("username", ""),
                    "encrypted_password": entry.get("encrypted_password", ""),
                    "encrypted_key": entry.get("encrypted_key", ""),
                    "url": entry.get("url", ""),
                    "icon": entry.get("icon", "default"),
                    "category": entry.get("category", DEFAULT_CATEGORY),
                    "sort_order": entry.get("sort_order", 0),
                    "glow_color": entry.get("glow_color", DEFAULT_GLOW_COLOR),
                }
            )
            imported += 1
        return imported

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> Card:
        return Card(
            id=row["id"],
            name=row["name"],
            card_type=row["card_type"],
            host=row["host"],
            port=row["port"],
            username=row["username"] or "",
            encrypted_password=row["encrypted_password"] or "",
            encrypted_key=row["encrypted_key"] or "",
            url=row["url"] or "",
            icon=row["icon"] or "default",
            category=row["category"] or DEFAULT_CATEGORY,
            sort_order=row["sort_order"] or 0,
            glow_color=normalize_color(row["glow_color"] or DEFAULT_GLOW_COLOR),
            key_file_path=(row["key_file_path"] if "key_file_path" in row.keys() else "") or "",
        )
