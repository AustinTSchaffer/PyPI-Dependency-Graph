create schema pypi_packages;
grant all on schema pypi_packages to pypi_scraper;

--
-- pypi_packages.known_package_names
--
create table pypi_packages.known_package_names (
    package_name text not null primary key,
    date_discovered timestamp not null default now(),
    date_last_checked timestamp null
);

--
-- pypi_packages.known_versions
--
create table pypi_packages.known_versions (
    known_version_id uuid not null default gen_random_uuid() primary key,
    package_name text not null,
    package_version text not null,
    date_discovered timestamp not null default now(),

    epoch bigint null,
    package_release bigint[] null,
    pre_0 text null,
    pre_1 bigint null,
    post bigint null,
    dev bigint null,
    "local" text null,
    is_prerelease boolean null,
    is_postrelease boolean null,
    is_devrelease boolean null
);

alter table pypi_packages.known_versions
    add unique (package_name, package_version);

alter table pypi_packages.known_versions
    add foreign key (package_name)
    references pypi_packages.known_package_names (package_name)
    on delete cascade;

create index
    on pypi_packages.known_versions
    using btree
    (package_name);

--
-- pypi_packages.version_distributions
--
create table pypi_packages.version_distributions (
    version_distribution_id uuid not null default gen_random_uuid() primary key,
    known_version_id uuid not null,
    package_type text not null,
    python_version text not null,
    requires_python text,
    upload_time timestamp not null,
    yanked boolean not null,
    package_filename text not null,
    package_url text not null,
    metadata_file_size int null,
    processed boolean not null default false
);

create index
    on pypi_packages.version_distributions
    using btree
    (processed)
    where processed = false;

alter table pypi_packages.version_distributions
    add foreign key (known_version_id)
    references pypi_packages.known_versions (known_version_id)
    on delete cascade;

create index
    on pypi_packages.version_distributions
    using btree
    (known_version_id);

alter table pypi_packages.version_distributions
    add unique (package_url);

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
    references pypi_packages.version_distributions (version_distribution_id)
    on delete cascade;

create index
    on pypi_packages.direct_dependencies
    using btree
    (version_distribution_id);

create index
    on pypi_packages.direct_dependencies
    using btree
    (dependency_name);
