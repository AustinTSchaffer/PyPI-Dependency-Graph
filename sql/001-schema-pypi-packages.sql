create schema pypi_packages;
grant all on schema pypi_packages to pypi_scraper;

--
-- pypi_packages.package_names
--
create table pypi_packages.package_names (
    package_name text not null primary key,
    date_discovered timestamp not null default now(),
    date_last_checked timestamp null
);

--
-- pypi_packages.versions
--
create table pypi_packages.versions (
    version_id uuid not null default gen_random_uuid() primary key,
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

alter table pypi_packages.versions
    add unique (package_name, package_version);

alter table pypi_packages.versions
    add foreign key (package_name)
    references pypi_packages.package_names (package_name)
    on delete cascade;

create index
    on pypi_packages.versions
    using btree
    (package_name);

--
-- pypi_packages.distributions
--
create table pypi_packages.distributions (
    distribution_id uuid not null default gen_random_uuid() primary key,
    version_id uuid not null,
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
    on pypi_packages.distributions
    using btree
    (processed)
    where processed = false;

alter table pypi_packages.distributions
    add foreign key (version_id)
    references pypi_packages.versions (version_id)
    on delete cascade;

create index
    on pypi_packages.distributions
    using btree
    (version_id);

alter table pypi_packages.distributions
    add unique (package_url);

--
-- pypi_packages.requirements
--
create table pypi_packages.requirements (
    distribution_id uuid not null,
    extras text,
    dependency_name text not null,
    dependency_extras text null,
    version_constraint text null
);

alter table pypi_packages.requirements
    add unique (distribution_id, extras, dependency_name, dependency_extras);

alter table pypi_packages.requirements
    add foreign key (distribution_id)
    references pypi_packages.distributions (distribution_id)
    on delete cascade;

create index
    on pypi_packages.requirements
    using btree
    (distribution_id);

create index
    on pypi_packages.requirements
    using btree
    (dependency_name);
