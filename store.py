from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "scheduler.db"))

DEFAULT_GROUPS = [
    "electronics",
    "liquor",
    "candy",
    "snacks",
    "household",
    "beauty",
]

DEFAULT_STORES = [
    "台北信義店",
    "板橋大遠百店",
    "中壢旗艦店",
    "台中公益店",
]

DEFAULT_BRANDS = [
    "Sony",
    "Asahi",
    "KitKat",
    "Lay's",
    "Dyson",
    "Shiseido",
]

DEFAULT_EMPLOYEES = [
    {
        "name": "Amy",
        "groups": "electronics,liquor",
        "available_days": "Mon,Tue,Wed,Thu,Fri,Sat",
        "available_slots": "AM,PM",
        "weekly_max_shifts": 5,
        "priority": 3,
        "notes": "資深熟手",
    },
    {
        "name": "Ben",
        "groups": "snacks,candy",
        "available_days": "Tue,Wed,Thu,Fri,Sat,Sun",
        "available_slots": "AM,PM",
        "weekly_max_shifts": 5,
        "priority": 2,
        "notes": "",
    },
    {
        "name": "Cara",
        "groups": "liquor",
        "available_days": "Fri,Sat,Sun",
        "available_slots": "PM",
        "weekly_max_shifts": 3,
        "priority": 4,
        "notes": "酒類表現佳",
    },
    {
        "name": "David",
        "groups": "electronics,household",
        "available_days": "Mon,Tue,Wed,Thu,Fri",
        "available_slots": "AM",
        "weekly_max_shifts": 5,
        "priority": 2,
        "notes": "",
    },
    {
        "name": "Ella",
        "groups": "snacks,candy,electronics,beauty",
        "available_days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
        "available_slots": "AM,PM",
        "weekly_max_shifts": 6,
        "priority": 5,
        "notes": "可跨類別支援",
    },
]

DEFAULT_EVENTS = [
    {
        "date": "2026-04-14",
        "slot": "AM",
        "store": "台北信義店",
        "brand": "Sony",
        "category": "electronics",
        "required_staff": 2,
        "preferred_group": "electronics",
        "notes": "",
    },
    {
        "date": "2026-04-14",
        "slot": "PM",
        "store": "板橋大遠百店",
        "brand": "Asahi",
        "category": "liquor",
        "required_staff": 1,
        "preferred_group": "liquor",
        "notes": "",
    },
    {
        "date": "2026-04-15",
        "slot": "AM",
        "store": "中壢旗艦店",
        "brand": "Lay's",
        "category": "snacks",
        "required_staff": 2,
        "preferred_group": "snacks",
        "notes": "",
    },
]

DEFAULT_LEAVES = [
    {"employee_name": "Ella", "date": "2026-04-15", "slot": "PM", "reason": "預先請假"},
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            groups_text TEXT NOT NULL,
            available_days TEXT NOT NULL,
            available_slots TEXT NOT NULL,
            weekly_max_shifts INTEGER NOT NULL DEFAULT 5,
            priority INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            slot TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            slot TEXT NOT NULL,
            store TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            required_staff INTEGER NOT NULL DEFAULT 1,
            preferred_group TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


def seed_defaults(force: bool = False) -> None:
    init_db()
    conn = connect()
    cur = conn.cursor()

    employee_count = cur.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    event_count = cur.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    leave_count = cur.execute("SELECT COUNT(*) FROM leaves").fetchone()[0]

    if force:
        cur.execute("DELETE FROM leaves")
        cur.execute("DELETE FROM events")
        cur.execute("DELETE FROM employees")
        conn.commit()
        employee_count = event_count = leave_count = 0

    if employee_count == 0:
        for row in DEFAULT_EMPLOYEES:
            cur.execute(
                """
                INSERT INTO employees
                (name, groups_text, available_days, available_slots, weekly_max_shifts, priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    row["groups"],
                    row["available_days"],
                    row["available_slots"],
                    row["weekly_max_shifts"],
                    row["priority"],
                    row["notes"],
                ),
            )

    if event_count == 0:
        for row in DEFAULT_EVENTS:
            cur.execute(
                """
                INSERT INTO events
                (date, slot, store, brand, category, required_staff, preferred_group, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["date"],
                    row["slot"],
                    row["store"],
                    row["brand"],
                    row["category"],
                    row["required_staff"],
                    row["preferred_group"],
                    row["notes"],
                ),
            )

    if leave_count == 0:
        for row in DEFAULT_LEAVES:
            employee = cur.execute("SELECT id FROM employees WHERE name = ?", (row["employee_name"],)).fetchone()
            if employee:
                cur.execute(
                    """
                    INSERT INTO leaves (employee_id, date, slot, reason)
                    VALUES (?, ?, ?, ?)
                    """,
                    (employee["id"], row["date"], row["slot"], row["reason"]),
                )

    conn.commit()
    conn.close()


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = connect()
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    conn = connect()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid
