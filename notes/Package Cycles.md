# Package Cycles

Without digging too far into our data to find out how common it is for cyclic dependency chains,
first I wanted to see if it were even possible for this to occur. The simplest case is a package
depending on itself, which is made evident by `ipython` depending on itself in a few cases. In
the case of `ipython`, the "all" extra simply causes the package to depend on itself, with the
rest of the extras specified, but with no version constraint. There are many other packages that
follow this pattern, I just chose `ipython` to demonstrate given its popularity.

```sql
-- This query is based on an older version of the schema where DD's link directly to KV's
select
    kv.package_name, kv.package_version,
    dd.extras, dd.dependency_name, dd.dependency_extras, dd.version_constraint
from known_versions kv join direct_dependencies dd
    on kv.known_version_id = dd.known_version_id
where dd.dependency_name = 'ipython' and kv.package_name = 'ipython'
limit 1;
```

| package_name | package_version | extras         | dependency_name | dependency_extras                                                          | version_constraint |
| ------------ | --------------- | -------------- | --------------- | -------------------------------------------------------------------------- | ------------------ |
| ipython      | 8.24.0          | extra == "all" | ipython         | kernel,nbconvert,black,notebook,parallel,doc,nbformat,qtconsole,matplotlib |                    |


Taking this a step further, I wanted to see if any packages depend on themselves.

```sql
select
    kv.package_name, kv.package_version,
    dd.extras, dd.dependency_name, dd.dependency_extras, dd.version_constraint
from known_versions kv
join version_distributions vd on vd.known_version_id = kv.known_version_id
join direct_dependencies dd on dd.version_distribution_id = vd.version_distribution_id
where dd.dependency_name = kv.package_name
and dd.version_constraint != '';
```

| package_name           | package_version       | extras | dependency_name        | dependency_extras | version_constraint      |
| ---------------------- | --------------------- | ------ | ---------------------- | ----------------- | ----------------------- |
| abstract-webtools      | 0.1.4.37              |        | abstract-webtools      |                   | >=0.1.0                 |
| hackingtools           | 2.2.3                 |        | hackingtools           |                   | ==2.2.3                 |
| hackingtools           | 2.0.9                 |        | hackingtools           |                   | ==2.0.9                 |
| hackingtools           | 2.0.3                 |        | hackingtools           |                   | ==2.0.3                 |
| hackingtools           | 3.0.0                 |        | hackingtools           |                   | ==3.0.0                 |
| hackingtools           | 1.6.8                 |        | hackingtools           |                   | ==1.6.8                 |
| ivystar                | 0.2.3                 |        | ivystar                |                   | <=0.0.4                 |
| masthay-helpers        | 0.2.89                |        | masthay-helpers        |                   | >=0.2.86                |
| mosaik-core-semver     | 2.5.3rc20210917000517 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| mosaik-core-semver     | 2.5.3rc20211207010506 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| mosaik-core-semver     | 2.5.3rc20220207010437 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| mosaik-core-semver     | 2.5.3rc20211105010518 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| mosaik-core-semver     | 2.5.3rc20220415000529 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| mosaik-core-semver     | 2.5.3rc20220110010511 |        | mosaik-core-semver     |                   | >=2.5.2rc20190715231038 |
| openats                | 0.0.dev14             |        | openats                |                   | ==0.0.dev8              |
| repelsec               | 0.3                   |        | repelsec               |                   | ~=0.1                   |
| weverse                | 1.0.7                 |        | weverse                |                   | ~=1.0.6                 |
| youcreep               | 0.1.35                |        | youcreep               |                   | ~=0.1.4                 |
| homebase-calendar-sync | 0.1.9                 |        | homebase-calendar-sync |                   | ==0.1.8                 |

The last entry of this table is really interesting. `homebase-calendar-sync` version 0.1.9 depends
on version 0.1.8 of itself. This version of the package is not installable via pip.

```bash
pip install homebase-calendar-sync==0.1.9
# INFO: pip is looking at multiple versions of homebase-calendar-sync to determine which version is compatible with other requirements. This could take a while.
# ERROR: Cannot install homebase-calendar-sync==0.1.9 because these package versions have conflicting dependencies.

# The conflict is caused by:
#     The user requested homebase-calendar-sync==0.1.9
#     homebase-calendar-sync 0.1.9 depends on homebase-calendar-sync==0.1.8
```

However, `uv pip install homebase-calendar-sync==0.1.9` completes successfully, installing version
0.1.9 of the package. I don't believe that it should work, but I'll hold off on submitting an issue
for now until I'm able to reproduce a less trivial example.
