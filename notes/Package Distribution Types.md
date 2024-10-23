# Package Distribution Type Identification

https://packaging.python.org/en/latest/specifications/section-distribution-formats/

https://packaging.python.org/en/latest/discussions/package-formats/#egg-format

- Currently using the HTML "simple" index for pulling package names: `pypi.org/simple`
- Currently using the "legacy JSON API" for pulling version and distribution information: `pypi.org/pypi/{name}/json`
- The "simple index" paths provide JSON output when you provide HTML header `Accept: application/vnd.pypi.simple.v1+json`
- The JSON-output has pretty much everything we need, except it doesn't provide package type information
  - We can infer package types from the file extensions of each distribution. However, some information has been lost due to overlaps between the categories.
  - Currently supported package types
    - `bdist_wheel`
      - `.whl` (6,700,000)
      - `.tar.gz` (20)
      - `.zip` (6)
      - `.egg` (2)
    - `sdist`
      - `.tar.gz` (5,400,000)
      - `.zip` (90,000)
      - `.tar.bz2` (3,500)
      - `.tgz` (200)
      - `.rpm` (27)
      - `.egg` (9)
      - `.egg.zip` (7)
      - `.whl` (4)
      - `.deb` (4)
  - Legacy unsupported package types. Unsupported meaning "no longer accepts uploads of this type, but still has available downlods"
    - `bdist_egg`
      - `.egg` (120,000)
      - `.tar.gz` (160)
      - `.zip` (40)
      - `.whl` (3)
      - `.tar.bz2` (1)
      - `.rpm` (1)
    - `bdist_wininst`
      - `.exe` (16,000)
      - `.egg` (1)
      - `.zip` (2)
    - `bdist_dumb`
      - `.tar.gz` (5,585)
      - `.deb` (30)
      - `.zip` (310)
      - `.rpm` (6)
      - `.tar.bz2` (5)
      - `.egg` (2)
      - `.egg.tar.gz` (1)
    - `bdist_msi`
      - `.msi` (580)
      - `.whl` (1)
      - `.egg` (1)
    - `bdist_rpm`
      - `.rpm` (500)
      - `.tar.gz` (4)
      - `.egg` (1)
    - `bdist_dmg`
      - `.dmg` (44)
      - `.egg` (1)


If you look at the PyPI web view for a package which has a legacy format, PyPI reports that the download link is a "Source" distribution (sdist), even when the distribution is definitively _not_ a source distribution. For example, Browshot has an Egg link (`.egg`) and a WinInstaller (`.exe`) link, but both are labeled "Source". https://pypi.org/project/Browshot/#files. PyPI does put them in their own section labelled "Built Distributions", but clearly the interface doesn't have access to metadata which reflects the actual package distribution type.

![Screenshot of the browshot listing on PyPI for posterity, showing various filenames being labelled as Source distributions, when they are definitely something else.](images/browshot.png)

In conclusion, filename extensions are not a reliable method for distinguishing between different package 
types. In fact, filename extensions are never a reliable method for determining the contents of a file.
For the purposes of this project, we need to keep relying on the "legacy JSON" interface for distribution
information in order to not classify Eggs, Win Installers, RPMs, etc as "source dist tarballs".
