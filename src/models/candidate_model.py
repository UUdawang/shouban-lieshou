"""候选商品数据访问层（扫描达标入库）。"""
from typing import Any, Dict, List

from .database import Database


def row_to_candidate(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "item_url": row["item_url"],
        "title": row["title"],
        "ip_id": row["ip_id"],
        "is_lot": bool(row["is_lot"]),
        "item_count": row["item_count"],
        "price_jpy": row["price_jpy"],
        "price_cny_proxy": row["price_cny_proxy"],
        "estimated_p": row["estimated_p"],
        "intl_shipping": row["intl_shipping"],
        "tariff": row["tariff"],
        "total_cost": row["total_cost"],
        "xian_fee": row["xian_fee"],
        "pack_fee": row["pack_fee"],
        "net_profit": row["net_profit"],
        "profit_rate": row["profit_rate"],
        "pass_threshold": bool(row["pass_threshold"]),
        "matched_ip": row["matched_ip"],
        "snapshot_at": row["snapshot_at"],
    }


def insert_candidate(item: Dict[str, Any]) -> int:
    db = Database()
    return db.execute(
        """
        INSERT INTO candidate_items
            (source, item_url, title, ip_id, is_lot, item_count,
             price_jpy, price_cny_proxy, estimated_p, intl_shipping,
             tariff, total_cost, xian_fee, pack_fee,
             net_profit, profit_rate, pass_threshold, matched_ip)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            item.get("source", "unknown"),
            item.get("item_url"),
            item.get("title", ""),
            item.get("ip_id"),
            1 if item.get("is_lot") else 0,
            item.get("item_count", 1),
            item.get("price_jpy", 0),
            item.get("price_cny_proxy", 0),
            item.get("estimated_p", 0),
            item.get("intl_shipping", 0),
            item.get("tariff", 0),
            item.get("total_cost", 0),
            item.get("xian_fee", 0),
            item.get("pack_fee", 0),
            item.get("net_profit", 0),
            item.get("profit_rate", 0),
            1 if item.get("pass_threshold") else 0,
            item.get("matched_ip"),
        ),
    )


def list_candidates(limit: int = 100, passed_only: bool = True) -> List[Dict[str, Any]]:
    db = Database()
    sql = "SELECT * FROM candidate_items"
    if passed_only:
        sql += " WHERE pass_threshold = 1"
    sql += " ORDER BY snapshot_at DESC LIMIT ?"
    rows = db.fetch_all(sql, (limit,))
    return [row_to_candidate(r) for r in rows]
