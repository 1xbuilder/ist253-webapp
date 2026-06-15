"""Провайдер Омского авиаколледжа (oat.ru) — парсинг HTML (API нет)."""
import aiohttp

NAME = "Омский авиационный колледж"
supports_group_picker = True
group_id_hint = "выбирается из списка"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StudyFlowBot/1.0)"}
_BASE = "https://www.oat.ru"

# Справочник корпусов: id (код в URL) + человекочитаемое имя.
# Код берётся из пути групп: /timetable/timetable/<код_корпуса>/<группа>
# Корпус 1 подтверждён. Остальные заполняются по мере проверки URL.
CAMPUSES = [
    {"id": "ul_lenina_24",          "name": "Корпус 1 — ул. Ленина, 24"},
    {"id": "ul_b_khmelnickogo_281a","name": "Корпус 2 — ул. Б. Хмельницкого, 281а"},
    {"id": "pr_kosmicheskij_14a",   "name": "Корпус 3 — пр. Космический, 14а"},
    {"id": "ul_volkhovstroya_5",    "name": "Корпус 4 — ул. Волховстроя, 5"},
]

_OAT_DAYS = ["понедельник", "вторник", "среда", "четверг",
             "пятница", "суббота", "воскресенье"]


def list_campuses():
    return CAMPUSES


async def _get(url):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=_HEADERS,
                             timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status == 200:
                    return await r.text()
                print(f"oat: HTTP {r.status} для {url}")
    except Exception as e:
        print(f"oat: ошибка запроса {url}: {e}")
    return None


async def list_groups(campus_id):
    """Список групп корпуса: [{'name': 'КС115', 'external_id': 'ul_lenina_24/КС115'}]."""
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        print(f"oat: нет bs4: {e}")
        return []
    # Страница групп корпуса. Пути групп ведут на /timetable/timetable/<campus>/<group>,
    # а страница со списком групп — /timetable/groups/<campus> (определено по навигации сайта).
    html = await _get(f"{_BASE}/timetable/groups/{campus_id}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select("a[href*='/timetable/timetable/']"):
        name = a.get_text(strip=True)
        href = a.get("href", "")
        path = href.split("/timetable/timetable/", 1)[-1]
        if name and path:
            out.append({"name": name, "external_id": path})
    return out


def _week_parity(date_obj):
    return 1 if date_obj.isocalendar()[1] % 2 == 1 else 2


async def fetch_lessons(external_id, date_obj):
    """external_id вида 'ul_lenina_24/КС115'."""
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        print(f"oat: нет bs4: {e}")
        return []
    html = await _get(f"{_BASE}/timetable/timetable/{external_id}")
    if not html:
        return []

    target_day = _OAT_DAYS[date_obj.weekday()]
    week = _week_parity(date_obj)
    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.select("table.timetable")
              if "display: none" not in (t.get("style") or "")
              and "groups" not in (t.get("class") or [])]
    if len(tables) < week:
        return []
    table = tables[week - 1]
    headers_row = [th.get_text(strip=True) for th in table.select("thead th")]
    day_cols = headers_row[2:]

    lessons = []
    for tr in table.select("tbody > tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        time_txt = " ".join(cells[1].get_text(" ", strip=True).split())
        for i, day_cell in enumerate(cells[2:]):
            if i >= len(day_cols):
                break
            col_day = day_cols[i].rsplit("-", 1)[0].lower()
            if col_day != target_day:
                continue
            subj_el = day_cell.select_one(".subjectt-name")
            if not subj_el:
                continue
            base_name = subj_el.get_text(strip=True)
            items = day_cell.select(".subjectt-more-item")
            has_sg = any("подгруппа" in it.get_text(" ", strip=True).lower()
                         for it in items)
            if has_sg and items:
                for it in items:
                    txt = it.get_text(" ", strip=True).lower()
                    sg = "1" if "подгруппа 1" in txt else ("2" if "подгруппа 2" in txt else None)
                    disc = f"{base_name}/{sg}" if sg else base_name
                    lessons.append({"discipline": disc, "time": time_txt})
            else:
                lessons.append({"discipline": base_name, "time": time_txt})
    return lessons
