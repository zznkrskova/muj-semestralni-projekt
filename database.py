import sqlite3
from datetime import datetime

DB_NAME = "planner.db"


def _safe_add_column(cursor, table, column_def):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
    except sqlite3.OperationalError:
        pass  # Sloupec už existuje


def get_connection():
    return sqlite3.connect(DB_NAME)


def _weekday_code(date_str):
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][datetime.fromisoformat(date_str).weekday()]


def _month_day(date_str):
    d = datetime.fromisoformat(date_str)
    return f"{d.month:02d}-{d.day:02d}"


def _fetch_one(query, params=()):
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, params)
    row = c.fetchone()
    conn.close()
    return row


def _fetch_all(query, params=()):
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


def _execute(query, params=()):
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()


def create_tables():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        start_hour INTEGER,
        start_minute INTEGER,
        end_hour INTEGER,
        end_minute INTEGER,
        difficulty INTEGER,
        date TEXT,
        recurring INTEGER,
        recurring_days TEXT,
        recurring_date TEXT,
        all_day INTEGER DEFAULT 0,
        load_type TEXT DEFAULT 'mental',
        is_rest INTEGER DEFAULT 0,
        rest_type TEXT DEFAULT NULL,
        rest_amount INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS activity_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT,
        start_hour INTEGER,
        start_minute INTEGER,
        end_hour INTEGER,
        end_minute INTEGER,
        difficulty INTEGER,
        all_day INTEGER DEFAULT 0,
        load_type TEXT DEFAULT 'mental',
        is_rest INTEGER DEFAULT 0,
        rest_type TEXT DEFAULT NULL,
        rest_amount INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS flags (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)


    c.execute("""
    CREATE TABLE IF NOT EXISTS activity_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        note_text TEXT,
        UNIQUE(activity_id, date)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS activity_exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recurring_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        UNIQUE(recurring_id, date)
    )
    """)

    # Přidej sloupce pro odpočinek pokud neexistují (pro starší databáze)
    _safe_add_column(c, "activities", "is_rest INTEGER DEFAULT 0")
    _safe_add_column(c, "activities", "rest_type TEXT DEFAULT NULL")
    _safe_add_column(c, "activities", "rest_amount INTEGER DEFAULT 0")
    _safe_add_column(c, "activity_templates", "is_rest INTEGER DEFAULT 0")
    _safe_add_column(c, "activity_templates", "rest_type TEXT DEFAULT NULL")
    _safe_add_column(c, "activity_templates", "rest_amount INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def add_activity(name, category, sh, sm, eh, em, difficulty,
                 date=None, recurring=0, recurring_days=None, recurring_date=None, all_day=0, load_type='mental', is_rest=0, rest_type=None, rest_amount=0):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO activities
    (name, category, start_hour, start_minute, end_hour, end_minute,
     difficulty, date, recurring, recurring_days, recurring_date, all_day, load_type, is_rest, rest_type, rest_amount)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, category, sh, sm, eh, em, difficulty,
          date, recurring, recurring_days, recurring_date, all_day, load_type, is_rest, rest_type, rest_amount))
    conn.commit()
    conn.close()


def delete_activity(activity_id):
    _execute("DELETE FROM activities WHERE id = ?", (activity_id,))


def get_all_activities():
    return _fetch_all("SELECT * FROM activities")


def get_activity_by_id(activity_id):
    return _fetch_one("SELECT * FROM activities WHERE id = ?", (activity_id,))


def update_activity(activity_id, name, category, sh, sm, eh, em, difficulty,
                    date=None, recurring=0, recurring_days=None, recurring_date=None, all_day=0, load_type='mental', is_rest=0, rest_type=None, rest_amount=0):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    UPDATE activities
    SET name = ?, category = ?, start_hour = ?, start_minute = ?,
        end_hour = ?, end_minute = ?, difficulty = ?, date = ?,
        recurring = ?, recurring_days = ?, recurring_date = ?, all_day = ?, load_type = ?, is_rest = ?, rest_type = ?, rest_amount = ?
    WHERE id = ?
    """, (name, category, sh, sm, eh, em, difficulty,
          date, recurring, recurring_days, recurring_date, all_day, load_type, is_rest, rest_type, rest_amount, activity_id))
    conn.commit()
    conn.close()


def add_template(name, category, sh, sm, eh, em, difficulty, all_day=0, load_type='mental', is_rest=0, rest_type=None, rest_amount=0):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO activity_templates
    (name, category, start_hour, start_minute, end_hour, end_minute, difficulty, all_day, load_type, is_rest, rest_type, rest_amount)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, category, sh, sm, eh, em, difficulty, all_day, load_type, is_rest, rest_type, rest_amount))
    conn.commit()
    conn.close()


def get_all_templates():
    return _fetch_all("SELECT * FROM activity_templates")


def delete_template(template_id):
    _execute("DELETE FROM activity_templates WHERE id = ?", (template_id,))


def delete_template_and_activities(template_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM activity_templates WHERE id = ?", (template_id,))
    template = c.fetchone()
    if not template:
        conn.close()
        return

    (_, name, category, sh, sm, eh, em, difficulty, all_day,
     load_type, is_rest, rest_type, rest_amount) = template

    c.execute("""
    DELETE FROM activities
    WHERE name = ?
      AND (category = ? OR (category IS NULL AND ? IS NULL))
      AND start_hour = ?
      AND start_minute = ?
      AND end_hour = ?
      AND end_minute = ?
      AND (difficulty = ? OR (difficulty IS NULL AND ? IS NULL))
      AND (all_day = ? OR (all_day IS NULL AND ? IS NULL))
      AND (load_type = ? OR (load_type IS NULL AND ? IS NULL))
      AND (is_rest = ? OR (is_rest IS NULL AND ? IS NULL))
      AND (rest_type = ? OR (rest_type IS NULL AND ? IS NULL))
      AND (rest_amount = ? OR (rest_amount IS NULL AND ? IS NULL))
    """, (
        name, category, category,
        sh, sm, eh, em,
        difficulty, difficulty,
        all_day, all_day,
        load_type, load_type,
        is_rest, is_rest,
        rest_type, rest_type,
        rest_amount, rest_amount
    ))

    c.execute("DELETE FROM activity_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


def get_flag(key, default=None):
    row = _fetch_one("SELECT value FROM flags WHERE key = ?", (key,))
    return row[0] if row else default


def set_flag(key, value):
    _execute("INSERT OR REPLACE INTO flags (key, value) VALUES (?, ?)", (key, value))




def is_first_run():
    return get_flag("initialized") != "1"


def mark_initialized():
    set_flag("initialized", "1")


def get_template_by_name(name):
    row = _fetch_one("SELECT * FROM activity_templates WHERE name = ?", (name,))
    return row


def get_activity_note(activity_id, date):
    """Získá poznámku pro aktivitu na konkrétní den"""
    row = _fetch_one(
        "SELECT note_text FROM activity_notes WHERE activity_id = ? AND date = ?",
        (activity_id, date)
    )
    return row[0] if row else None


def add_or_update_activity_note(activity_id, date, note_text):
    """Přidá nebo upraví poznámku pro aktivitu na konkrétní den"""
    _execute(
        """
        INSERT OR REPLACE INTO activity_notes (activity_id, date, note_text)
        VALUES (?, ?, ?)
        """,
        (activity_id, date, note_text)
    )


def delete_activity_note(activity_id, date):
    """Smaže poznámku pro aktivitu na konkrétní den"""
    _execute("DELETE FROM activity_notes WHERE activity_id = ? AND date = ?", (activity_id, date))


def add_activity_exception(recurring_id, date):
    """Přidá výjimku (skrytí) pro dlouhodobou aktivitu v konkrétní den"""
    _execute(
        """
        INSERT OR IGNORE INTO activity_exceptions (recurring_id, date)
        VALUES (?, ?)
        """,
        (recurring_id, date)
    )


def delete_activity_exception(recurring_id, date):
    """Smaže výjimku pro dlouhodobou aktivitu v konkrétní den"""
    _execute("DELETE FROM activity_exceptions WHERE recurring_id = ? AND date = ?", (recurring_id, date))


def has_activity_exception(recurring_id, date):
    """Zjistí, zda má dlouhodobá aktivita výjimku v daný den"""
    row = _fetch_one("SELECT 1 FROM activity_exceptions WHERE recurring_id = ? AND date = ?", (recurring_id, date))
    return row is not None


def activity_applies_to_day(activity_id, date_str):
    weekday = _weekday_code(date_str)
    month_day = _month_day(date_str)
    row = _fetch_one(
        """
        SELECT 1
        FROM activities
        WHERE id = ?
          AND (
                date = ?
             OR (
                  recurring = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM activity_exceptions e
                      WHERE e.recurring_id = activities.id AND e.date = ?
                  )
                  AND (
                        (recurring_days IS NOT NULL AND recurring_days != '' AND instr(recurring_days, ?) > 0)
                     OR (recurring_date IS NOT NULL AND recurring_date != '' AND recurring_date = ?)
                  )
             )
          )
        """,
        (activity_id, date_str, date_str, weekday, month_day)
    )
    return row is not None


def get_activities_for_day(date_str):
    weekday = _weekday_code(date_str)
    month_day = _month_day(date_str)
    return _fetch_all(
        """
        SELECT *
        FROM activities
        WHERE date = ?
           OR (
                recurring = 1
                AND NOT EXISTS (
                    SELECT 1
                    FROM activity_exceptions e
                    WHERE e.recurring_id = activities.id AND e.date = ?
                )
                AND (
                      (recurring_days IS NOT NULL AND recurring_days != '' AND instr(recurring_days, ?) > 0)
                   OR (recurring_date IS NOT NULL AND recurring_date != '' AND recurring_date = ?)
                )
           )
        """,
        (date_str, date_str, weekday, month_day)
    )


def get_conflicting_activities(date_str, sh, sm, eh, em):
    new_start = sh * 60 + sm
    new_end = eh * 60 + em
    weekday = _weekday_code(date_str)
    month_day = _month_day(date_str)
    return _fetch_all(
        """
        SELECT *
        FROM activities
        WHERE (
                date = ?
             OR (
                  recurring = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM activity_exceptions e
                      WHERE e.recurring_id = activities.id AND e.date = ?
                  )
                  AND (
                        (recurring_days IS NOT NULL AND recurring_days != '' AND instr(recurring_days, ?) > 0)
                     OR (recurring_date IS NOT NULL AND recurring_date != '' AND recurring_date = ?)
                  )
             )
        )
          AND (start_hour * 60 + start_minute) < ?
          AND (end_hour * 60 + end_minute) > ?
        """,
        (date_str, date_str, weekday, month_day, new_end, new_start)
    )
