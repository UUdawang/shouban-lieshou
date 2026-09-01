"""角色分级数据访问层。"""
import json
from typing import Any, Dict, List, Optional

from .database import Database


def row_to_char(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "ip_id": row["ip_id"],
        "name_cn": row["name_cn"],
        "name_jp": row["name_jp"],
        "aliases": json.loads(row["aliases"] or "[]"),
        "grade": row["grade"],
        "price_factor": row["price_factor"],
        "heat_score": row["heat_score"],
        "manual_override": bool(row["manual_override"]),
    }


def list_characters_by_ip(ip_id: int) -> List[Dict[str, Any]]:
    db = Database()
    rows = db.fetch_all(
        "SELECT * FROM characters WHERE ip_id = ? ORDER BY price_factor DESC",
        (ip_id,),
    )
    return [row_to_char(r) for r in rows]


def get_avg_price_factor_by_ip(ip_id: int) -> float:
    """IP内角色的加权平均price_factor，打包无法识别角色时使用。"""
    db = Database()
    row = db.fetch_one(
        "SELECT AVG(price_factor) AS avg_f FROM characters WHERE ip_id = ?",
        (ip_id,),
    )
    if row and row["avg_f"] is not None:
        return float(row["avg_f"])
    return 0.753  # 配置中的默认值


def insert_character(
    ip_id: int,
    name_cn: str,
    name_jp: Optional[str] = None,
    grade: str = "C",
    price_factor: Optional[float] = None,
    heat_score: float = 0.0,
) -> int:
    if price_factor is None:
        pf = {"S": 1.2, "A": 1.0, "B": 0.7, "C": 0.4}[grade]
    else:
        pf = price_factor
    db = Database()
    return db.execute(
        """INSERT INTO characters (ip_id, name_cn, name_jp, grade, price_factor, heat_score)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ip_id, name_cn, name_jp, grade, pf, heat_score),
    )
