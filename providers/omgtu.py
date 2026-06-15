"""Провайдер ОмГТУ — JSON API rasp.omgtu.ru."""
import aiohttp

NAME = "ОмГТУ"
supports_group_picker = False  # списка групп нет, староста вводит числовой id
group_id_hint = "числовой id группы из rasp.omgtu.ru (например 427)"


def list_campuses():
    return []  # без корпусов


def list_groups(campus_id=None):
    return []  # списка нет


async def fetch_lessons(external_id, date_obj):
    """Возвращает пары на дату в общем формате [{'discipline', ...}]."""
    if not external_id:
        return []
    date_str = date_obj.strftime("%Y.%m.%d")
    url = (f"https://rasp.omgtu.ru/api/schedule/group/{external_id}"
           f"?start={date_str}&finish={date_str}&lng=1")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    return data if isinstance(data, list) else []
    except Exception as e:
        print(f"omgtu fetch error: {e}")
    return []
