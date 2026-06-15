import argparse
from pathlib import Path
from types import SimpleNamespace

import yaml
from NextGen_Forcings_Engine.core.config import ConfigOptions

from ESMF_Mesh_Domain_Configuration_Production.NextGen_hyfab_to_ESMF_Mesh import (
    convert_hyfab_to_esmf,
)


def create_mesh(cfg: ConfigOptions):
    """Create ESMF Mesh from geopackage file provided by the forcing engine config.

    :param cfg: Object with attributes:
                - geopackage: path to hydrofabric geopackage file
                - geogrid: path to desired ESMF mesh output file
    """
    # Set the mesh file name based on the hydrofabric file
    hyfab_name = cfg.geopackage
    mesh_out_path = Path(cfg.geogrid)

    # Check if the mesh file already exists and remake if it does.
    # The remake is necessary to ensure the same true catchment IDs will be generated.
    if mesh_out_path.is_file():
        mesh_out_path.unlink()
    return convert_hyfab_to_esmf(hyfab_gpkg=hyfab_name, esmf_mesh_output=mesh_out_path)


def main():
    """Create ESMF mesh from hydrofabric geopackage.

    Main function to parse arguments and create ESMF mesh.

    :param cfg: path to dictionary of forcing engine config parameters
    """
    parser = argparse.ArgumentParser(
        description="Create ESMF mesh from hydrofabric geopackage"
    )
    parser.add_argument("cfg", help="Path to YAML config file")
    args = parser.parse_args()

    # Load Yaml into dict
    with open(args.cfg, "r") as f:
        cfg_dict = yaml.safe_load(f)

    # Wrap config dict into simplenamespace to match ConfigOptions format
    cfg = SimpleNamespace(
        geopackage=cfg_dict["Geopackage"], geogrid=cfg_dict["GeogridIn"]
    )

    # Run mesh creation
    create_mesh(cfg)


if __name__ == "__main__":
    main()
