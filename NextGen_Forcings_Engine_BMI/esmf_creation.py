import os
import argparse
from ESMF_Mesh_Domain_Configuration_Production.NextGen_hyfab_to_ESMF_Mesh import convert_hyfab_to_esmf


def create_mesh(cfg: dict):
    """
    Create ESMF Mesh from geopackage file provided by the forcing engine config

    :param cfg: dictionary of forcing engine config parameters
    :param hyfab_name: path to hydrofabric geopackage file (we might move this to the config file)
    """

    # Set the mesh file name based on the hydrofabric file
    #base_geo_name = os.path.splitext(os.path.basename(hyfab_name))[0]
    #mesh_fileName = f"{base_geo_name}_ESMF_Mesh.nc"
    hyfab_name = cfg.geopackage
    mesh_outPath = cfg.geogrid

    # Extract set global paths
    #mesh_outPath = os.path.join("/ngen-app/data/esmf_mesh/", mesh_fileName)

    # Check if the mesh file already exists and skip conversion if it does
    if not os.path.exists(mesh_outPath):
        convert_hyfab_to_esmf(
            hyfab_gpkg=hyfab_name,
            esmf_mesh_output=mesh_outPath
        )
    else:
        print(f"ESMF mesh file already exists at {mesh_outPath}, skipping conversion.")


def main(cfg: dict):
    """
    Main function to parse arguments and create ESMF mesh.

    :param cfg: dictionary of forcing engine config parameters
    """
    parser = argparse.ArgumentParser(description="Create ESMF mesh from hydrofabric geopackage")
    parser.add_argument("hyfab_name", help="Path to hydrofabric geopackage file")
    args = parser.parse_args()

    create_mesh(cfg)


if __name__ == "__main__":
    main()
