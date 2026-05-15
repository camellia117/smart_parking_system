"""SQLite 轻量迁移：为已有库追加列。"""
from sqlalchemy import inspect, text


def ensure_sqlite_schema(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    names = set(insp.get_table_names())

    with engine.begin() as conn:

        def pragma_cols(table: str):
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return {r[1] for r in rows}

        if "parking_records" in names:
            cols = pragma_cols("parking_records")
            if "entry_gate" not in cols:
                conn.execute(text("ALTER TABLE parking_records ADD COLUMN entry_gate VARCHAR"))
            if "exit_gate" not in cols:
                conn.execute(text("ALTER TABLE parking_records ADD COLUMN exit_gate VARCHAR"))
