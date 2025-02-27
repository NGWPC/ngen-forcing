from setuptools import setup, find_packages

setup(
    name="swe_timeseries",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "geopandas",
        "numpy",
        "matplotlib",
        "fsspec",
        "s3fs"
    ],
    python_requires='>=3.8',
)