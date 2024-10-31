-- TODO: Overloads of each function.
-- TODO: Consistent variable/function naming.

drop function if exists specifier_equals;
drop function if exists specifier_compatible;
drop function if exists specifier_arbitrary_equals;
drop function if exists specifier_greater;
drop function if exists specifier_greater_or_equal;
drop function if exists specifier_less;
drop function if exists specifier_less_or_equal;

drop function if exists specifier_contains;
drop function if exists specifier_set_contains;

drop function if exists parse_version;
drop function if exists parse_specifier;
drop function if exists parse_specifier_set;

drop function if exists try_cast_bigint;

drop type if exists "version";
drop type if exists "specifier";


create type "version" as (
    "version_string" text,
    "epoch" bigint,
    "package_release" bigint[],
    "pre_0" text,
    "pre_1" bigint,
    "post" bigint,
    "dev" bigint,
    "local" text,
    "is_prerelease" boolean,
    "is_postrelease" boolean,
    "is_devrelease" boolean
);


create type "specifier" as (
    "operator" text,
    "version" text
);


create or replace function try_cast_bigint(
	"value" text,
	"default_" bigint default null
) returns bigint as $body$
begin
  begin
    return "value"::int;
  exception 
    when others then
       return "default_";
  end;
end;
$body$ language plpgsql;


create or replace function
parse_version(
    "version_string" text
) returns version as $body$
declare
    -- This regex was generated by processing the regex from packaging.version:
	-- python -c 'import packaging.version; import re; vp = packaging.version.VERSION_PATTERN; vp = re.sub(r"\?P<[^>]+>", "", vp); vp = re.sub(r"#.+\n", "", vp); vp = re.sub(r"\s+", "", vp); print(f"{chr(39)}^{vp}${chr(39)};")'
    version_pattern text := '^v?(?:(?:([0-9]+)!)?([0-9]+(?:\.[0-9]+)*)([-_\.]?(alpha|a|beta|b|preview|pre|c|rc)[-_\.]?([0-9]+)?)?((?:-([0-9]+))|(?:[-_\.]?(post|rev|r)[-_\.]?([0-9]+)?))?([-_\.]?(dev)[-_\.]?([0-9]+)?)?)(?:\+([a-z0-9]+(?:[-_\.][a-z0-9]+)*))?$';
    pv text[];
	pre_0 text;
	pre_1 bigint;
	post bigint;
	dev bigint;
begin
    pv := regexp_match(version_string, version_pattern);

	pre_0 := (pv)[4];
	pre_1 := try_cast_bigint((pv)[5]);
	post := try_cast_bigint(coalesce((pv)[7], (pv)[9]));
	dev := try_cast_bigint((pv)[12]);

	return (
		version_string,
		try_cast_bigint((pv)[1]),
		regexp_split_to_array((pv)[2], '\.')::bigint[],
		pre_0,
		pre_1,
		post,
		dev,
		(pv)[13],
		dev is not null or pre_0 is not null,
		post is not null,
		dev is not null
	);
end;
$body$ language plpgsql;


create or replace function
parse_specifier(
    "version_specifier" text
) returns "specifier" as $body$
declare
	-- This regex was generated by processing the regex from packaging.specifiers:
	-- python -c 'import packaging.specifiers; import re; op_re = packaging.specifiers.Specifier._operator_regex_str; op_re = re.sub(r"\?P<[^>]+>", "", op_re); op_re = re.sub(r"#.+\n", "", op_re); op_re = re.sub(r"\s+", "", op_re); vers_re = packaging.specifiers.Specifier._version_regex_str; vers_re = re.sub(r"\?P<[^>]+>", "", vers_re); vers_re = re.sub(r"#.+\n", "", vers_re); vers_re = re.sub(r"\s+", "", vers_re); print(f"{chr(39)}\\s*{op_re}{vers_re}\\s*{chr(39)};")'
	specifier_pattern text := '\s*((~=|==|!=|<=|>=|<|>|===))((?:(?<====)\s*[^\s;)]*)|(?:(?<===|!=)\s*v?(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:\.\*|(?:[-_\.]?(alpha|beta|preview|pre|a|b|c|rc)[-_\.]?[0-9]*)?(?:(?:-[0-9]+)|(?:[-_\.]?(post|rev|r)[-_\.]?[0-9]*))?(?:[-_\.]?dev[-_\.]?[0-9]*)?(?:\+[a-z0-9]+(?:[-_\.][a-z0-9]+)*)?)?)|(?:(?<=~=)\s*v?(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)+(?:[-_\.]?(alpha|beta|preview|pre|a|b|c|rc)[-_\.]?[0-9]*)?(?:(?:-[0-9]+)|(?:[-_\.]?(post|rev|r)[-_\.]?[0-9]*))?(?:[-_\.]?dev[-_\.]?[0-9]*)?)|(?:(?<!==|!=|~=)\s*v?(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:[-_\.]?(alpha|beta|preview|pre|a|b|c|rc)[-_\.]?[0-9]*)?(?:(?:-[0-9]+)|(?:[-_\.]?(post|rev|r)[-_\.]?[0-9]*))?(?:[-_\.]?dev[-_\.]?[0-9]*)?))\s*';
	vs text[];
begin
    vs := regexp_match(version_specifier, specifier_pattern);

    return (
        (vs)[1],
        (vs)[3]
    )::"specifier";
end;
$body$ language plpgsql;


create or replace function
parse_specifier_set(
    "specifier_set" text
) returns "specifier"[] as $body$
declare
	spec_set "specifier"[];
begin
    select array_agg(parse_specifier(n))
	into spec_set
    from unnest(string_to_array(specifier_set, ',')) n;

	return coalesce(spec_set, '{}');
end;
$body$ language plpgsql;


create or replace function
specifier_arbitrary_equals(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    return ("specifier")."version" = ("version")."version_string";
end;
$body$ language plpgsql;


create or replace function
specifier_equals(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_compatible(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_less(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_greater(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_less_or_equal(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_greater_or_equal(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    -- TODO:
end;
$body$ language plpgsql;


create or replace function
specifier_contains(
    "specifier" "specifier",
    "version" "version"
) returns boolean as $body$
begin
    if (specifier).operator = '==' then
        return specifier_equals(specifier, "version");
    elsif (specifier).operator = '~=' then
        return specifier_compatible(specifier, "version");
    elsif (specifier).operator = '!=' then
		return not specifier_equals(specifier, "version");
    elsif (specifier).operator = '>' then
        return specifier_greater(specifier, "version");
    elsif (specifier).operator = '<' then
        return specifier_less(specifier, "version");
    elsif (specifier).operator = '>=' then
        return specifier_greater_or_equal(specifier, "version");
    elsif (specifier).operator = '<=' then
        return specifier_less_or_equal(specifier, "version");
    elsif (specifier).operator = '===' then
        return specifier_arbitrary_equals(specifier, "version");
	else
		raise exception 'Unknown specifier operator --> %', (specifier).operator;
    end if;
end;
$body$ language plpgsql;


create or replace function
specifier_set_contains(
    "specifier_set" "specifier"[],
    "version" "version"
) returns boolean as $body$
declare
    _specifier "specifier";
begin
    foreach _specifier in array specifier_set loop
		if not specifier_contains(_specifier, "version") then
			return false;
		end if;
    end loop;

    return true;
end;
$body$ language plpgsql;
