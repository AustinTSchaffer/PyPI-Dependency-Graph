-- General info on file sizes, table sizes, processing status, etc.

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
-- Packages with non-compliant version strings
--
select * from pypi_packages.known_versions where package_release = '{}';

select package_name, count(*) from pypi_packages.known_versions
where package_release = '{}'
group by package_name
order by count(*) desc;
