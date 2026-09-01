"""IP 数据访问层。"""
import json
from typing import Any, Dict, List, Optional

from .database import Database


def row_to_ip(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name_cn": row["name_cn"],
        "name_jp": row["name_jp"],
        "aliases": json.loads(row["aliases"] or "[]"),
        "heat_score": row["heat_score"],
        "heat_rank": row["heat_rank"],
        "source_weights": json.loads(row["source_weights"] or "{}"),
        "search_keywords": json.loads(row["search_keywords"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "manual_override": bool(row["manual_override"]),
    }


def list_all_ips(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    db = Database()
    sql = "SELECT * FROM ips ORDER BY heat_rank ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = db.fetch_all(sql)
    return [row_to_ip(r) for r in rows]


def get_ip(ip_id: int) -> Optional[Dict[str, Any]]:
    db = Database()
    row = db.fetch_one("SELECT * FROM ips WHERE id = ?", (ip_id,))
    return row_to_ip(row) if row else None


def get_ip_by_name(name: str) -> Optional[Dict[str, Any]]:
    """按中文名/日文名/别名模糊匹配，取第一个。"""
    db = Database()
    row = db.fetch_one(
        "SELECT * FROM ips WHERE name_cn = ? OR name_jp = ? LIMIT 1",
        (name, name),
    )
    if row:
        return row_to_ip(row)
    # 别名匹配
    rows = db.fetch_all("SELECT * FROM ips")
    for r in rows:
        aliases = json.loads(r["aliases"] or "[]")
        if name in aliases:
            return row_to_ip(r)
    return None


def insert_ip(
    name_cn: str,
    name_jp: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    heat_score: float = 0.0,
    heat_rank: int = 9999,
    search_keywords: Optional[List[str]] = None,
) -> int:
    db = Database()
    return db.execute(
        """INSERT INTO ips (name_cn, name_jp, aliases, heat_score, heat_rank, search_keywords)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            name_cn,
            name_jp,
            json.dumps(aliases or [], ensure_ascii=False),
            heat_score,
            heat_rank,
            json.dumps(search_keywords or [], ensure_ascii=False),
        ),
    )
