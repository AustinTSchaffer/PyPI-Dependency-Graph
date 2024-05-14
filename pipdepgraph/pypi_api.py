import aiohttp

from pipdepgraph import models

class PypiApi:
    # TODO: How do we want to do this?
    def __init__(self):
        ...

    async def get_package_info(package_name) -> dict[str, list[models.VersionDistribution]]:
        # print(f'Fetching version information for package: {package_name}')
        # package_name = packaging.utils.canonicalize_name(package_name)

        # package_info_resp = await session.get(f'https://pypi.org/pypi/{package_name}/json')

        # if 404...
        # if not package_info_resp.ok:
        #     # if 404
        #     return {}
        #     otherwise raise valueerror
        #     print(f'Bad status code from fetching version information for package {package_name}. Code {package_info_resp.status}. Response:', await package_info_resp.text())
        #     return {}

        # package_info = await package_info_resp.json()
        ...

    async def get_distribution_metadata():
        # metadata_file_resp = await session.get(f"{package_url}.metadata")

        # # TODO: Write this metric to Postgres.
        # print(f"Metadata file size for {package_name}: {metadata_file_resp.content_length} (kvid: {known_version_id})")

        # # TODO: is it possible to parse only the header?
        # metadata_file_text = await metadata_file_resp.text()
        # package_metadata = packaging.metadata.Metadata.from_email(metadata_file_text, validate=False)

        ...
