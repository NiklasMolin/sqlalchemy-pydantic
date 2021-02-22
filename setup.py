from setuptools import find_packages, setup


setup(
    name="SQLALCHEMY-PYDANTIC",
    version="0.0.7",
    plat_name="",
    packages=[ *find_packages(
        include=[
            "sp"
        ]
    )],
    url="https://https://github.com/NiklasMolin/sqlalchemy-pydantic",
    entry_points={
        "console_scripts": [
        ]
    },
    package_data={".":["*.py"]},
)
