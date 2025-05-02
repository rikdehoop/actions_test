import requests
import geopandas as gpd
import logging
import io
from shapely.geometry import shape

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load the vector grid into a GeoDataFrame
gdf_grid = gpd.read_file("vrbn_grid_5km_buffer.gpkg")

# WFS base URL
base_url = "https://service.pdok.nl/lv/bag/wfs/v2_0"

def get_bag(typename: str):
    all_combined_gdf = gpd.GeoDataFrame()

    for idx, feature in gdf_grid.iterrows():
        bbox = feature.geometry.bounds
        minx, miny, maxx, maxy = bbox
        logging.info(f"Processing feature {idx} BBOX: {bbox}")

        params = {
            "REQUEST": "GetFeature",
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "OUTPUTFORMAT": "application/gml+xml; version=3.2",
            "BBOX": f"{minx},{miny},{maxx},{maxy}",
            "srsName": "EPSG:28992",
            "TYPENAMES": f"{typename}",
            "count": 500
        }

        combined_gdf = gpd.GeoDataFrame()

        for page in range(1000):
            params["startindex"] = page * params["count"]

            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()

                with io.BytesIO(response.content) as in_memory_file:
                    try:
                        gpd_data = gpd.read_file(in_memory_file, driver='GML', layer=f"{typename}")
                    except Exception as e:
                        logging.error(f"Failed to read GML data on page {page}: {e}")
                        break

                if not gpd_data.empty:
                    combined_gdf = combined_gdf._append(gpd_data, ignore_index=True)
                    logging.info(f"Retrieved page {page}")
                else:
                    logging.info(f"No more data on page {page}")
                    break

            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed on page {page}: {e}")
                break

        all_combined_gdf = all_combined_gdf._append(combined_gdf, ignore_index=True)

    all_combined_gdf.set_geometry('geometry', inplace=True)
    all_combined_gdf = all_combined_gdf.drop_duplicates(subset='geometry')
    all_combined_gdf = all_combined_gdf[all_combined_gdf.is_valid & all_combined_gdf['geometry'].notnull()]

    all_combined_gdf.set_crs("EPSG:28992", allow_override=True, inplace=True)
    print(all_combined_gdf.head())
    # output_file = f"clipped_{typename}.gpkg"
    # all_combined_gdf.to_file(output_file, driver="GPKG")
    # logging.info(f"Saved output to {output_file}")

# Run it
if __name__ == "__main__":
    get_bag("bag:pand")
