from setuptools import find_packages, setup


setup(
    name="app",
    version="1.0.2",
    plat_name="",
    packages=[ *find_packages(
        include=[
            "app"
        ]
    )],
    url="https://stash.int.klarna.net/projects/DPF/repos/alps-core/browse",
    entry_points={
        "console_scripts": [
        ]
    },
    package_data={".":["*.py"]},
)
