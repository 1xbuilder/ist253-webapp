"""
Провайдеры расписания. Каждый вуз = свой провайдер.
Единый интерфейс, чтобы бот не знал деталей конкретного вуза.

Каждый провайдер реализует:
  - list_campuses() -> list[dict]      : корпуса вуза (если несколько), [] если не делится
  - list_groups(campus_id) -> list[dict]: группы (название + внутренний код)
  - fetch_lessons(external_id, date)   : пары на дату в общем формате [{'discipline', 'time'}]
  - supports_group_picker -> bool      : можно ли выбрать группу из списка (иначе ручной ввод)
"""
from providers import omgtu, oat

# Реестр: ключ = schedule_provider заведения
REGISTRY = {
    "omgtu": omgtu,
    "oat": oat,
}


def get_provider(provider_key):
    return REGISTRY.get(provider_key)
