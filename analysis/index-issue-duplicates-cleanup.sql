select * from pypi_packages.known_versions kv where package_name ilike 'json-spec' order by package_release;

begin;

with dupes as (
	select
		package_name,
		date_discovered,
		date_last_checked
	from (
		select
			*,
			rank() over(partition by package_name order by date_discovered asc) rank_
		from pypi_packages.known_package_names kpn
		where package_name in (
			select
				package_name
			from pypi_packages.known_package_names kpn
			group by package_name
			having count(*) > 1
		)
	) subq
	where subq.rank_ > 1
) delete from pypi_packages.known_package_names kpn
using dupes
where kpn.package_name = dupes.package_name and kpn.date_discovered = dupes.date_discovered;


reindex table pypi_packages.known_package_names;

commit;

delete from pypi_packages.known_versions where package_name ilike 'json-spec';

with dupes as (
	select
		package_name,
		package_version
	from (
		select
			*,
			rank() over(partition by package_name, package_version order by date_discovered asc) rank_
		from pypi_packages.known_versions kv
		where (package_name, package_version) in (
			select
				package_name, package_version
			from pypi_packages.known_versions kv
			group by package_name, package_version
			having count(*) > 1
		)
	) subq
	where subq.rank_ > 1
) delete from pypi_packages.known_package_names kpn
using dupes
where kpn.package_name = dupes.package_name and kpn.date_discovered = dupes.date_discovered;

commit;

reindex table pypi_packages.direct_dependencies;
reindex table pypi_packages.known_versions;
reindex table pypi_packages.version_distributions;
reindex table pypi_packages.direct_dependencies;
