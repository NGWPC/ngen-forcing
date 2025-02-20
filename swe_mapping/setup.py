from setuptools import setup, find_packages

setup(
    name="swe_mapping",
    packages=find_packages(),
    install_requires=[
        'xarray',
        'matplotlib',
        'cartopy',
        'numpy',
        'geopandas',
        'shapely',
        'fsspec',
        'pandas'  
    ],
)
