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

select * from known_package_names kpn order by date_discovered asc;
select count(*) from direct_dependencies dd;

--
-- package types with no dependencies.
--

select distinct package_type
from version_distributions vd
where package_type != 'bdist_wheel';

select
	package_type,
	count(*)
from version_distributions
group by package_type
order by count(*) desc;

select package_type, count(*)
from version_distributions vd
join direct_dependencies dd on dd.version_distribution_id = vd.version_distribution_id
group by package_type;

--
-- Packages without any versions.
--
select count(*) over(), * from known_package_names kpn
left join known_versions kv on kv.package_name = kpn.package_name
where kv.known_version_id is null;

-- delete from known_package_names kpn where
-- kpn.package_name != lower(regexp_replace(kpn.package_name, '[-_\.]+', '-', 'g'));

--
-- Non-canonicalized duplicate package names.
--

select
	kpn.package_name,
	pypi_packages.canonicalize_package_name(kpn.package_name) canonname
from known_package_names kpn
where pypi_packages.canonicalize_package_name(kpn.package_name) != kpn.package_name;

--
-- Percentage of known_versions with processed = true
--
select (
	100.0 *
	(select count(vd.processed)::float from pypi_packages.version_distributions vd where vd.processed = true) /
	(select count(vd.processed)::float from pypi_packages.version_distributions vd)
) as "percentage complete";

select count(*) from pypi_packages.version_distributions vd where vd.processed = false;
select * from pypi_packages.known_versions where package_release = '{}';

--
-- Determining the set of package_name/version combinations which depend on dependency_name
--

select
	count(*) over(),
	kv.package_name,
	kv.package_version,
	vd.requires_python,
	dd.extras,
	dd.dependency_name,
	dd.dependency_extras,
	dd.version_constraint,
	vd.package_filename
from pypi_packages.direct_dependencies dd
join pypi_packages.version_distributions vd on vd.version_distribution_id = dd.version_distribution_id
join pypi_packages.known_versions kv on vd.known_version_id = kv.known_version_id
where dd.dependency_name = 'botocore';

--
-- Propagate newly discovered package names back into known_package_names
--

select distinct dependency_name, count(*) over()
from pypi_packages.direct_dependencies
where dependency_name not in (select package_name from known_package_names);

begin;

insert into pypi_packages.known_package_names (package_name)
select distinct dependency_name from pypi_packages.direct_dependencies
on conflict do nothing;

commit;
rollback;

--
-- Deps of boto3 version 1.2.3
--
select kv.*, vd.*, dd.*
from known_versions kv
left join version_distributions vd on vd.known_version_id = kv.known_version_id
left join direct_dependencies dd on dd.version_distribution_id = vd.version_distribution_id
where
	kv.package_name = 'notebook' and vd.package_type = 'bdist_wheel'
;

--
-- Self-referential package dependencies
--
select
	kv.package_name, kv.package_version,
	vd.python_version, vd.requires_python, vd.upload_time, vd.yanked,
	dd.extras, dd.dependency_name, dd.dependency_extras, dd.version_constraint
from pypi_packages.direct_dependencies dd
join version_distributions vd on vd.version_distribution_id = dd.version_distribution_id
join known_versions kv on kv.known_version_id = vd.known_version_id
where dd.dependency_name = kv.package_name;

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

-- Dep tree for boto3 (WIP)
--with
--latest_versions as (
--	select subq.* from (
--		select
--			*,
--			rank() OVER (PARTITION BY package_name ORDER BY upload_time DESC) as r
--		from known_versions kv
--	) subq
--	where subq.r = 1
--),
--boto3version as (
--	select * from latest_versions kv
--	where kv.package_name = 'boto3'
--)
--select
--	'boto3' as package_name,
--	dd_l1.dependency_name dep_name_l1 ,
--	dd_l2.dependency_name dep_name_l2 ,
--	dd_l3.dependency_name dep_name_l3 ,
--	dd_l4.dependency_name dep_name_l4 ,
--	dd_l5.dependency_name dep_name_l5 ,
--	dd_l6.dependency_name dep_name_l6 --,
--	--dd_l7.dependency_name dep_name_l7
--from direct_dependencies dd_l1
--join boto3version b3v on b3v.known_version_id = dd_l1.known_version_id
--left join latest_versions lv_l1 on lv_l1.package_name = dd_l1.dependency_name
--left join direct_dependencies dd_l2 on lv_l1.known_version_id = dd_l2.known_version_id
--left join latest_versions lv_l2 on lv_l2.package_name = dd_l2.dependency_name
--left join direct_dependencies dd_l3 on lv_l2.known_version_id = dd_l3.known_version_id
--left join latest_versions lv_l3 on lv_l3.package_name = dd_l3.dependency_name
--left join direct_dependencies dd_l4 on lv_l3.known_version_id = dd_l4.known_version_id
--left join latest_versions lv_l4 on lv_l4.package_name = dd_l4.dependency_name
--left join direct_dependencies dd_l5 on lv_l4.known_version_id = dd_l5.known_version_id
--left join latest_versions lv_l5 on lv_l5.package_name = dd_l5.dependency_name
--left join direct_dependencies dd_l6 on lv_l5.known_version_id = dd_l6.known_version_id
----left join latest_versions lv_l6 on lv_l6.package_name = dd_l6.dependency_name
----left join direct_dependencies dd_l7 on lv_l6.known_version_id = dd_l7.known_version_id
--order by package_name, dep_name_l1, dep_name_l2, dep_name_l3, dep_name_l4, dep_name_l5, dep_name_l6 --, dep_name_l7

-- DANGER
-- delete from known_package_names where package_name != 'boto3';
-- update known_package_names set date_last_checked = now() - interval '5 min';

  SELECT blocked_locks.pid     AS blocked_pid,
         blocked_activity.usename  AS blocked_user,
         blocking_locks.pid     AS blocking_pid,
         blocking_activity.usename AS blocking_user,
         blocked_activity.query    AS blocked_statement,
         blocking_activity.query   AS current_statement_in_blocking_process
   FROM  pg_catalog.pg_locks         blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity  ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks         blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
        AND blocking_locks.pid != blocked_locks.pid
    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
   WHERE NOT blocked_locks.granted;

  
--
-- Check for dupes
--
select kpn.*, kv.* from known_package_names kpn
left join known_versions kv on kv.package_name = kpn.package_name
where kv.known_version_id is null;
  
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
where subq.rank_ > 1;

select count(*) from direct_dependencies dd;
-- truncate table pypi_packages.version_distributions cascade;
