# TODO

- Set up cron for pruning cdc.event_log
- Switch from the legacy API to the simple index API (where appropriate). We just need to pass request header `Accept: application/vnd.pypi.simple.v1+json` in order to get enriched output.
- Currently not parsing platform compatibility from filenames.
  - Have a process for parsing that info from filenames of wheels.
- Need to do some analysis to see how much version information changes between different "version metadata"
- Tons of documentation
  - Method-level and class-level docstrings
  - Architecture diagram
- Unit tests

```py
# TODO: Use this for persisting platform info.
_, _, _, version_tag_info = packaging.utils.parse_wheel_filename(distribution['filename'])
```
