create schema cdc;
grant all on schema cdc to pypi_scraper;

create user cdc_user with password 'password';
grant select update on all tables in schema cdc to cdc_user;

create table if not exists cdc.event_log (
    "event_id" bigserial primary key,
    "operation" text not null,
    "schema" text not null,
    "table" text not null,
    "before" jsonb,
    "after" jsonb,
    "timestamp" timestamp not null default now()
);

create table if not exists cdc.offsets (
    "schema" text not null,
    "table" text not null,
    "event_id" bigint not null
);
