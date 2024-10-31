alter function parse_specifier_set set search_path = pypi_packages, public;
alter role pypi_scraper set search_path = pypi_packages, public;
alter database defaultdb set search_path = pypi_packages, public;
