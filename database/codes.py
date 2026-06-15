# database/codes.py
"""Генерация пригласительных кодов.
Алфавит без похожих символов (0/O, 1/l/I) — коды легко передать голосом/глазами.
secrets -> криптостойко, перебором не угадать."""
import secrets

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без 0 O 1 I L


def _gen(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def make_create_group_code() -> str:
    """Ссылка на создание группы — ценная, делаем длинной (12 символов)."""
    return "G" + _gen(12)


def make_join_group_code() -> str:
    """Ссылка-приглашение в группу — низкий риск, делаем покороче (8 символов)."""
    return "J" + _gen(8)
