-- Counts of unparsed package versions vs count of all versions.
select 'non-conforming (count)' as "q", count(*) v from versions kv where kv.package_release = '{}'
union select 'all (count)' as "q", count(*) v from versions kv;

-- Latest non-conforming package versions
with
	non_conforming_versions as (
		select
			version_id,
			package_name,
			package_version
		from versions kv
		where kv.package_release = '{}'
	)
select
	package_name,
	package_version,
	max(vd.upload_time) max_upload_time
from non_conforming_versions ncv
left join distributions vd on ncv.version_id = vd.version_id
group by package_name, package_version
order by max_upload_time desc nulls last;
