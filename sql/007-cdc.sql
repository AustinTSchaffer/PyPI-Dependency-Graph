create schema cdc;
grant all on schema cdc to pypi_scraper;

create user debezium with password 'password';
grant select on all tables in schema cdc to debezium;
