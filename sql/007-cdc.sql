create schema cdc;
grant all on schema cdc to pypi_scraper;

create user cdc_user with password 'password';
grant select update on all tables in schema cdc to cdc_user;

create table if not exists cdc.event_log (
    "event_id" bigserial primary key,
    "operation" text not null,
    "schema" text not null,
    "table" text not null,
    "before" json,
    "after" json,
    "timestamp" timestamp not null default now()
);

create table if not exists cdc.offsets (
    "table" text not null,
    "event_id" bigint not null
);

alter table cdc.offsets
    add unique ("table");

create or replace function cdc.event_log_insert_tr()
    returns trigger as $body$
    begin
        insert into cdc.event_log (
            "operation",
            "schema",
            "table",
            "before",
            "after"
        ) values (
            tg_op::text,
            tg_table_schema::text,
            tg_table_name::text,
            row_to_json(old),
            row_to_json(new)
        );

        if tg_op = 'DELETE' then
            return old;
        else
            return new;
        end if;
    end;
$body$ language plpgsql;

-- Not currently needed.
-- create or replace trigger cdc_event_log_insert
--     before insert or update or delete
--     on pypi_packages.package_names
--     for each row
--     execute function cdc.event_log_insert_tr();

create or replace trigger cdc_event_log_insert
    before insert or update or delete
    on pypi_packages.versions
    for each row
    execute function cdc.event_log_insert_tr();

-- Not currently needed.
-- create or replace trigger cdc_event_log_insert
--     before insert or update or delete
--     on pypi_packages.distributions
--     for each row
--     execute function cdc.event_log_insert_tr();

create or replace trigger cdc_event_log_insert
    before insert or update or delete
    on pypi_packages.requirements
    for each row
    execute function cdc.event_log_insert_tr();

-- Not currently needed.
-- create or replace trigger cdc_event_log_insert
--     before insert or update or delete
--     on pypi_packages.candidates
--     for each row
--     execute function cdc.event_log_insert_tr();
