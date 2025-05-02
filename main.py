import requests
import geopandas as gpd
import logging
import io
from shapely.geometry import shape
#medina
# Configure logging
logging.basicConfig(level=logging.INFO)

# Load the vector grid into a GeoDataFrame
gdf_grid = gpd.read_file("vrbn_grid_5km_buffer.gpkg")

# Define the WFS base URL
base_url = "https://service.pdok.nl/lv/bag/wfs/v2_0"
# typename = "pand"
# Create an empty GeoDataFrame to hold the combined data for all features
all_combined_gdf = gpd.GeoDataFrame()
def get_bag(typename, all_combined_gdf):
    # Iterate over each feature and extract its bounding box
    for idx, feature in gdf_grid.iterrows():
        # Extract the bounding box (minx, miny, maxx, maxy)
        bbox = feature.geometry.bounds
        minx, miny, maxx, maxy = bbox
        logging.info(f"Processing feature {idx} Bounding Box: minx={minx}, miny={miny}, maxx={maxx}, maxy={maxy}")

        # Define the parameters for the WFS request
        params = {
            "REQUEST": "GetFeature",
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "OUTPUTFORMAT": "application/gml+xml; version=3.2",
            "BBOX": f"{minx},{miny},{maxx},{maxy}",
            "srsName": "EPSG:28992",
            "TYPENAMES": f"bag:{typename}",
            "count": 500  # Number of records per page
        }

        # Initialize a GeoDataFrame to store data for the current feature
        combined_gdf = gpd.GeoDataFrame()

        # Loop to handle paging for WFS requests
        for page in range(1000):  # Set high limit if many pages are expected
            params["startindex"] = page * params["count"]

            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()

                # Use BytesIO to read the response content in-memory
                with io.BytesIO(response.content) as in_memory_file:
                    try:
                        gpd_data = gpd.read_file(in_memory_file, driver='GML', layer=f"{typename}")
                    except Exception as e:
                        logging.error(f"Failed to read data for page {page}: {e}")
                        break

                # Append the new data to the combined GeoDataFrame
                if not gpd_data.empty:
                    combined_gdf = combined_gdf._append(gpd_data, ignore_index=True)
                    logging.info(f"Page {page} data retrieved.")
                else:
                    logging.info(f"No more data found for page {page}. Ending pagination.")
                    break

            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to retrieve data for page {page}: {e}")
                break  # Stop the loop on network errors

        # Add the combined data for the current feature to the main GeoDataFrame
        all_combined_gdf = all_combined_gdf._append(combined_gdf, ignore_index=True)

    # Drop duplicate geometries
    all_combined_gdf.set_geometry('geometry', inplace=True)
    all_combined_gdf = all_combined_gdf.drop_duplicates(subset='geometry', keep='first')

    # Ensure the CRS is set
    if all_combined_gdf.crs is None:
        all_combined_gdf.set_crs("EPSG:28992", allow_override=True, inplace=True)

    # Remove any invalid geometries
    all_combined_gdf = all_combined_gdf[all_combined_gdf.is_valid]
    all_combined_gdf = all_combined_gdf[all_combined_gdf['geometry'].notnull()]

    # Save the combined data for all features to a GeoPackage
    all_combined_gdf.to_file(f"paged_bag_{typename}.gpkg", driver="GPKG")
    logging.info("All data successfully saved to 'combined_bag.gpkg'.")
typename = "pand"
all_combined_gdf = gpd.GeoDataFrame()
get_bag(typename, all_combined_gdf)
all_combined_gdf = gpd.GeoDataFrame()
typename = "verblijfsobject"
get_bag(typename, all_combined_gdf)



# Load the GeoPackage files into GeoDataFrames
verblijfsobject_gdf = gpd.read_file("paged_bag_verblijfsobject.gpkg")
pand_gdf = gpd.read_file("paged_bag_pand.gpkg")


# Perform a spatial join: points (verblijfsobject) within polygons (pand)
joined_gdf = gpd.sjoin(pand_gdf, verblijfsobject_gdf, how="left", predicate="contains")

# Save the result to a new GeoPackage file or inspect it
joined_gdf.to_file("paged_bag.gpkg", driver="GPKG")

# Inspect the result
print(joined_gdf.head())
