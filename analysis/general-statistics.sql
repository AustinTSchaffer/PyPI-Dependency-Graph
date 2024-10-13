--
-- Current table sizes with estimate counts
--
select
  table_name,
  reltuples as row_count_estimate,
  pg_size_pretty(pg_total_relation_size('pypi_packages.' || table_name)) as size_pretty,
  pg_total_relation_size('pypi_packages.' || table_name) as size_bytes,
  pg_size_pretty(sum(pg_total_relation_size('pypi_packages.' || table_name)) over()) as total_size_pretty,
  sum(pg_total_relation_size('pypi_packages.' || table_name)) over() total_size
from information_schema.tables
left join pg_class on relname = table_name
where table_schema = 'pypi_packages'
order by row_count_estimate;

--
-- Average num versions per package
--
with cte as (
	select count(*) count_ from known_versions kv group by kv.package_name
) select avg(count_) from cte;

--
-- Distributions per package
--
select
	kv.package_name,
	count(*)
from known_versions kv
join version_distributions vd on kv.known_version_id = vd.known_version_id
group by kv.package_name
order by count(*) desc;

--
-- Distributions per package/version pair
--
select
	kv.package_name,
	kv.package_version,
	count(*)
from known_versions kv
join version_distributions vd on kv.known_version_id = vd.known_version_id
group by kv.package_name, kv.package_version
order by count(*) desc;

--
-- Average num distributions per package.
--
with num_dists_per_package as (
	select
		kv.package_name,
		count(*) count_
	from known_versions kv
	join version_distributions vd on kv.known_version_id = vd.known_version_id
	group by kv.package_name
) select avg(count_) from num_dists_per_package;

--
-- Average num distributions per version.
--
with num_dists_per_version as (
	select
		vd.known_version_id,
		count(*) count_
	from version_distributions vd
	group by vd.known_version_id
) select avg(count_) from num_dists_per_version;

--
-- Percentage of known_versions with processed = true
--
select (
	100.0 *
	(select count(vd.processed)::float from pypi_packages.version_distributions vd where vd.processed = true) /
	(select count(vd.processed)::float from pypi_packages.version_distributions vd)
) as "percentage complete";

--
-- Average size of a metadata file
--
select avg(vd.metadata_file_size)
from version_distributions vd
where vd.processed and vd.metadata_file_size != 0;
