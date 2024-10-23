# Platform Selection

This document is scoped to the decisions that pip makes when deciding which variant of a wheel to download.

One of the challenges pip has when choosing to download a package is that it needs to look at a list of
distributions of the package and choose the "best" one. There are many different factors that pip considers
when combing through distributions, but the top criterion are:

- Wheels are preferred
- The latest version of the package is preferred
- The python version and platform must be compatible with the system

Looking at our dataset, one stress-test that we can perform would be to make pip comb through the distributions
for a package which has the most number of distributions per version. If you sort unique package name/version
pairs by the number of distributions, the top 9 ([1](#footnotes)) packages are listed below.

```sql
select kv.package_name, kv.package_version, count(*) c
from pypi_packages.distributions vd
join pypi_packages.versions kv on vd.version_id = kv.version_id
group by kv.version_id
order by count(*) desc;
```

| package name              | version | num distributions |
| ------------------------- | ------- | ----------------- |
| google-re2                | 1.1     | 307               |
| cmeel-eigen               | 3.4.0.1 | 173               |
| simple-manylinux-demo     | 3.0     | 171               |
| simple-manylinux-demo     | 4.0     | 168               |
| pyromark                  | 0.5.0   | 158               |
| mkdocs-minify-html-plugin | 0.2.3   | 158               |
| lxml                      | 5.2.1   | 154               |
| pin                       | 2.6.12  | 154               |
| just-playback             | 0.1.8   | 147               |

`google-re2` is clearly the winner here, and the verbose pip installation logs are included in this repository:
[analysis/logs/pip-install-google-re2-verbose.linux-container.arm64.log](../analysis/logs/pip-install-google-re2-verbose.linux-container.arm64.log)

From this test, we can see that pip

1. listed all 745 of the distributions from `google-re2`'s simple index
2. Filtered the list of distributions
   1. For wheels
      1. parsed all of the wheel filenames to get the list of platform tags for each wheel
      2. compared all of those platform tags to the list of platform tags that were supported by the environment ([2](#footnotes))
   2. For sdists, pip filters the sdists based on the required python version ([3](#footnotes)).
3. attempted installing the latest wheel matching that filter. Notably, it looks like pip did sort this list by
   preference after filtering, because the wheel was not the last link in the list returned by the simple index.

## Footnotes

1. The top 9 were picked because there were 6 versions of `pyromark` and 3 versions of `mkdocs-minify-html-plugin`
   that were tied for 10th place, each with 143 distributions.
2. The supported environment tags can be retrieved using `pip debug --verbose`. The output of that command in that
   scenario is included here: [analysis/logs/pip-debug-verbose/linux-container.aarch64.py312.log](../analysis/logs/pip-debug-verbose/linux-container.aarch64.py312.log).
3. Somehow, PyPI has basic python requirements for sdists. This information is in the distribution's PKG-INFO file, but it's not in
   the link's URL, so it's not obvious how that information is ingested on the backend. It's exposed to `pip` when you pass
   the `Accept: application/vnd.pypi.simple.v1+json` request header. You can also see that information for the sdist distributions via
   the "legacy JSON" API: https://pypi.org/pypi/google-re2/json. We've thankfully already ingested this information from the JSON API
   into our database. At any rate, this information is clearly not required. For those sdists, I assume pip will try installing it
   blindly assuming that it's compatible.
