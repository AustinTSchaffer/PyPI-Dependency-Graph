# Non-Conforming Package Versions

Part of the package name processor involves storing all of the "known versions" of a particular
package. A piece of that process involves parsing the package's version number using the
`packaging` module. Specifically, using the `packaging.version.parse` method.

```python
try:
    parsed_version = packaging.version.parse(known_version.package_version)
    for release_term in parsed_version.release:
        if release_term > constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
            raise ValueError(
                f"{package_name.package_name} - Version {known_version.package_version} contains a term larger than {constants.PACKAGE_RELEASE_TERM_MAX_SIZE}"
            )

    known_version.package_release = parsed_version.release
except Exception as ex:
    logger.error(
        f"{package_name.package_name} - Error parsing version {known_version.package_version}.",
        exc_info=ex,
    )
```

The intent of this is to break each version string down into an array of integers, so that
it's easier for non-python processes (e.g. Postgres) to filter a list of version strings
based on some version range.

```sql
select
	kv.package_name,
	kv.package_version
from known_versions kv
where
	kv.package_name = 'boto3'
	and (
		kv.package_release >= '{1, 34, 123}' and 
		kv.package_release < '{1, 35}'
	)
order by kv.package_release;
```

One of the issues with this approach is that [PEP-440](https://peps.python.org/pep-0440/) and
[PyPA](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-specifiers)
are pretty strict about the formatting of a version string, but PyPI seems to allow arbitrary
versions strings with no validation. As a result, our scripts have collected thousands of
non-conforming version strings, where the version string has failed validation in one way or
another. Just to illustrate a few examples:

| package name        | version string   |
| ------------------- | ---------------- |
| h5py                | `1.3.0.dev-r634` |
| pytz                | `2004d`          |
| yapsy               | `1.9.0-python3`  |
| ics                 | `indev`          |
| plexapi             | `0.1-`           |
| django-haystack     | `1.0.0-final`    |
| pypi                | `2004-03-01`     |
| zope-lifecycleevent | `3.4dev-r72934`  |

In many of these cases, a version number was clearly attempted, but none are natively parsable.
This presents a problem, since the version strings are non-conformant, they're not parsable
by the normal means, so we can't filter them using the SQL methodology presented above.

Across all of the version strings present on PyPI so far (October 2024), approximately 0.08%
of them are not natively parsable.

```sql
select 'non-conforming' as "q", count(*) from known_versions kv where kv.package_release = '{}'
union select 'all' as "q", count(*) from known_versions kv;

-- all            6222702
-- non-conforming    5129
```

One example that shows up a lot in this list of non-conforming package version strings is
`pytz`. Many versions of this package are formateed as a year with a letter suffix. Using 
version `2004d` of this package as an example:

- `pip install pytz==2004d` fails with an "Invalid requirement" error, since `pip` is not able to
  parse `2004d` as a 
- `install 'pytz>=2004,<2005'` fails too, stating that it could not find a version that satisfies
  the requirement. Looking at the list of versions returned in the console output, `2004d` doesn't
  show up.
- `uv` also fails to install this package version.

```bash
pip install pytz==2004d
# ERROR: Invalid requirement: 'pytz==2004d': Expected end or semicolon (after version specifier)
#     pytz==2004d
#         ~~~~~~^

pip install 'pytz>=2004,<2005'
# ERROR: Could not find a version that satisfies the requirement pytz<2005,>=2004 (from versions: 2004a0, 2004b0, 2004b2, 2005a0, 2005.post0, 2007rc0, 2008a0, 2008b0, 2008rc0, 2009a0, 2009.post0, 2010b0, 2011b0, 2011rc0, 2012b0, 2012rc0, 2013b0, 2013.6, 2013.7, 2013.8, 2013.9, 2014.1, 2014.1.1, 2014.2, 2014.3, 2014.4, 2014.7, 2014.9, 2014.10, 2015.2, 2015.4, 2015.6, 2015.7, 2016.1, 2016.2, 2016.3, 2016.4, 2016.6, 2016.6.1, 2016.7, 2016.10, 2017.2, 2017.3, 2018.3, 2018.4, 2018.5, 2018.6, 2018.7, 2018.9, 2019.1, 2019.2, 2019.3, 2020.1, 2020.4, 2020.5, 2021.1, 2021.3, 2022.1, 2022.2, 2022.2.1, 2022.4, 2022.5, 2022.6, 2022.7, 2022.7.1, 2023.2, 2023.3, 2023.3.post1, 2023.4, 2024.1, 2024.2)
# ERROR: No matching distribution found for pytz<2005,>=2004
```

It's still possible to install this version of this package.
