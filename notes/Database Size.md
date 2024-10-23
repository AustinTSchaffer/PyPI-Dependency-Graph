# Estimate on Database Size

## In Practice...

In practice, extracting metadata from all Wheel metadata files on PyPI ended up
creating a database sized at around 20GB. I'm not sure how the math was so wrong,
but here's the mathematics I originally did:

## Mathematics

With the current schema, at this present moment. Here's the DB stats.

| table               | rows    | size_pretty | size_bytes |
|---------------------|---------|-------------|------------|
| package_names |    2936 | 368 kB      |     376832 |
| versions      |  477995 | 247 MB      |  258850816 |
| requirements | 2185832 | 455 MB      |  476807168 |

- Current num packages on PyPI: $530,000$
- Percentage of packages discovered:
  - $=2936/530000$
  - $=0.00554$
  - $\approx 0.55\%$
- Approximate full size of `package_names`
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
- Estimate full size of `requirements`
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
- Estimate full size of `versions`
  - $=86,390,000 * 542 \space\text{B}$
  - $=46,823,380,000 \space\text{B}$
  - $=46 \space\text{GB}$
- Total space required (2024)
  - $\ge 46 \space\text{GB} + 322 \space\text{GB}$
  - $\ge 400 \space\text{GB}$

Conclusion, totally doable.
