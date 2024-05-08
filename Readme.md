# Python Package Dependency Graph

Project goal: catalogue the dependency chain for all versions of all* packages.

\* This requirement will likely be revised.

My hypothesis is that you can dramatically speed up package version resolution, especially in a few hand-crafted failure cases. Such failure cases include fairly innocuous-looking pip install commands:

- `pip install 'z3-solver<4.11' crosshair-tool`
- `pip install boto3 botocore==1.23.54"`

The reason why I believe these can be improved is because there's no reverse-dependency information available anywhere online. Essentially, each version of `boto3` knows which versions of `botocore` it depends on, but neither `botocore` nor PyPI know which versions of `boto3` depend on specific versions of `botocore`.

## TODO

- Split the `main.py` file into discrete components. Currently it's a spaghetti mess.
- Need to parallelize this process
  - Celery might be a good option for the Python process.
  - Unclear what streaming backends are supported by Celery. RabbitMQ might be a good option.
- Are the postgres indexes sufficient? Over-engineered?
- Currently not parsing platform compatibility from wheel filenames.
  - Issue being related to the parsing script not handling `.egg` files.
- Missing an automatic feedback mechanism for newly discovered package names. Currently running a SQL script manually, then rerunning the process.
- Need to write some estimates on how big this database will end up.
  - Average number of versions per package.
  - Average number of dependencies per version.
  - Average number of storage bytes required per package? Might not need the answer to the previous bullets for calculating this metric.
  - Multiply this value by the number of packages on PyPI.
