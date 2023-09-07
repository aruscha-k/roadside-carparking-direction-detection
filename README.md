# Create an environment like so:
Note for Python 3.10 on M1 / Apple Silicon:
Its best to install the following before trying to setup the conda env
```bash
brew tap homebrew/core
brew install postgresql
brew install libpq
brew install openssl
export PATH="$PATH:$(which pg_config)"
export PATH="$PATH:$(which openssl)"
```

```bash
conda create --name cut_parkplatz_data python=3.10 --file requirements_conda.txt
conda activate cut_parkplatz_data
pip install -r requirements.txt
```


# Installing the Database System Postgis
Following the this guide https://trac.osgeo.org/postgis/wiki/UsersWikiPostGIS3UbuntuPGSQLApt
To install PostgreSQL 14, PostGIS 3.2 and pgRouting 3.4 on Ubuntu

```bash
sudo apt install ca-certificates gnupg
curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/apt.postgresql.org.gpg >/dev/null
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt upgrade
sudo apt install -y postgresql-14 
sudo apt install -y postgresql-14-postgis-3 postgis postgresql-14-pgrouting osm2pgrouting

sudo -u postgres psql
# The following commands are better issued one after another
CREATE DATABASE gisdb;
ALTER DATABASE gisdb SET search_path=public,postgis,contrib;
\connect gisdb;

CREATE SCHEMA postgis;

CREATE EXTENSION postgis SCHEMA postgis;
CREATE EXTENSION postgis_raster SCHEMA postgis;
CREATE  EXTENSION pgrouting SCHEMA postgis;
CREATE USER cut WITH PASSWORD 'get the password from the file in the cloud' CREATEDB;
CREATE DATABASE streets_leipzig;
\c streets_leipzig
CREATE EXTENSION postgis;
\q

sudo nano /etc/postgresql/14/main/postgresql.conf
# change 
# listen_addresses = 'localhost'
# to
# listen_addresses = '0.0.0.0'
# and remove the # in front of the line

# next add the scads lan net and the uni vpn to the allowed hosts in the pg_hba.conf
echo 'host    all             cut             172.26.44.0/22          scram-sha-256' | sudo tee -a /etc/postgresql/14/main/pg_hba.conf
echo 'host    all             cut             172.22.0.0/15           scram-sha-256' | sudo tee -a /etc/postgresql/14/main/pg_hba.conf

# restart postgresql with
sudo systemctl restart postgresql
```

# Seting up DB-Schema
Switch to a client computer with this repo and the conda env installed.
Then run the following command to create the schema in the database.
```bash
python python-scripts/DB_create_db_schema.py
python python-scripts/DB_create_relations.py
python python-scripts/DB_load_city_data.py
```