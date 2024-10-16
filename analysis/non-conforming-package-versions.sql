-- Counts of unparsed package versions vs count of all versions.
select 'non-conforming (count)' as "q", count(*) v from known_versions kv where kv.package_release = '{}'
union select 'all (count)' as "q", count(*) v from known_versions kv;

-- Latest non-conforming package versions
with
	non_conforming_versions as (
		select
			known_version_id,
			package_name,
			package_version
		from known_versions kv
		where kv.package_release = '{}'
	)
select
	package_name,
	package_version,
	max(vd.upload_time) max_upload_time
from non_conforming_versions ncv
left join version_distributions vd on ncv.known_version_id = vd.known_version_id
group by package_name, package_version
order by max_upload_time desc nulls last;

-- 
update known_versions
set package_release_numeric = string_to_array(package_version, '.')::numeric[]
where package_release = '{}'
and package_version ~ '^\d+(\.\d+)*$';
