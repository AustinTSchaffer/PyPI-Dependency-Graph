-- Due to the relationship between packages-versions-distributions, each
-- distribution of a package version has a slightly different upload time.
-- Most distributions of a version are uploaded within a few minutes of each other.
-- Some versions have distributions with upload times spanning multiple years (4000+ days!!!)
-- We call this "version distribution lag".

-- Biggest Lag
select
	kv.package_name,
	kv.package_version,
	count(kv.known_version_id),
	min(upload_time) min_upload_time,
	max(upload_time) max_upload_time,
	max(upload_time) - min(upload_time) upload_time_diff
from pypi_packages.version_distributions vd
join pypi_packages.known_versions kv on vd.known_version_id = kv.known_version_id
group by kv.known_version_id
order by upload_time_diff desc
limit 100;

-- Most distributions for a single version
select
	kv.package_name,
	kv.package_version,
	count(kv.known_version_id),
	min(upload_time) min_upload_time,
	max(upload_time) max_upload_time,
	max(upload_time) - min(upload_time) upload_time_diff
from pypi_packages.version_distributions vd
join pypi_packages.known_versions kv on vd.known_version_id = kv.known_version_id
group by kv.known_version_id
order by count(kv.known_version_id) desc
limit 100;
