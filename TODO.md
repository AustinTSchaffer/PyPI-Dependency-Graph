# TODO

- Switch from the legacy API to the simple index API. We just need to pass request header `Accept: application/vnd.pypi.simple.v1+json` in order to get enriched output.
- 
- Currently not parsing platform compatibility from filenames.
  - Have a process for parsing that info from filenames of wheels.
  - The file that those methods live in doesn't process `.egg` files.
- Need to do some analysis to see how much version information changes between different "version metadata"
- Tons of documentation
  - Method-level and class-level docstrings
  - Architecture diagram
- Unit tests

```py
# TODO: Persist this somehow.
# Supports "in" operator. `'3.5.2' in python_version_specs`
python_version_specs = (
    packaging.specifiers.SpecifierSet(distribution['requires_python'])
    if distribution['requires_python'] is not None else
    None
)

# TODO: Use this for persisting platform info.
_, _, _, version_tag_info = packaging.utils.parse_wheel_filename(distribution['filename'])
# Doesn't support .egg files. Probably don't need them anyway.
```
