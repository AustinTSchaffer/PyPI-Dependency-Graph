alter table pypi_packages.known_versions rename to version_distributions;

create table pypi_packages.known_versions (
    known_version_id uuid not null default gen_random_uuid() primary key,
    package_name text not null,
    package_version text not null,
    package_release integer[] not null,
    date_discovered timestamp not null default now()
);

alter table pypi_packages.known_versions
    add unique (package_name, package_version);

alter table pypi_packages.known_versions
    add foreign key (package_name)
    references pypi_packages.known_package_names (package_name)
    on delete cascade;

create index known_versions_package_name
    on pypi_packages.known_versions
    using btree
    (package_name);

insert into pypi_packages.known_versions (package_name, package_version, package_release)
select vd.package_name, vd.package_version, vd.package_release
from pypi_packages.version_distributions vd
on conflict do nothing;

alter table pypi_packages.version_distributions
rename column known_version_id to version_distribution_id;

alter table pypi_packages.direct_dependencies
rename column known_version_id to version_distribution_id;

alter table pypi_packages.version_distributions
add column known_version_id uuid null;

alter table pypi_packages.version_distributions
    add foreign key (known_version_id)
    references pypi_packages.known_versions (known_version_id)
    on delete cascade;

update pypi_packages.version_distributions vd
set known_version_id = kv.known_version_id
from pypi_packages.known_versions kv
where
	kv.package_name = vd.package_name and
	kv.package_version = vd.package_version;

select kv.*, vd.*a
from pypi_packages.known_versions kv
join pypi_packages.version_distributions vd
	on vd.known_version_id = kv.known_version_id
order by kv.package_name desc, kv.package_release desc;

alter table pypi_packages.version_distributions
	alter column known_version_id set not null;

alter table pypi_packages.version_distributions	drop column package_name;
alter table pypi_packages.version_distributions	drop column package_version;
alter table pypi_packages.version_distributions	drop column package_release;

alter table pypi_packages.known_package_names
	add column date_last_checked timestamp null;
