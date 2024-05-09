create or replace function pypi_packages.canonicalize_package_name(package_name text)
  	returns text as
	$body$
	begin
		return lower(regexp_replace(package_name, '[-_\.]+', '-', 'g'));
	end;
	$body$
language plpgsql;

create or replace function pypi_packages.canonicalize_package_name_tr()
  	returns trigger as
	$body$
	begin
	   new.package_name = pypi_packages.canonicalize_package_name(new.package_name);
	   return new;
	end;
	$body$
language plpgsql;

create or replace function pypi_packages.canonicalize_dependency_name_tr()
  	returns trigger as
	$body$
	begin
	   new.dependency_name = pypi_packages.canonicalize_package_name(new.dependency_name);
	   return new;
	end;
	$body$
language plpgsql;

create or replace trigger canonicalize_package_name
	before insert or update
	on pypi_packages.known_package_names
	for each row
	execute function pypi_packages.canonicalize_package_name_tr();

create or replace trigger canonicalize_package_name
	before insert or update
	on pypi_packages.known_versions
	for each row
	execute function pypi_packages.canonicalize_package_name_tr();

create or replace trigger canonicalize_dependency_name
	before insert or update
	on pypi_packages.direct_dependencies
	for each row
	execute function pypi_packages.canonicalize_dependency_name_tr();
