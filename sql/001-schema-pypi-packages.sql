create schema pypi_packages;
grant all on schema pypi_packages to pypi_scraper;

create table pypi_packages.known_package_names (
    package_name text not null primary key,
    date_discovered timestamp not null default now()
);

create table pypi_packages.known_versions (
    known_version_id uuid not null default gen_random_uuid() primary key,
    package_name text not null,
    package_version text not null,
    package_release integer[] not null,
    python_version text not null,
    requires_python text,
    upload_time timestamp not null,
    yanked boolean not null,
    package_filename text not null,
    package_url text not null,
    processed boolean not null default false
);

alter table pypi_packages.known_versions
    add unique (package_filename);

alter table pypi_packages.known_versions
    add foreign key (package_name)
    references pypi_packages.known_package_names (package_name)
    on delete cascade;

create index package_name
    on pypi_packages.known_versions
    using btree
    (package_name);

create index unprocessed_versions
    on pypi_packages.known_versions
    using btree
    (processed)
    where processed = false;

create table pypi_packages.direct_dependencies (
    known_version_id uuid not null,
    extras text,
    dependency_name text not null,
    dependency_extras text null,
    version_constraint text not null
);

alter table pypi_packages.direct_dependencies
    add unique (known_version_id, extras, dependency_name, dependency_extras);

alter table pypi_packages.direct_dependencies
    add foreign key (known_version_id)
    references pypi_packages.known_versions (known_version_id)
    on delete cascade;

create index known_version_id
    on pypi_packages.direct_dependencies
    using btree
    (known_version_id);

create index dependency_name
    on pypi_packages.direct_dependencies
    using btree
    (dependency_name);
