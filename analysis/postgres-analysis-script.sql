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
select count(*) over(), * from known_package_names kpn
left join known_versions kv on lower(kv.package_name) = lower(kpn.package_name)
where kv.known_version_id is null
and kpn.package_name ilike '%zope%';

select distinct package_name from known_versions kv where kv.package_name ilike '%zope%';

select * from known_versions where package_name ilike 'cython';

-- delete from known_package_names kpn where
-- kpn.package_name != lower(regexp_replace(kpn.package_name, '[-_\.]+', '-', 'g'));

--
-- Non-canonicalized duplicate package names.
--

select
	kpn_1.package_name,
	kpn_2.package_name
from known_package_names kpn_1
join known_package_names kpn_2 on
	kpn_1.package_name != kpn_2.package_name and
	lower(regexp_replace(kpn_1.package_name, '[-_\.]+', '-')) = lower(regexp_replace(kpn_2.package_name, '[-_\.]+', '-'));

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

explain analyze
insert into known_package_names (package_name)
	select lower(regexp_replace(subq.dependency_name, '[-_\.]+', '-', 'g')) from (
		select distinct dependency_name from pypi_packages.direct_dependencies
	) subq
on conflict do nothing;

explain analyze
insert into known_package_names (package_name)
	select lower(regexp_replace(subq.package_name, '[-_\.]+', '-', 'g')) cn from (
		select distinct package_name from pypi_packages.known_package_names
	) subq order by cn
on conflict do nothing;

--
-- pycrdt has a freaking ton of versions.
--
select
	count(*) over(),
	*
from known_versions kv
where package_name ilike 'pycrdt'
order by package_release desc;

--
-- Average number of dependencies per known version (only versions that have completed processing).
--

with
	subq as (select dd.known_version_id, count(*) c
		from direct_dependencies dd
		join known_versions kv on kv.known_version_id = dd.known_version_id and kv.processed
		group by dd.known_version_id
	)
select avg(c) from subq;

select * from known_package_names kpn order by date_discovered;
select * from known_versions kv;