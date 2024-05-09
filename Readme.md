# Python Package Dependency Graph

Project goal: catalogue the dependency chain for all versions of all* packages.

\* This requirement will likely be revised.

My hypothesis is that you can dramatically speed up package version resolution, especially in a few hand-crafted failure cases. Such failure cases include fairly innocuous-looking pip install commands:

- `pip install 'z3-solver<4.11' crosshair-tool`
- `pip install boto3 "botocore==1.23.54"`

The reason why I believe these can be improved is because there's no reverse-dependency information available anywhere online. Essentially, each version of `boto3` knows which versions of `botocore` it depends on, but neither `botocore` nor PyPI know which versions of `boto3` depend on specific versions of `botocore`.

## TODO

- Split the `main.py` file into discrete components. Currently it's a spaghetti mess.
- Need to parallelize this process
  - Celery might be a good option for the Python process.
  - Unclear what streaming backends are supported by Celery. RabbitMQ might be a good option.
- Are the postgres indexes sufficient? Over-engineered?
- Currently not parsing platform compatibility from filenames.
  - Have a process for parsing that info from .gz filenames.
  - Issue being related to the parsing script not handling `.egg` files.
- Missing an automatic feedback mechanism for newly discovered package names. Currently running a SQL script manually, then rerunning the process.
- Try to create a pypi package loop.
  - A depends on B
  - B depends on A
  - are there any in the wild?

## Estimate on Database Size

With the current schema, at this present moment. Here's the DB stats.

| table               | rows    | size_pretty | size_bytes |
|---------------------|---------|-------------|------------|
| known_package_names |    2936 | 368 kB      |     376832 |
| known_versions      |  477995 | 247 MB      |  258850816 |
| direct_dependencies | 2185832 | 455 MB      |  476807168 |

- Current num packages on PyPI: $530,000$
- Percentage of packages discovered:
  - $=2936/530000$
  - $=0.00554$
  - $\approx 0.55\%$
- Approximate full size of `known_package_names`
  - $=\frac{376832 \space\text{B}}{0.00554}$
  - $=68,020,216 \space\text{B}$
  - $=68 \space\text{MB}$
- Versions per package
  - $=477995/2936$
  - $\approx 163$
- Direct dependencies per package version:
  - $\approx 17.1$ deps per processed known version
  - (See analysis SQL script)
- Bytes per direct dependency
  - $=476807168/2185832$
  - $\approx 218 \text{B}$
- Num direct dependency records across all PyPI
  - $=530000*163*17.1$
  - $=1,477,269,000$
  - **1.48 billion `dd` records**
- Estimate full size of `direct_dependencies`
  - $=1,477,269,000*218 \space\text{B}$
  - $=322,044,642,000 \space\text{B}$
  - $=322 \space\text{GB}$
- Bytes per version record
  - $=258850816/477995$
  - $\approx 542 \space\text{B}$
- Num versions across PyPI
  - $=530000*163$
  - $=86,390,000$
  - **86.4 million `kv` records**
- Estimate full size of `known_versions`
  - $=86,390,000 * 542 \space\text{B}$
  - $=46,823,380,000 \space\text{B}$
  - $=46 \space\text{GB}$
- Total space required (2024)
  - $\ge 46 \space\text{GB} + 322 \space\text{GB}$
  - $\ge 400 \space\text{GB}$

Conclusion, totally doable.
