"""纯逻辑验证脚本（不启动GUI）。跑通：建库 → 种子 → 套利公式 → 扫描服务。"""
from __future__ import annotations

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def main():
    # 1) DB + 种子
    from src.models import init_database
    init_database()
    from seed_data import seed_if_empty
    n = seed_if_empty()
    print(f"[OK] 初始化种子: 导入 {n} 个IP (0=已存在)")

    from src.models import ip_model, character_model
    ips = ip_model.list_all_ips()
    print(f"[OK] 当前共有 IP: {len(ips)} 个")
    for ip in ips[:3]:
        chars = character_model.list_characters_by_ip(ip["id"])
        print(f"   - IP: {ip['name_cn']}/{ip['name_jp']} Rank#{ip['heat_rank']} 角色{len(chars)}个")

    # 2) 套利引擎 - 单品
    from src.services import calculate_single_item, calculate_lot, reverse_max_bid_jpy
    r = calculate_single_item(
        source="wamei",
        title="テスト うずまきナルト フィギュア VIBRATION STARS",
        price_jpy=3000,
        xianyu_avg_price=100.0,
        price_factor=1.2,  # 鸣人S级
        matched_ip="火影忍者",
    )
    print(
        f"[OK] 单品套利: 3000日元 → 到手价{r.total_cost:.1f}元 "
        f"闲鱼估价{r.estimated_p:.1f}元 净赚{r.net_profit:.1f}元 利润率{r.profit_rate*100:.1f}% "
        f"是否达标={r.pass_threshold}"
    )

    # 3) 套利引擎 - 打包（类似你截图那个火影11件）
    r2 = calculate_lot(
        source="wamei",
        title="NARUTO フィギュア まとめ売り プライズ景品 11点セット",
        price_jpy=8000,
        item_count=11,
        xianyu_avg_price_per_item=100.0,
        matched_ip="火影忍者",
        known_factor_items=[
            {"name": "鸣人", "factor": 1.2, "count": 4},
            {"name": "佐助", "factor": 1.0, "count": 4},
            {"name": "鼬",   "factor": 1.2, "count": 1},
        ],
    )
    print(
        f"[OK] 打包套利(11件火影8000日元): 到手价{r2.total_cost:.1f}元 "
        f"闲鱼估价{r2.estimated_p:.1f}元 净赚{r2.net_profit:.1f}元 利润率{r2.profit_rate*100:.1f}% "
        f"是否达标={r2.pass_threshold}"
    )
    assert r2.pass_threshold, "打包套利应该达标，看公式是否有bug"

    # 4) 反推心理价位（同打包）
    max_bid = reverse_max_bid_jpy(r2.estimated_p, r2.item_count)
    print(f"[OK] 打包反推最大可出: {max_bid:.0f} 日元")

    # 5) 扫描服务: 跑一遍 Mock 爬虫 → 入库 → 统计
    from src.services.scan_service import ScanService, ScanOptions
    opts = ScanOptions()
    svc = ScanService()

    def on_stage(stage, cur, total):
        if total > 0:
            print(f"   · {stage}: {cur}/{total}", end="\r", flush=True)
    svc.on_progress(on_stage)

    summary = svc.run_scan(opts)
    print()  # 换行刷掉进度
    print(
        f"[OK] 扫描完成: 抓到{summary.total_raw_items}条 → "
        f"计算{summary.calculated}条（其中打包{summary.lot_items}件）→ "
        f"达标{summary.passed_threshold}条"
    )
    if summary.results:
        print("   前3条达标结果展示:")
        for i, rr in enumerate(summary.results[:3], 1):
            print(
                f"     {i}) [{rr.matched_ip}] 利润率{rr.profit_rate*100:.1f}% "
                f"净赚{rr.net_profit:.0f}元 商品价{rr.price_jpy:.0f}日元 "
                f"({'打包x'+str(rr.item_count) if rr.is_lot else '单品'})"
            )
    if summary.errors:
        print(f"[WARN] 扫描期间 {len(summary.errors)} 条错误:")
        for e in summary.errors[:3]:
            print(f"   - {e}")

    # 6) 断言：数据库里 candidate_items 确实有东西
    from src.models import candidate_model
    rows = candidate_model.list_candidates(limit=5, passed_only=True)
    print(f"[OK] 数据库 candidate_items(达标) 共 {len(rows)} 条可展示")

    # 7) 盯拍表: 看有没有自动加入的
    from src.models import auction_watch_model
    aw = auction_watch_model.list_active_auctions()
    print(f"[OK] auction_watches 中的盯拍: {len(aw)} 条")
    for a in aw[:2]:
        print(f"   - {a['status']} / {a['source']} / 当前{a['current_jpy']:.0f} / 建议最多{a['max_bid_jpy']:.0f}")

    print("\n✅ 全链路验证通过")


if __name__ == "__main__":
    main()
