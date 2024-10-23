-- Packages that apparently depend on themselves.
select
	kv.package_name, kv.package_version,
	vd.python_version, vd.requires_python, vd.upload_time, vd.yanked,
	dd.extras, dd.dependency_name, dd.dependency_extras, dd.version_constraint
from pypi_packages.requirements dd
join distributions vd on vd.distribution_id = dd.distribution_id
join versions kv on kv.version_id = vd.version_id
where dd.dependency_name = kv.package_name;
