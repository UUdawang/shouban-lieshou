"""盯拍拍卖数据访问层。"""
from typing import Any, Dict, List, Optional

from .database import Database


def row_to_aw(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "auction_url": row["auction_url"],
        "title": row["title"],
        "ip_id": row["ip_id"],
        "is_lot": bool(row["is_lot"]),
        "item_count": row["item_count"],
        "estimated_p": row["estimated_p"],
        "current_jpy": row["current_jpy"],
        "bid_count": row["bid_count"],
        "end_time": row["end_time"],
        "status": row["status"],
        "max_bid_jpy": row["max_bid_jpy"],
        "my_bid_jpy": row["my_bid_jpy"],
        "last_checked": row["last_checked"],
        "notify_level": row["notify_level"],
        "note": row["note"],
    }


def insert_auction_watch(item: Dict[str, Any]) -> int:
    db = Database()
    return db.execute(
        """
        INSERT INTO auction_watches
            (source, auction_url, title, ip_id, is_lot, item_count,
             estimated_p, current_jpy, bid_count, end_time,
             status, max_bid_jpy, my_bid_jpy, notify_level, note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(auction_url) DO NOTHING
        """,
        (
            item.get("source", "wamei"),
            item.get("auction_url"),
            item.get("title", ""),
            item.get("ip_id"),
            1 if item.get("is_lot") else 0,
            item.get("item_count", 1),
            item.get("estimated_p", 0),
            item.get("current_jpy", 0),
            item.get("bid_count", 0),
            item.get("end_time"),
            item.get("status", "watching"),
            item.get("max_bid_jpy", 0),
            item.get("my_bid_jpy"),
            item.get("notify_level", 0),
            item.get("note"),
        ),
    )


def list_active_auctions() -> List[Dict[str, Any]]:
    db = Database()
    rows = db.fetch_all(
        "SELECT * FROM auction_watches WHERE status IN ('watching','over_threshold','bidded') ORDER BY end_time ASC"
    )
    return [row_to_aw(r) for r in rows]


def update_status(watch_id: int, status: str, current_jpy: Optional[float] = None,
                  bid_count: Optional[int] = None):
    db = Database()
    sets = ["status = ?", "last_checked = CURRENT_TIMESTAMP"]
    params: List[Any] = [status]
    if current_jpy is not None:
        sets.append("current_jpy = ?")
        params.append(current_jpy)
    if bid_count is not None:
        sets.append("bid_count = ?")
        params.append(bid_count)
    params.append(watch_id)
    db.execute(
        f"UPDATE auction_watches SET {', '.join(sets)} WHERE id = ?",
        params,
    )
