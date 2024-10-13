-- Packages that apparently depend on themselves.
select
	kv.package_name, kv.package_version,
	vd.python_version, vd.requires_python, vd.upload_time, vd.yanked,
	dd.extras, dd.dependency_name, dd.dependency_extras, dd.version_constraint
from pypi_packages.direct_dependencies dd
join version_distributions vd on vd.version_distribution_id = dd.version_distribution_id
join known_versions kv on kv.known_version_id = vd.known_version_id
where dd.dependency_name = kv.package_name;
