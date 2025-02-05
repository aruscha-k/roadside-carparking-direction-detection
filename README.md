# Create an environment like so:
```bash
conda create --name cut_parkplatz_data python=3.10 --file requirements_conda.txt
conda activate cut_parkplatz_data
pip install -r requirements.txt
```

# Information
This repository contains the code to evaluate street view and True DOP images concerning the parking type of cars to classify the parking type for a street. It requires a PostgreSQL database with PostGIS extension to be installed and linked in the config files. Further needed data is explained below. Currently the street view images need to be by the company 'cyclomedia'. If these are not available the code will also work with orthophotos only, just disable the extraction of streetview images and set image_type to "air".
Disclaimer: due to the data coming from German cities, most of the properties are in German language, please excuse this.

# File descriptions

## db_config.json
Information for connection to (local/external) PostgreSQL database (with postgis extension)

## db_schema.json
All tables that are initially created to read city data by python file "create_db_schema.py". In this file the DB schema is definded as json.


# How to run
1. Needed files: fileformat see below
   1. [spatial files for street segmentation](https://cloud.scadsai.uni-leipzig.de/index.php/s/HY4oEWz42C3mQsT) - pw: parking-sdsc24
      1. strassensegmente.json
      2. trafficareas.json
      3. suburbs.json
   2. images files
      1. [air-imgs per suburb](https://opendata.leipzig.de/dataset/luftbild-2022-stadt-leipzig) remark: our networks were trained on a resolution of 10cm/px, the openly available data is 20cm/px
      2. cyclomedia /street view images are downloaded in the process
   3. model files - *models had to be removed due to copyright on the files they were trained on*
      1. object detection model for air images
      2. object detection model for streetview images
      3. detection model for driveways (not implemented in this version)
2. Maybe needed: data preprocessing
3. Install dependencies:
   1. Postgresql DB with postgis extension (locally: https://postgresapp.com)
   2. Flask (for frontend)
   3. Python Libraries in requierements.txt
4. Configure all paths in PATH_CONFIGS.py
5. Configure all variables in GLOBAL_VARS.py (e.g.city center)
6. Set mapping: Edit files verkehrsflaechen_testgebiet_mapping.json, strassen_segmente_testgebiet_mapping.json, ortsteile_mapping.json
   1. Set the name of the column in json city data to be read into database
7. Run the Python files in the following order to load all necessary data (or just run RUN.py for execution of all necessary files listed below)
   1. Start pg-admin / Database
   2. RUN create_db_schema.py
   3. RUN load_city_data.py
   4. Before running the next file, check that postgis is installed or renew installation
      1. DROP EXTENSION IF EXISTS postgis CASCADE;
      2. CREATE EXTENSION postgis SCHEMA public;
      3. RUN create_relations.py
     
# File formats 

#### strassensegmente.json

needed properties:

{"name": "id", "type": "int", "primary key": true, "not null": true},

{"name": "segm_gid", "type": "int"}, (alias to trafficarea)

{"name": "sstrgsname", "type": "text"},

{"name": "laenge_m", "type": "float8"},

{"name": "ot_name", "type": "text"},

{"name": "geom_type", "type": "text"},

{"name": "geom_coordinates", "type": "json"}, coordinates (LineString) of a segment. If lenght > 2 segment is pairwise split in further process

{"name": "geometry", "type": "jsonb"}

### trafficareas

{"name": "id", "type": "int", "primary key": true, "not null": true},

{"name": "segm_gid", "type": "int"},

{"name": "stsa_text", "type": "text"}, (type description zB "Fahrbahn")

{"name": "length_m", "type": "float8"},

{"name": "median_breite", "type": "float8"},

{"name": "geom_type", "type": "text"},

{"name": "geom_coordinates", "type": "json"}

### suburbs

{"name": "ot_nr", "type": "text", "primary key": true, "not null": true},

{"name": "ot_name", "type": "text"},

{"name": "geom_type", "type": "text"},

{"name": "geom_coordinates", "type": "json"},

{"name": "geometry", "type": "jsonb"}
