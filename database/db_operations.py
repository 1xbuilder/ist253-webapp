# database/db_operations.py
from database.db_session import supabase
from database.codes import make_create_group_code, make_join_group_code
from datetime import date, datetime, timedelta
import json


# ── DTO-классы (имитируют ORM-объекты, чтобы хендлеры меньше переписывать) ──────

class InstitutionDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.name = d.get('name', '')
        self.city = d.get('city')
        self.schedule_provider = d.get('schedule_provider')
        self.schedule_provider_id = d.get('schedule_provider_id')


class GroupDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.institution_id = d.get('institution_id')
        self.name = d.get('name', '')
        self.external_schedule_id = d.get('external_schedule_id')
        self.owner_user_id = d.get('owner_user_id')


class UserDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.user_id = d.get('user_id')
        self.username = d.get('username')
        self.first_name = d.get('first_name', '')
        self.last_name = d.get('last_name')
        self.active_group_id = d.get('active_group_id')
        self.global_role = d.get('global_role', 'user')
        self.subgroup = d.get('subgroup')


class MemberDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.group_id = d.get('group_id')
        self.user_id = d.get('user_id')
        self.group_role = d.get('group_role', 'member')
        self.subgroup = d.get('subgroup')


class InviteDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.code = d.get('code')
        self.invite_type = d.get('invite_type')
        self.group_id = d.get('group_id')
        self.institution_id = d.get('institution_id')
        self.created_by = d.get('created_by')
        self.is_single_use = d.get('is_single_use', True)
        self.max_uses = d.get('max_uses')
        self.uses_count = d.get('uses_count', 0)
        self.is_active = d.get('is_active', True)
        self.expires_at = d.get('expires_at')


class HomeworkDTO:
    def __init__(self, d: dict):
        self.id = d.get('id')
        self.group_id = d.get('group_id')
        self.subject = d.get('subject', '')
        self.task = d.get('task', '')
        raw = d.get('date_for')
        self.date_for = date.fromisoformat(raw) if isinstance(raw, str) else raw
        self.subgroup = d.get('subgroup')
        self.attachment_file_id = d.get('attachment_file_id')
        self.attachment_type = d.get('attachment_type')
        self.created_by = d.get('created_by')
        self.created_at = d.get('created_at')


# ── Institutions ───────────────────────────────────────────────────────────────

def create_institution(name, city=None, schedule_provider=None, schedule_provider_id=None):
    try:
        data = {"name": name, "city": city,
                "schedule_provider": schedule_provider,
                "schedule_provider_id": schedule_provider_id}
        r = supabase.table("institutions").insert(data).execute()
        return InstitutionDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка create_institution: {e}")
        return None


def get_institution_by_id(institution_id):
    try:
        r = supabase.table("institutions").select("*").eq("id", institution_id).execute()
        return InstitutionDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_institution_by_id: {e}")
        return None


def list_institutions():
    try:
        r = supabase.table("institutions").select("*").order("name").execute()
        return [InstitutionDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_institutions: {e}")
        return []


# ── Groups ─────────────────────────────────────────────────────────────────────

def create_group(institution_id, name, owner_user_id=None, external_schedule_id=None):
    global LAST_ERROR
    LAST_ERROR = None
    try:
        data = {"institution_id": institution_id, "name": name,
                "owner_user_id": owner_user_id,
                "external_schedule_id": external_schedule_id}
        r = supabase.table("groups").insert(data).execute()
        return GroupDTO(r.data[0]) if r.data else None
    except Exception as e:
        import logging
        LAST_ERROR = str(e)
        logging.warning(f"CREATE_GROUP FAIL: {e}")
        print(f"Ошибка create_group: {e}")
        return None


def get_group_by_id(group_id):
    try:
        r = supabase.table("groups").select("*").eq("id", group_id).execute()
        return GroupDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_group_by_id: {e}")
        return None


def list_groups_by_institution(institution_id):
    try:
        r = supabase.table("groups").select("*").eq("institution_id", institution_id).order("name").execute()
        return [GroupDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_groups_by_institution: {e}")
        return []


def update_group(group_id, **fields):
    try:
        clean = {k: v for k, v in fields.items() if v is not None}
        if not clean:
            return get_group_by_id(group_id)
        r = supabase.table("groups").update(clean).eq("id", group_id).execute()
        return GroupDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка update_group: {e}")
        return None


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_telegram_id(db=None, telegram_id=None):
    try:
        r = supabase.table("users").select("*").eq("user_id", telegram_id).execute()
        return UserDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_user_by_telegram_id: {e}")
        return None


LAST_ERROR = None  # текст последней ошибки БД (для отладки регистрации)


def create_user(db=None, telegram_id=None, username=None, first_name=None, last_name=None):
    global LAST_ERROR
    LAST_ERROR = None
    try:
        data = {"user_id": telegram_id, "username": username,
                "first_name": first_name or "", "last_name": last_name,
                "global_role": "user"}
        r = supabase.table("users").insert(data).execute()
        if r.data:
            return UserDTO(r.data[0])
        # Вставка могла пройти, но ответ пуст (например из-за RLS на возврат строки).
        # Перечитываем пользователя — если он есть, регистрация удалась.
        existing = get_user_by_telegram_id(telegram_id=telegram_id)
        if existing:
            return existing
        LAST_ERROR = "insert вернул пустой ответ и пользователь не найден при перечитывании"
        return None
    except Exception as e:
        LAST_ERROR = str(e)
        print(f"Ошибка create_user: {e}")
        return None


def set_active_group(telegram_id, group_id):
    try:
        r = supabase.table("users").update({"active_group_id": group_id}).eq("user_id", telegram_id).execute()
        return UserDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка set_active_group: {e}")
        return None


def set_global_role(telegram_id, role):
    """role: 'user' | 'moderator' | 'admin'"""
    try:
        r = supabase.table("users").update({"global_role": role}).eq("user_id", telegram_id).execute()
        return UserDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка set_global_role: {e}")
        return None


def update_user_subgroup(db=None, telegram_id=None, subgroup=None):
    try:
        r = supabase.table("users").update({"subgroup": subgroup}).eq("user_id", telegram_id).execute()
        return UserDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка update_user_subgroup: {e}")
        return None


# ── Group members (роли внутри группы) ─────────────────────────────────────────

def add_member(group_id, user_id, group_role="member", subgroup=None):
    """Добавляет/обновляет участника группы. Если уже есть — обновляет роль."""
    try:
        existing = supabase.table("group_members").select("*") \
            .eq("group_id", group_id).eq("user_id", user_id).execute()
        if existing.data:
            upd = {"group_role": group_role}
            if subgroup is not None:
                upd["subgroup"] = subgroup
            r = supabase.table("group_members").update(upd) \
                .eq("id", existing.data[0]["id"]).execute()
            return MemberDTO(r.data[0]) if r.data else None
        data = {"group_id": group_id, "user_id": user_id,
                "group_role": group_role, "subgroup": subgroup}
        r = supabase.table("group_members").insert(data).execute()
        return MemberDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка add_member: {e}")
        return None


def get_membership(group_id, user_id):
    try:
        r = supabase.table("group_members").select("*") \
            .eq("group_id", group_id).eq("user_id", user_id).execute()
        return MemberDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_membership: {e}")
        return None


def list_user_memberships(user_id):
    try:
        r = supabase.table("group_members").select("*").eq("user_id", user_id).execute()
        return [MemberDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_user_memberships: {e}")
        return []


def list_group_members(group_id, role=None):
    try:
        q = supabase.table("group_members").select("*").eq("group_id", group_id)
        if role:
            q = q.eq("group_role", role)
        r = q.execute()
        return [MemberDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_group_members: {e}")
        return []


def set_member_role(group_id, user_id, group_role):
    """group_role: 'owner' | 'helper' | 'member'"""
    return add_member(group_id, user_id, group_role=group_role)


def remove_member(group_id, user_id):
    try:
        supabase.table("group_members").delete() \
            .eq("group_id", group_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"Ошибка remove_member: {e}")
        return False


# ── Invites ────────────────────────────────────────────────────────────────────

def create_invite(invite_type, group_id=None, institution_id=None, created_by=None,
                  is_single_use=None, max_uses=None, expires_at=None):
    """invite_type: 'create_group' (одноразовая) | 'join_group' (многоразовая)."""
    try:
        if invite_type == "create_group":
            code = make_create_group_code()
            if is_single_use is None:
                is_single_use = True
        else:
            code = make_join_group_code()
            if is_single_use is None:
                is_single_use = False
        data = {"code": code, "invite_type": invite_type,
                "group_id": group_id, "institution_id": institution_id,
                "created_by": created_by, "is_single_use": is_single_use,
                "max_uses": max_uses, "uses_count": 0, "is_active": True,
                "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at}
        r = supabase.table("invites").insert(data).execute()
        return InviteDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка create_invite: {e}")
        return None


def get_invite_by_code(code):
    try:
        r = supabase.table("invites").select("*").eq("code", code).execute()
        return InviteDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_invite_by_code: {e}")
        return None


def is_invite_usable(invite: "InviteDTO"):
    """Проверяет, можно ли ещё воспользоваться инвайтом. Возвращает (ok, причина)."""
    if invite is None:
        return False, "Ссылка не найдена"
    if not invite.is_active:
        return False, "Ссылка больше не активна"
    if invite.expires_at:
        try:
            exp = datetime.fromisoformat(str(invite.expires_at).replace("Z", "+00:00"))
            if datetime.now(exp.tzinfo) > exp:
                return False, "Срок действия ссылки истёк"
        except Exception:
            pass
    if invite.is_single_use and invite.uses_count >= 1:
        return False, "Одноразовая ссылка уже использована"
    if invite.max_uses is not None and invite.uses_count >= invite.max_uses:
        return False, "Исчерпан лимит использований ссылки"
    return True, ""


def mark_invite_used(code):
    """Увеличивает счётчик; одноразовую деактивирует."""
    try:
        inv = get_invite_by_code(code)
        if not inv:
            return False
        upd = {"uses_count": (inv.uses_count or 0) + 1}
        if inv.is_single_use:
            upd["is_active"] = False
        supabase.table("invites").update(upd).eq("code", code).execute()
        return True
    except Exception as e:
        print(f"Ошибка mark_invite_used: {e}")
        return False


def deactivate_invite(code):
    try:
        supabase.table("invites").update({"is_active": False}).eq("code", code).execute()
        return True
    except Exception as e:
        print(f"Ошибка deactivate_invite: {e}")
        return False


def list_group_invites(group_id):
    try:
        r = supabase.table("invites").select("*").eq("group_id", group_id) \
            .order("created_at", desc=True).execute()
        return [InviteDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_group_invites: {e}")
        return []


# ── Homework (теперь всё в контексте group_id) ─────────────────────────────────

def add_homework_to_db(db=None, group_id=None, subject='', task='', date_for=None,
                       subgroup=None, attachment_file_id=None, created_by=None):
    try:
        if attachment_file_id and isinstance(attachment_file_id, list):
            attachment_file_id = json.dumps(attachment_file_id, ensure_ascii=False)
        data = {"group_id": group_id, "subject": subject, "task": task,
                "date_for": str(date_for), "subgroup": subgroup,
                "attachment_file_id": attachment_file_id, "created_by": created_by}
        r = supabase.table("homeworks").insert(data).execute()
        return HomeworkDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка add_homework_to_db: {e}")
        return None


def get_homework_by_date(db=None, group_id=None, target_date=None):
    try:
        q = supabase.table("homeworks").select("*").eq("date_for", str(target_date))
        if group_id is not None:
            q = q.eq("group_id", group_id)
        r = q.execute()
        return [HomeworkDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка get_homework_by_date: {e}")
        return []


def get_today_homework(db=None, group_id=None):
    return get_homework_by_date(group_id=group_id, target_date=date.today())


def get_tomorrow_homework(db=None, group_id=None):
    return get_homework_by_date(group_id=group_id, target_date=date.today() + timedelta(days=1))


def get_week_homework(db=None, group_id=None):
    try:
        today = date.today()
        end = today + timedelta(days=7)
        q = supabase.table("homeworks").select("*") \
            .gte("date_for", str(today)).lte("date_for", str(end))
        if group_id is not None:
            q = q.eq("group_id", group_id)
        r = q.order("date_for").execute()
        return [HomeworkDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка get_week_homework: {e}")
        return []


def get_all_homeworks(db=None, group_id=None):
    try:
        q = supabase.table("homeworks").select("*")
        if group_id is not None:
            q = q.eq("group_id", group_id)
        r = q.order("date_for", desc=True).execute()
        return [HomeworkDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка get_all_homeworks: {e}")
        return []


def get_homework_by_id(db=None, homework_id=None):
    try:
        r = supabase.table("homeworks").select("*").eq("id", homework_id).execute()
        return HomeworkDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка get_homework_by_id: {e}")
        return None


def delete_homework(db=None, homework_id=None):
    try:
        supabase.table("homeworks").delete().eq("id", homework_id).execute()
        return True
    except Exception as e:
        print(f"Ошибка delete_homework: {e}")
        return False


def update_homework(db=None, homework_id=None, subject=None, task=None,
                    date_for=None, subgroup=None, attachment_file_id=None):
    try:
        updates = {"updated_at": datetime.now().isoformat()}
        if subject is not None:
            updates["subject"] = subject
        if task is not None:
            updates["task"] = task
        if date_for is not None:
            updates["date_for"] = str(date_for)
        if subgroup is not None:
            updates["subgroup"] = subgroup
        if attachment_file_id is not None:
            if isinstance(attachment_file_id, list):
                attachment_file_id = json.dumps(attachment_file_id, ensure_ascii=False)
            updates["attachment_file_id"] = attachment_file_id
        r = supabase.table("homeworks").update(updates).eq("id", homework_id).execute()
        return HomeworkDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка update_homework: {e}")
        return None


def get_attachments_from_homework(homework):
    if homework.attachment_file_id:
        try:
            return json.loads(homework.attachment_file_id)
        except Exception:
            return []
    return []


# ── Права (хелперы для проверок в хендлерах) ───────────────────────────────────

def can_edit_homework(user_id, group_id):
    """Может ли пользователь добавлять/удалять ДЗ в этой группе.
    Да, если он admin/moderator глобально ИЛИ owner/helper в этой группе."""
    user = get_user_by_telegram_id(telegram_id=user_id)
    if user and user.global_role in ("admin", "moderator"):
        return True
    m = get_membership(group_id, user_id)
    return bool(m and m.group_role in ("owner", "helper"))


def can_manage_group(user_id, group_id):
    """Может ли управлять группой (помощники, ссылки): admin глобально ИЛИ owner группы."""
    user = get_user_by_telegram_id(telegram_id=user_id)
    if user and user.global_role == "admin":
        return True
    m = get_membership(group_id, user_id)
    return bool(m and m.group_role == "owner")


# ── Дополнительные операции (профиль, переключение групп, админка) ──────────────

def update_user_name(telegram_id, first_name):
    try:
        r = supabase.table("users").update({"first_name": first_name}).eq("user_id", telegram_id).execute()
        return UserDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка update_user_name: {e}")
        return None


def list_user_groups_detailed(user_id):
    """Возвращает список (membership, group) по всем группам пользователя."""
    out = []
    for m in list_user_memberships(user_id):
        g = get_group_by_id(m.group_id)
        if g:
            out.append((m, g))
    return out


def leave_group(user_id, group_id):
    """Покидает группу. Если это была активная — переключает на любую оставшуюся.
    Возвращает (ok, новая_активная_group_id|None)."""
    try:
        remove_member(group_id, user_id)
        user = get_user_by_telegram_id(telegram_id=user_id)
        new_active = None
        if user and user.active_group_id == group_id:
            remaining = list_user_memberships(user_id)
            new_active = remaining[0].group_id if remaining else None
            set_active_group(user_id, new_active)
        return True, new_active
    except Exception as e:
        print(f"Ошибка leave_group: {e}")
        return False, None


def delete_group(group_id):
    """Удаляет группу (каскадом — её ДЗ, участников, инвайты через FK on delete cascade)."""
    try:
        supabase.table("groups").delete().eq("id", group_id).execute()
        return True
    except Exception as e:
        print(f"Ошибка delete_group: {e}")
        return False


def delete_institution(institution_id):
    """Удаляет заведение (каскадом — его группы)."""
    try:
        supabase.table("institutions").delete().eq("id", institution_id).execute()
        return True
    except Exception as e:
        print(f"Ошибка delete_institution: {e}")
        return False


def list_all_groups():
    try:
        r = supabase.table("groups").select("*").order("institution_id").execute()
        return [GroupDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка list_all_groups: {e}")
        return []


def search_users(query):
    """Поиск пользователей по имени или username (для админки)."""
    try:
        r = supabase.table("users").select("*").or_(
            f"first_name.ilike.%{query}%,username.ilike.%{query}%"
        ).limit(20).execute()
        return [UserDTO(x) for x in r.data]
    except Exception as e:
        print(f"Ошибка search_users: {e}")
        return []


def count_group_members(group_id):
    try:
        r = supabase.table("group_members").select("id", count="exact").eq("group_id", group_id).execute()
        return r.count or 0
    except Exception as e:
        print(f"Ошибка count_group_members: {e}")
        return 0


def update_institution(institution_id, **fields):
    try:
        clean = {k: v for k, v in fields.items() if v is not None}
        if not clean:
            return get_institution_by_id(institution_id)
        r = supabase.table("institutions").update(clean).eq("id", institution_id).execute()
        return InstitutionDTO(r.data[0]) if r.data else None
    except Exception as e:
        print(f"Ошибка update_institution: {e}")
        return None
