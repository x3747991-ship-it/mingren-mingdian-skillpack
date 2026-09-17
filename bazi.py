# -*- coding: utf-8 -*-
"""八字（四柱）换算与逆向反推。

依赖：lunar_python（纯 Python），安装：pip install lunar_python

功能：
  1) date 子命令：公历日期 -> 四柱
  2) reverse 子命令：前三柱（年/月/日柱）-> 反推公历出生日期

约定：
  - 四柱均用两字符干支表示，如 "庚午"、"庚辰"、"丁卯"。
  - 前三柱（年柱、月柱、日柱）只由公历出生年月日决定（时柱需时辰，此处不用）。
"""
import sys
from datetime import date, timedelta

from lunar_python import Solar

GAN = list("甲乙丙丁戊己庚辛壬癸")
ZHI = list("子丑寅卯辰巳午未申酉戌亥")


def is_valid_pillar(s):
    """校验一个干支是否为合法六十甲子组合。"""
    if not s or len(s) != 2:
        return False
    if s[0] not in GAN or s[1] not in ZHI:
        return False
    # 合法甲子组合要求天干、地支序号奇偶一致
    return GAN.index(s[0]) % 2 == ZHI.index(s[1]) % 2


def pillars_from_date(y, m, d, h=12, minute=0):
    """公历出生日期 -> (年柱, 月柱, 日柱, 时柱)。"""
    l = Solar.fromYmdHms(y, m, d, h, minute, 0).getLunar()
    ec = l.getEightChar()
    return ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()


def date_from_pillars(year_gz, month_gz, day_gz, start=1900, end=2030):
    """由前三柱反推公历日期。返回 [(year, month, day), ...]。

    注意：同一组前三柱可能对应多个年份（年柱 60 年一循环，且月柱/日柱在
    不同年份可能同时命中），故返回全部候选日期，供上层消歧（如询问用户出生年份）。
    """
    if not (is_valid_pillar(year_gz) and is_valid_pillar(month_gz) and is_valid_pillar(day_gz)):
        raise ValueError("存在非法的干支组合：%s %s %s" % (year_gz, month_gz, day_gz))

    # 1) 定位年柱匹配的年份（以每年 7 月 1 日的年柱为准，避开立春边界歧义）
    anchor_years = []
    for y in range(start, end + 2):
        if Solar.fromYmd(y, 7, 1).getLunar().getEightChar().getYear() == year_gz:
            anchor_years.append(y)
    if not anchor_years:
        raise ValueError("在 %d-%d 范围内未找到年柱为 %s 的年份" % (start, end, year_gz))

    # 2) 在这些年份（及次年，覆盖立春跨年）内逐日匹配月柱、日柱
    results = []
    years_to_scan = set()
    for y in anchor_years:
        years_to_scan.add(y)
        years_to_scan.add(y + 1)
    for y in sorted(years_to_scan):
        if y < start or y > end:
            continue
        d = date(y, 1, 1)
        end_of_year = date(y, 12, 31)
        while d <= end_of_year:
            e = _eight_char(d)
            if e[1] == month_gz and e[2] == day_gz:
                results.append((d.year, d.month, d.day))
            d += timedelta(days=1)
    results.sort()
    return results


def _eight_char(d):
    """公历 date -> (年柱, 月柱, 日柱, 时柱)。时柱按午时(12:00)占位，仅前三柱有意义。"""
    l = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
    ec = l.getEightChar()
    return ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "date":
        # 用法：bazi.py date 1990-05-02 [12:00]
        yy, mm, dd = argv[2].split("-")
        hh = 12
        if len(argv) >= 4 and ":" in argv[3]:
            hh = int(argv[3].split(":")[0])
        p = pillars_from_date(int(yy), int(mm), int(dd), hh, 0)
        print("年柱=%s 月柱=%s 日柱=%s 时柱=%s" % p)
        return 0
    if cmd == "reverse":
        # 用法：bazi.py reverse 庚午 庚辰 丁卯 [start] [end]
        year_gz, month_gz, day_gz = argv[2], argv[3], argv[4]
        start = int(argv[5]) if len(argv) >= 6 else 1900
        end = int(argv[6]) if len(argv) >= 7 else 2030
        try:
            dates = date_from_pillars(year_gz, month_gz, day_gz, start, end)
        except ValueError as e:
            print("错误：", e)
            return 1
        if not dates:
            print("未找到匹配的日期")
            return 0
        for y, m, d in dates:
            print("%04d-%02d-%02d" % (y, m, d))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))