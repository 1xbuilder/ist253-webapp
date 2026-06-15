-- =====================================================================
-- Миграция 001: чистая схема под городской уровень
-- Запускать в Supabase -> SQL Editor.
-- ВНИМАНИЕ: дропает старые таблицы users/homeworks. Данные не сохраняются
-- (по согласованию — текущие тестовые данные не нужны).
-- =====================================================================

-- Сносим старое (если было)
drop table if exists homeworks     cascade;
drop table if exists group_members cascade;
drop table if exists invites       cascade;
drop table if exists groups        cascade;
drop table if exists institutions  cascade;
drop table if exists users         cascade;

-- ─────────────────────────────────────────────────────────────────────
-- Учебные заведения
-- ─────────────────────────────────────────────────────────────────────
create table institutions (
    id                   bigserial primary key,
    name                 varchar(200) not null,
    city                 varchar(100),
    schedule_provider    varchar(50),       -- 'omgtu' или NULL (нет API расписания)
    schedule_provider_id varchar(50),
    created_at           timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────────────
-- Группы
-- ─────────────────────────────────────────────────────────────────────
create table groups (
    id                   bigserial primary key,
    institution_id       bigint not null references institutions(id) on delete cascade,
    name                 varchar(100) not null,
    external_schedule_id varchar(50),        -- ID группы во внешнем API (заменяет GROUP_ID=427)
    owner_user_id        bigint,             -- Telegram ID старосты-владельца
    created_at           timestamptz default now()
);
create index idx_groups_institution on groups(institution_id);

-- ─────────────────────────────────────────────────────────────────────
-- Пользователи (только ГЛОБАЛЬНАЯ роль; роль в группе — в group_members)
-- ─────────────────────────────────────────────────────────────────────
create table users (
    id              bigserial primary key,
    user_id         bigint unique not null,  -- Telegram ID
    username        varchar(100),
    first_name      varchar(100) not null,
    last_name       varchar(100),
    active_group_id bigint references groups(id) on delete set null,
    global_role     varchar(20) not null default 'user',  -- 'user' | 'moderator' | 'admin'
    subgroup        varchar(10),
    created_at      timestamptz default now()
);

-- ─────────────────────────────────────────────────────────────────────
-- Членство в группе + роль В ЭТОЙ группе
-- 'owner' (староста) | 'helper' (помощник) | 'member' (обычный)
-- ─────────────────────────────────────────────────────────────────────
create table group_members (
    id         bigserial primary key,
    group_id   bigint not null references groups(id) on delete cascade,
    user_id    bigint not null references users(user_id) on delete cascade,
    group_role varchar(20) not null default 'member',
    subgroup   varchar(10),
    joined_at  timestamptz default now(),
    unique (group_id, user_id)               -- один человек — одна запись на группу
);
create index idx_members_user  on group_members(user_id);
create index idx_members_group on group_members(group_id);

-- ─────────────────────────────────────────────────────────────────────
-- Пригласительные ссылки
-- 'create_group' — одноразовая (ты -> старосте)
-- 'join_group'   — многоразовая (староста -> одногруппникам)
-- ─────────────────────────────────────────────────────────────────────
create table invites (
    id             bigserial primary key,
    code           varchar(32) unique not null,
    invite_type    varchar(20) not null,     -- 'create_group' | 'join_group'
    group_id       bigint references groups(id) on delete cascade,
    institution_id bigint references institutions(id) on delete set null,
    created_by     bigint,
    is_single_use  boolean default true,
    max_uses       integer,
    uses_count     integer default 0,
    is_active      boolean default true,
    expires_at     timestamptz,
    created_at     timestamptz default now()
);
create index idx_invites_code on invites(code);

-- ─────────────────────────────────────────────────────────────────────
-- Домашние задания — теперь принадлежат группе
-- ─────────────────────────────────────────────────────────────────────
create table homeworks (
    id                 bigserial primary key,
    group_id           bigint not null references groups(id) on delete cascade,
    subject            varchar(100) not null,
    task               text not null,
    date_for           date not null,
    subgroup           varchar(10),           -- NULL = всей группе
    created_by         bigint,
    attachment_file_id varchar(255),
    attachment_type    varchar(20),
    created_at         timestamptz default now(),
    updated_at         timestamptz
);
create index idx_homeworks_group_date on homeworks(group_id, date_for);
