# -*- coding: utf-8 -*-
"""Wikidata 正查核实：给定人名，返回该实体在 Wikidata 的出生日期（P569）。

用于「发现」候选人之后做交叉核实。本环境 query.wikidata.org 的 SPARQL 不可达，
但 www.wikidata.org 的实体 API 可达，故用「名字搜 QID → 取 P569」的正查方式。

用法：python query_wikidata_verify.py "<名字>" [语言]
      语言默认 zh，可传 en。
依赖：仅标准库 urllib。
"""
import json
import sys
import urllib.parse
import urllib.request

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "tongren-mingdian-skill/1.0 (research tool; contact: user@example.com)"


def _get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_time(t):
    if not t or not t.startswith("+"):
        return None
    return t[1:].split("T")[0]


def lookup(name, lang="zh", limit=5):
    """返回匹配的人类实体列表，每个含 qid/name/description/birthdate/precision/url。"""
    s = _get({
        "action": "wbsearchentities",
        "search": name,
        "language": lang,
        "type": "item",
        "limit": str(limit),
        "format": "json",
    })
    hits = s.get("search", [])
    if not hits:
        return []

    ids = "|".join(h["id"] for h in hits)
    e = _get({"action": "wbgetentities", "ids": ids, "props": "claims", "format": "json"})
    entities = e.get("entities", {})

    results = []
    for h in hits:
        qid = h["id"]
        claims = entities.get(qid, {}).get("claims", {})
        p31 = claims.get("P31", [])
        is_human = any(
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5"
            for c in p31
        )
        if not is_human:
            continue
        p569 = claims.get("P569", [])
        if not p569:
            continue
        dv = p569[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
        results.append({
            "qid": qid,
            "name": h.get("label") or name,
            "description": h.get("description") or "",
            "birthdate": _parse_time(dv.get("time")),
            "precision": dv.get("precision"),  # 11=日 10=月 9=年
            "url": "https://www.wikidata.org/wiki/" + qid,
        })
    return results


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    name = argv[1]
    lang = argv[2] if len(argv) >= 3 else "zh"
    try:
        results = lookup(name, lang)
    except Exception as e:
        print("错误：", e)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))