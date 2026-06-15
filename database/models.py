# database/models.py
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Date, DateTime, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Institution(Base):
    """Учебное заведение: институт / колледж / техникум."""
    __tablename__ = 'institutions'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=True)

    # Поставщик расписания. У вузов может быть API (как ОмГТУ),
    # у колледжей зачастую его нет -> только ручной ввод предметов.
    schedule_provider = Column(String(50), nullable=True)      # 'omgtu' или None
    schedule_provider_id = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    groups = relationship("Group", back_populates="institution")

    def __repr__(self):
        return f"Institution(id={self.id}, name='{self.name}', city='{self.city}')"


class Group(Base):
    """Учебная группа внутри заведения (напр. ИС-301)."""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    institution_id = Column(Integer, ForeignKey('institutions.id'), nullable=False)
    name = Column(String(100), nullable=False)

    # ID этой группы во внешнем API расписания заведения.
    # Заменяет зашитый ранее GROUP_ID = 427. None -> ручной ввод предметов.
    external_schedule_id = Column(String(50), nullable=True)

    # Кто создал группу (староста-владелец). Дублируется ролью owner в group_members,
    # но удобно иметь прямую ссылку.
    owner_user_id = Column(BigInteger, nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    institution = relationship("Institution", back_populates="groups")
    homeworks = relationship("Homework", back_populates="group")
    members = relationship("GroupMember", back_populates="group")

    def __repr__(self):
        return f"Group(id={self.id}, name='{self.name}', institution_id={self.institution_id})"


class User(Base):
    """Пользователь Telegram. Хранит ТОЛЬКО глобальную роль.
    Роль внутри конкретной группы — в GroupMember."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)   # Telegram ID
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)

    # Активная (выбранная) группа пользователя — что он сейчас смотрит по умолчанию.
    active_group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)

    # ГЛОБАЛЬНАЯ роль: 'user' | 'moderator' | 'admin'.
    # Роли внутри группы (owner/helper/member) лежат в group_members.
    global_role = Column(String(20), nullable=False, default='user')

    subgroup = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    memberships = relationship("GroupMember", back_populates="user")

    def __repr__(self):
        return f"User(id={self.id}, user_id={self.user_id}, first_name='{self.first_name}', global_role='{self.global_role}')"


class GroupMember(Base):
    """Связка пользователь <-> группа с ролью В ЭТОЙ группе.
    Позволяет одному человеку быть старостой одной группы и обычным членом другой."""
    __tablename__ = 'group_members'

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)

    # Роль в группе: 'owner' (староста) | 'helper' (помощник) | 'member' (обычный).
    group_role = Column(String(20), nullable=False, default='member')

    subgroup = Column(String(10), nullable=True)   # подгруппа внутри этой группы
    joined_at = Column(DateTime, default=datetime.now)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")

    def __repr__(self):
        return f"GroupMember(group_id={self.group_id}, user_id={self.user_id}, role='{self.group_role}')"


class Invite(Base):
    """Пригласительная ссылка. Два типа:
    - 'create_group' — одноразовая, ты выдаёшь старосте на создание группы;
    - 'join_group'   — многоразовая, староста раздаёт одногруппникам."""
    __tablename__ = 'invites'

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    invite_type = Column(String(20), nullable=False)   # 'create_group' | 'join_group'

    # Для join_group — в какую группу ведёт.
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    # Для create_group — к какому заведению привязать новую группу (опционально).
    institution_id = Column(Integer, ForeignKey('institutions.id'), nullable=True)

    created_by = Column(BigInteger, nullable=True)     # кто выпустил ссылку
    is_single_use = Column(Boolean, default=True)      # одноразовая?
    max_uses = Column(Integer, nullable=True)          # лимит использований (None = без лимита)
    uses_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"Invite(code='{self.code}', type='{self.invite_type}', active={self.is_active})"


class Homework(Base):
    __tablename__ = 'homeworks'

    id = Column(Integer, primary_key=True)

    # Главное изменение для масштабирования: ДЗ принадлежит конкретной группе.
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=False)

    subject = Column(String(100), nullable=False)
    task = Column(Text, nullable=False)
    date_for = Column(Date, nullable=False)

    # ДЗ адресовано конкретной подгруппе (None -> всей группе).
    subgroup = Column(String(10), nullable=True)

    created_by = Column(BigInteger, nullable=True)     # кто добавил (для истории/модерации)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True)
    attachment_file_id = Column(String(255), nullable=True)
    attachment_type = Column(String(20), nullable=True)

    group = relationship("Group", back_populates="homeworks")

    def __repr__(self):
        return f"Homework(id={self.id}, subject='{self.subject}', group_id={self.group_id}, date_for='{self.date_for}')"
