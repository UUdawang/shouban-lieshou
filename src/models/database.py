"""SQLite 统一封装。参数化 SQL，避免注入和重复连接管理代码。"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, List, Optional, Tuple

from config import DB_PATH, ensure_dirs


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        ensure_dirs()
        self._db_path = str(DB_PATH)
        self._conn_lock = threading.Lock()
        self._initialized = True

    # ---------- 基础执行 ----------
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self._db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        """执行写操作（INSERT/UPDATE/DELETE），返回 lastrowid 或 affected rows。"""
        with self._conn_lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, tuple(params))
                return cur.lastrowid if cur.lastrowid else cur.rowcount

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self._conn_lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, tuple(params))
                return cur.fetchone()

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self._conn_lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, tuple(params))
                return cur.fetchall()

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]) -> int:
        with self._conn_lock:
            with self._get_conn() as conn:
                cur = conn.executemany(sql, [tuple(p) for p in seq_of_params])
                return cur.rowcount


# ============================================================
# 建表 SQL（MVP-0 4 张表）
# ============================================================
CREATE_TABLES_SQL = [
    # IP 表
    """
    CREATE TABLE IF NOT EXISTS ips (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name_cn         TEXT NOT NULL,
        name_jp         TEXT,
        aliases         TEXT DEFAULT '[]',        -- JSON array
        heat_score      REAL DEFAULT 0,
        heat_rank       INTEGER DEFAULT 9999,
        source_weights  TEXT DEFAULT '{}',        -- JSON object
        search_keywords TEXT DEFAULT '[]',        -- JSON array of keyword combos
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        manual_override INTEGER DEFAULT 0         -- BOOLEAN
    )
    """,
    # 角色分级表
    """
    CREATE TABLE IF NOT EXISTS characters (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_id           INTEGER NOT NULL,
        name_cn         TEXT NOT NULL,
        name_jp         TEXT,
        aliases         TEXT DEFAULT '[]',        -- JSON array
        grade           TEXT NOT NULL DEFAULT 'C',  -- S/A/B/C
        price_factor    REAL NOT NULL DEFAULT 0.4,  -- S=1.2 / A=1.0 / B=0.7 / C=0.4
        heat_score      REAL DEFAULT 0,
        source_weights  TEXT DEFAULT '{}',
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        manual_override INTEGER DEFAULT 0,
        FOREIGN KEY (ip_id) REFERENCES ips(id) ON DELETE CASCADE
    )
    """,
    # 盯拍拍卖表
    """
    CREATE TABLE IF NOT EXISTS auction_watches (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        source          TEXT NOT NULL DEFAULT 'wamei',
        auction_url     TEXT UNIQUE,
        title           TEXT NOT NULL,
        ip_id           INTEGER,
        is_lot          INTEGER NOT NULL DEFAULT 0,  -- BOOLEAN
        item_count      INTEGER DEFAULT 1,
        estimated_p     REAL NOT NULL DEFAULT 0,     -- 国内预估总售价（元）
        current_jpy     REAL NOT NULL DEFAULT 0,     -- 当前日元出价
        bid_count       INTEGER DEFAULT 0,
        end_time        DATETIME,
        status          TEXT NOT NULL DEFAULT 'watching',
        max_bid_jpy     REAL DEFAULT 0,              -- 最大心理价位（日元）
        my_bid_jpy      REAL,
        last_checked    DATETIME,
        notify_level    INTEGER DEFAULT 0,
        note            TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ip_id) REFERENCES ips(id) ON DELETE SET NULL
    )
    """,
    # 候选商品池（扫描达标后入库，UI展示/历史记录均基于此）
    """
    CREATE TABLE IF NOT EXISTS candidate_items (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        source          TEXT NOT NULL,
        item_url        TEXT,
        title           TEXT NOT NULL,
        ip_id           INTEGER,
        is_lot          INTEGER NOT NULL DEFAULT 0,
        item_count      INTEGER DEFAULT 1,
        price_jpy       REAL NOT NULL,               -- 商品显示的日元价
        price_cny_proxy REAL NOT NULL DEFAULT 0,     -- 挖煤姬到手价估算 CNY
        estimated_p     REAL NOT NULL DEFAULT 0,     -- 闲鱼估价 CNY
        intl_shipping   REAL NOT NULL DEFAULT 0,     -- 国际运费估算
        tariff          REAL NOT NULL DEFAULT 0,     -- 关税估算
        total_cost      REAL NOT NULL DEFAULT 0,     -- 总成本 CNY
        xian_fee        REAL NOT NULL DEFAULT 0,     -- 闲鱼手续费
        pack_fee        REAL NOT NULL DEFAULT 0,     -- 包装发货
        net_profit      REAL NOT NULL DEFAULT 0,     -- 净毛利
        profit_rate     REAL NOT NULL DEFAULT 0,     -- 利润率
        pass_threshold  INTEGER NOT NULL DEFAULT 0,  -- 是否通过双阈值 BOOLEAN
        matched_ip      TEXT,                        -- 冗余，展示用
        snapshot_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def init_database():
    """首次启动调用，建表 + 检查种子数据是否存在。"""
    db = Database()
    for sql in CREATE_TABLES_SQL:
        db.execute(sql)
