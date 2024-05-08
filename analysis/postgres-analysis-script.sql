with table_sizes as (
	select
	  table_name,
	  pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size_pretty,
	  pg_total_relation_size(quote_ident(table_name)) as size_bytes
	from information_schema.tables
	where table_schema = 'pypi_packages'
)
select
	t."table",
	t."count" as "rows",
	ts.size_pretty,
	ts.size_bytes
from (
	select 1 as "idx", 'known_package_names' as "table", count(*) from pypi_packages.known_package_names kpn
	union
	select 2 as "idx", 'known_versions' as "table", count(*) from pypi_packages.known_versions kv
	union
	select 3 as "idx", 'direct_dependencies' as "table", count(*) from pypi_packages.direct_dependencies dd
) t
left join table_sizes ts on ts.table_name = t."table"
order by t.idx;

--
-- Packages without any versions.
--
select * from known_package_names kpn
left join known_versions kv on lower(kv.package_name) = lower(kpn.package_name)
where kv.known_version_id is null;

select * from known_versions where package_name ilike 'cython';

--
-- Case-insensitive duplicate package names.
--
select lower(package_name), count(*) c
from known_package_names kpn
group by lower(package_name)
having count(*) > 1;

--
-- Percentage of known_versions with processed = true
--
select (
	100.0 *
	(select count(*)::float from pypi_packages.known_versions kv where kv.processed = true) /
	(select count(*)::float from pypi_packages.known_versions kv)
) as "percentage complete";

select * from pypi_packages.known_package_names kpn order by date_discovered; 
select * from pypi_packages.direct_dependencies dd;
select * from pypi_packages.known_versions kv where kv.known_version_id = '1cbe2091-0fb0-4c6a-9919-e014de526dc9';

--
-- Determining the set of package_name/version combinations which depend on dependency_name
--
select
	count(*) over(),
	kv.package_name,
	kv.package_version,
	kv.requires_python,
	dd.extras,
	dd.dependency_name,
	dd.dependency_extras,
	dd.version_constraint,
	kv.package_filename
from pypi_packages.direct_dependencies dd
join pypi_packages.known_versions kv on dd.known_version_id = kv.known_version_id
where dd.dependency_name = 'grpcio';

--
-- Propagate newly discovered package names back into known_package_names
--
insert into known_package_names (package_name)
select distinct dependency_name from pypi_packages.direct_dependencies
on conflict do nothing;

