# Requirements Specification

In order to start actually linking a package/version/extras with the list of package/version/extras
that the package actually depends on, we need to start breaking out the various text fields of
`requirements` into components.

The first one, each requirement can specify that it depends on optional features of a package
using the "extras" feature.

```sql
select * from requirements r
where
    r.dependency_extras !~ '([a-zA-Z]+,)*[a-zA-Z]+'
    and r.dependency_extras <> ''
;

-- 0 results
```

Finally, a specification that doesn't require a million edge cases. We can easily split dependency_extras
into text arrays.

```sql
with requirement as (
	select r.* from requirements r
	join distributions d on d.distribution_id = r.distribution_id
	join versions v on v.version_id = d.version_id
	where v.package_name = 'boto3' and v.package_version = '1.35.54'
)
select
	r.extras,
	r.dependency_name,
	r.dependency_extras,
	r.version_constraint,
	v.package_version "prospective_version"
from versions v
join requirement r on
	r.dependency_name = v.package_name
	and r.parsable
	and specifier_set_contains(r.specifier_set, parse_version(v.package_version));
```
