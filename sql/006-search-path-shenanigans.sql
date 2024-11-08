alter role pypi_scraper in database defaultdb set search_path = pypi_packages, pg_catalog, public;
alter database defaultdb set search_path = pypi_packages, pg_catalog, public;
