create schema pypi_packages;
grant all on schema pypi_packages to pypi_scraper;

--
-- pypi_packages.known_package_names
--
create table pypi_packages.known_package_names (
    package_name text not null primary key,
    date_discovered timestamp not null default now()
);

--
-- pypi_packages.known_versions
--
create table pypi_packages.known_versions (
    known_version_id uuid not null default gen_random_uuid() primary key,
    package_name text not null,
    package_version text not null,
    package_release integer[] not null,
    date_discovered timestamp not null default now()
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

--
-- pypi_packages.version_distributions
--
create table pypi_packages.version_distributions (
    version_distribution_id uuid not null default gen_random_uuid() primary key,
    known_version_id uuid not null,
    python_version text not null,
    requires_python text,
    upload_time timestamp not null,
    yanked boolean not null,
    package_filename text not null,
    package_url text not null,
    processed boolean not null default false
);

create index unprocessed_versions
    on pypi_packages.version_distributions
    using btree
    (processed)
    where processed = false;

alter table pypi_packages.version_distributions
    add foreign key (known_version_id)
    references pypi_packages.known_versions (known_version_id)
    on delete cascade;

create index known_version_id
    on pypi_packages.direct_dependencies
    using btree
    (known_version_id);

--
-- pypi_packages.direct_dependencies
--
create table pypi_packages.direct_dependencies (
    version_distribution_id uuid not null,
    extras text,
    dependency_name text not null,
    dependency_extras text null,
    version_constraint text null
);

alter table pypi_packages.direct_dependencies
    add unique (version_distribution_id, extras, dependency_name, dependency_extras);

alter table pypi_packages.direct_dependencies
    add foreign key (version_distribution_id)
    references pypi_packages.known_versions (version_distribution_id)
    on delete cascade;

create index version_distribution_id
    on pypi_packages.direct_dependencies
    using btree
    (version_distribution_id);

create index dependency_name
    on pypi_packages.direct_dependencies
    using btree
    (dependency_name);
