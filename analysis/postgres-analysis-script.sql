select count(*) from pypi_packages.direct_dependencies dd;
select count(*) from pypi_packages.known_versions kv where kv.processed = false;

select * from pypi_packages.known_package_names kpn order by date_discovered; 

select * from pypi_packages.direct_dependencies dd;

select * from pypi_packages.known_versions kv where kv.known_version_id = '1cbe2091-0fb0-4c6a-9919-e014de526dc9';

select
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
where dd.dependency_name = 'z3-solver';

insert into known_package_names (package_name)
select distinct dependency_name from pypi_packages.direct_dependencies
on conflict do nothing;

select
  table_name,
  pg_size_pretty(pg_total_relation_size(quote_ident(table_name))),
  pg_total_relation_size(quote_ident(table_name))
from information_schema.tables
where table_schema = 'pypi_packages'
order by 3 desc;
