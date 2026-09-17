# -*- coding: utf-8 -*-
"""查询 Wikidata：给定公历日期，返回该日出生的名人数数据。

用法：python query_wikidata.py YYYY-MM-DD [min_sitelinks]
依赖：仅标准库 urllib。
"""
import json
import sys
import urllib.parse
import urllib.request

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "tongren-mingdian-skill/1.0 (research tool; contact: user@example.com)"

QUERY_TEMPLATE = """
SELECT ?person ?personLabel ?personDescription ?sitelinks ?birthdate ?enTitle ?zhTitle WHERE {
  ?person wdt:P31 wd:Q5 .
  ?person wdt:P569 ?birthdate .
  FILTER(YEAR(?birthdate) = __Y__ && MONTH(?birthdate) = __M__ && DAY(?birthdate) = __D__)
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= __MIN__)
  OPTIONAL { ?enArticle schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?enTitle . }
  OPTIONAL { ?zhArticle schema:about ?person ; schema:isPartOf <https://zh.wikipedia.org/> ; schema:name ?zhTitle . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,en". }
}
ORDER BY DESC(?sitelinks)
LIMIT __LIMIT__
"""


def query(date_str, min_links=3, limit=200):
    y, m, d = date_str.split("-")
    query_str = (QUERY_TEMPLATE
                 .replace("__Y__", str(int(y)))
                 .replace("__M__", str(int(m)))
                 .replace("__D__", str(int(d)))
                 .replace("__MIN__", str(int(min_links)))
                 .replace("__LIMIT__", str(int(limit))))
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"format": "json", "query": query_str})
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return _parse(data)


def _parse(data):
    results = []
    for binding in data.get("results", {}).get("bindings", []):
        def val(k):
            return binding.get(k, {}).get("value")

        person_uri = val("person") or ""
        qid = person_uri.rsplit("/", 1)[-1]
        name = val("personLabel") or qid
        desc = val("personDescription") or ""
        sitelinks = val("sitelinks")
        birthdate = val("birthdate")
        en_title = val("enTitle")
        zh_title = val("zhTitle")
        if zh_title:
            url = "https://zh.wikipedia.org/wiki/" + urllib.parse.quote(zh_title.replace(" ", "_"))
        elif en_title:
            url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(en_title.replace(" ", "_"))
        else:
            url = "https://www.wikidata.org/wiki/" + qid
        results.append({
            "qid": qid,
            "name": name,
            "description": desc,
            "birthdate": birthdate,
            "sitelinks": int(sitelinks) if sitelinks else 0,
            "zh_title": zh_title,
            "en_title": en_title,
            "url": url,
        })
    return results


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    date_str = argv[1]
    min_links = int(argv[2]) if len(argv) >= 3 else 3
    try:
        results = query(date_str, min_links=min_links)
    except Exception as e:
        print("错误：", e)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))