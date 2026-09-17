# -*- coding: utf-8 -*-
"""盘叔命典 · 查同八字

输入你的八字（或出生时间），查出命例库中与你八字相同/相近的名人与命例。

用法：
    python 查同八字.py --bazi "癸巳 甲子 丁酉 甲辰"
    python 查同八字.py --birth "1893-12-26 07:30"
    python 查同八字.py --birth "1893-12-26" --hour 7 --minute 30
    python 查同八字.py --birth "1893-11-19 07:30" --lunar      # 农历输入
    python 查同八字.py --bazi "癸巳 甲子 丁酉"                  # 只知三柱
    python 查同八字.py --bazi "癸巳 甲子 丁酉 甲辰" --json      # 机器可读
    python 查同八字.py --bazi "癸巳 甲子 丁酉 甲辰" --loose     # 附带日主相同的参考

匹配分级：
    ★★★ 完全一致   四柱全同（年+月+日+时）
    ★★☆ 三柱同     年+月+日相同；差别只在时柱（对方未知 / 你未知 / 确实不同）
    ★★☆ 相近       相同 2 柱（如「日柱+时柱同」年柱不同），按相同柱数排序
    ★☆☆ 日柱同     日柱相同（年月不同，可作同日元参考）
    ☆☆☆ 日主同     仅日干相同（弱参考，需 --loose）
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "_vendor")
if os.path.isdir(VENDOR):
    sys.path.insert(0, VENDOR)

DATA = os.path.join(os.path.dirname(HERE), "data")
LIB = os.path.join(DATA, "命例库.jsonl")

GZ = "甲乙丙丁戊己庚辛壬癸"
Z = "子丑寅卯辰巳午未申酉戌亥"
PILLAR_RE = re.compile(rf"^[{GZ}][{Z}]$")

TIER_ORDER = {"完全一致": 0, "三柱同": 1, "相近": 2, "日柱同": 3, "日主同": 4}
TYPE_ORDER = {"名人": 0, "赛事命例": 1, "古籍命例": 2}


def load_lib():
    with open(LIB, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def parse_bazi(text):
    """接受 '癸巳 甲子 丁酉 甲辰' / '癸巳甲子丁酉甲辰' / 三柱。"""
    toks = re.findall(rf"[{GZ}][{Z}]", text or "")
    if not toks:
        return None
    v = list(toks) + [None] * (4 - len(toks))
    return {"year": v[0], "month": v[1], "day": v[2], "hour": v[3]}


def bazi_from_birth(date_str, hour, minute, lunar=False):
    try:
        from lunar_python import Solar, Lunar
    except ImportError:
        print("需要内置的 lunar-python（scripts/_vendor/lunar_python），未找到。", file=sys.stderr)
        return None, None
    m = re.match(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", date_str)
    if not m:
        print(f"无法解析日期：{date_str}（示例 1893-12-26）", file=sys.stderr)
        return None, None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = hour if hour is not None else 0
    mm = minute or 0
    if lunar:
        lunar_obj = Lunar.fromYmdHms(y, mo, d, hh, mm, 0)
        solar = lunar_obj.getSolar()
        ec = lunar_obj.getEightChar()
        lunar_text = f"{y}年{mo}月{d}日 {hh}:{mm:02d}"
    else:
        solar = Solar.fromYmdHms(y, mo, d, hh, mm, 0)
        lunar_obj = solar.getLunar()
        ec = lunar_obj.getEightChar()
        lunar_text = lunar_obj.toString()
    pl = {"year": ec.getYear(), "month": ec.getMonth(), "day": ec.getDay(),
          "hour": ec.getTime() if hour is not None else None}
    return pl, lunar_text


def match(records, mine):
    my_y, my_m, my_d, my_h = (mine.get(k) for k in ("year", "month", "day", "hour"))
    out = []
    for r in records:
        pl = r.get("pillars") or {}
        y, m, d, h = pl.get("year"), pl.get("month"), pl.get("day"), pl.get("hour")
        if not (y and m and d):
            continue
        same3 = (y == my_y and m == my_m and d == my_d)
        same_day = (d == my_d)
        POS_LABEL = {"year": "年", "month": "月", "day": "日", "hour": "时"}
        same = [k for k in ("year", "month", "day", "hour")
                if mine.get(k) and pl.get(k) and mine[k] == pl[k]]
        n_same = len(same)
        if same3 and my_h and h and my_h == h:
            tier, why = "完全一致", "四柱全同"
        elif same3 and my_h and h and my_h != h:
            tier, why = "三柱同", f"年月日相同，时柱不同（你 {my_h} / 对方 {h}）"
        elif same3 and my_h and not h:
            tier, why = "三柱同", "年月日相同，对方时辰未知（若时辰相同即四柱全同）"
        elif same3 and not my_h and h:
            tier, why = "三柱同", f"年月日相同，你未提供时柱（对方为 {h} 时）"
        elif same3:
            tier, why = "三柱同", "年月日相同，双方时辰均未知"
        elif n_same >= 2:
            # 相同 2 柱以上（含「日柱+时柱同」这类），比单纯日柱同更有参考价值，优先归类
            tier = "相近"
            why = f"相同 {n_same} 柱：" + "、".join(POS_LABEL[k] for k in same)
        elif same_day:
            tier, why = "日柱同", "日柱相同（同日元）"
        else:
            continue
        out.append((TIER_ORDER[tier], (TYPE_ORDER.get(r.get("type"), 9), -n_same),
                    r.get("name") or "（无名）", r, tier, why))
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    return out


def show(rows, mine, loose_rows=None, verbose=False, limit=8):
    print("=" * 96)
    print(f"你的八字：{' '.join(mine.get(k) or '？？' for k in ('year', 'month', 'day', 'hour'))}"
          f"    日主：{mine['day'][0] if mine.get('day') else '?'}")
    print("=" * 96)
    if not rows:
        print("\n命例库中没有与你年月日相同的记录。")
        print("（命例库以古籍与历史人物为主，八字组合约 51.8 万种，查不到属正常。）")
        return

    def detail(r, why):
        pl = r["pillars"]
        four = " ".join(pl.get(k) or "？？" for k in ("year", "month", "day", "hour"))
        who = r.get("name") or "（古籍未具名）"
        meta = " / ".join(x for x in [r.get("type"), r.get("era"), r.get("domain"),
                                      (f"{r['gender']}命" if r.get("gender") else None)] if x)
        print(f"  ◆ {who}   [{meta}]")
        print(f"      四柱：{four}")
        if r.get("pattern"):
            print(f"      格局：{r['pattern']}")
        if r.get("summary"):
            print(f"      断语：{r['summary']}")
        if r.get("rules"):
            print(f"      规则：{r['rules']}")
        if r.get("reasoning"):
            print(f"      推理：{r['reasoning']}")
        if r.get("conclusion"):
            print(f"      结论：{r['conclusion']}")
        if r.get("master"):
            print(f"      评断：{r['master']}")
        print(f"      依据：{why}")
        print(f"      出处：{'、'.join(r.get('sources') or [])}")
        if r.get("caution"):
            print(f"      ⚠ {r['caution']}")
        for v in (r.get("variants") or []):
            print(f"      异说：{v.get('pillars')} —— {v.get('note')}")

    buckets = {"完全一致": [], "三柱同": [], "日柱同": []}
    for o, t, n, r, tier, why in rows:
        buckets.setdefault(tier, []).append((o, t, n, r, tier, why))

    for tier, mark in (("完全一致", "★★★"), ("三柱同", "★★☆"), ("相近", "★★☆")):
        items = buckets.get(tier) or []
        if not items:
            continue
        named = [x for x in items if x[3].get("type") == "名人"]
        print(f"\n{mark} 【{tier}】命中 {len(items)} 条（其中具名名人 {len(named)} 位）")
        for x in items[:limit]:
            detail(x[3], x[5])
        if len(items) > limit:
            print(f"  …另 {len(items) - limit} 条同类，用 --limit 调整")

    # 日柱同：默认只做摘要，避免刷屏
    items = buckets.get("日柱同") or []
    if items:
        named = [x for x in items if x[3].get("type") == "名人"]
        print(f"\n★☆☆ 【日柱同·同日元参考】命中 {len(items)} 条（具名名人 {len(named)} 位）")
        if named:
            print("  具名名人：" + "、".join(x[3]["name"] for x in named[:20])
                  + ("…" if len(named) > 20 else ""))
        if verbose:
            for x in items[:limit]:
                detail(x[3], x[5])
        else:
            print("  （加 --verbose 查看逐条断语）")

    if loose_rows:
        print(f"\n☆☆☆ 【日主同·弱参考】共 {len(loose_rows)} 条，仅列前 8 条：")
        for _o, _t, _n, r, _tier, _why in loose_rows[:8]:
            pl = r["pillars"]
            print(f"  · {(r.get('name') or '（无名）'):<12} "
                  f"{pl.get('year')} {pl.get('month')} {pl.get('day')} {pl.get('hour') or '？？'}"
                  f"   [{r.get('type')}]")
    print()


def main():
    ap = argparse.ArgumentParser(description="盘叔命典 · 查同八字")
    ap.add_argument("--bazi", help="四柱，如 \"癸巳 甲子 丁酉 甲辰\"（可只给三柱）")
    ap.add_argument("--birth", help="公历生日，如 1893-12-26")
    ap.add_argument("--hour", type=int, default=None, help="出生小时 0-23")
    ap.add_argument("--minute", type=int, default=0)
    ap.add_argument("--lunar", action="store_true", help="--birth 按农历解释")
    ap.add_argument("--loose", action="store_true", help="附带日主相同的弱参考")
    ap.add_argument("--verbose", action="store_true", help="日柱同层级也逐条展开")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    lunar_text = None
    if args.bazi:
        mine = parse_bazi(args.bazi)
        if not mine:
            print("八字解析失败。示例：--bazi \"癸巳 甲子 丁酉 甲辰\"", file=sys.stderr)
            return 2
    elif args.birth:
        mine, lunar_text = bazi_from_birth(args.birth, args.hour, args.minute, args.lunar)
        if not mine:
            return 2
    else:
        ap.print_help()
        return 1

    records = load_lib()
    rows = match(records, mine)
    loose_rows = []
    if args.loose and mine.get("day"):
        dm = mine["day"][0]
        loose_rows = [(3, TYPE_ORDER.get(r.get("type"), 9), r.get("name") or "",
                       r, "日主同", "日干相同") for r in records
                      if (r.get("pillars") or {}).get("day")
                      and r["pillars"]["day"][0] == dm
                      and not any(x[3] is r for x in rows)]
        loose_rows.sort(key=lambda x: (x[1], x[2]))

    if args.json:
        print(json.dumps({
            "输入八字": mine,
            "农历": lunar_text,
            "命中数": len(rows),
            "命中": [{"分级": t, "理由": w, **r} for _o, _t, _n, r, t, w in rows[:args.limit]],
        }, ensure_ascii=False, indent=2))
        return 0

    show(rows[:60], mine, loose_rows, verbose=args.verbose, limit=args.limit)
    if lunar_text:
        print(f"（换算农历：{lunar_text}）")
    hit = {}
    for _o, _t, _n, _r, tier, _w in rows:
        hit[tier] = hit.get(tier, 0) + 1
    print(f"命中统计：{hit if hit else '无'}    命例库共 {len(records)} 条")
    if not any(t == "完全一致" for _o, _t, _n, _r, t, _w in rows):
        print("提示：四柱完全一致者极少（时柱多缺失）。三星之外，「三柱同」已属高度相似。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
