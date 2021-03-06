import os
import requests
import pprint
import datetime
import dateutil.parser
import datefinder
from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient, GEO2D

load_dotenv(find_dotenv())
pp = pprint.PrettyPrinter(indent=4)

# Mongo setup
client = MongoClient(os.getenv("MONGODB_URI"))
db = client['ncov']


############## HELPERS ##############

# Gets a date string, returns either a formatted date, or the string itself
def parse_date(date_str):
    try:
        return list(datefinder.find_dates(date_str))[-1]
    except:
        return date_str

def get_last_updated():
    doh_template_url = "https://dohph.maps.arcgis.com/sharing/rest/content/items/3dda5e52a7244f12a4fb3d697e32fd39/data"
    doh_template_params = {
        'f':'json'
    }

    response = requests.get(doh_template_url, doh_template_params)
    json_response = response.json()

    version = json_response['version']
    dashboard_title = json_response['headerPanel']['title'].split('of ')[1].replace(';','') # get string after 'of' and remove semicolon between date and time
    dashboard_last_updated = parse_date(dashboard_title)
    info = {
        'dashboard_version': version,
        'dashboard_last_updated': dashboard_last_updated
    }
    return info

def parse_facility_data(fac_obj, last_updated):
    fac_obj = fac_obj['attributes']
    try:
        fac_obj['location'] = {"type": "Point", "coordinates": [float(fac_obj['longitude']), float(fac_obj['latitude']) ]}
    except:
        fac_obj['location'] = {"type": "Point", "coordinates": [0.0, 0.0]}
    fac_obj['inserted_at'] = datetime.datetime.now()

    fac_obj['dashboard_version'] = last_updated['dashboard_version']
    fac_obj['dashboard_last_updated'] = last_updated['dashboard_last_updated']

    return fac_obj


# Convert Lat long to Geo Coordinates for Mongodb
def parse_location(ncov_case):
    try:
        location = {"type": "Point", "coordinates": [float(ncov_case['longitude']), float(ncov_case['latitude']) ]}
    except:
        location = {"type": "Point", "coordinates": [0.0, 0.0]}
    return location

############## API QUERIES ##############

### # Get local cases in the PH
def get_confirmed_cases_ph(last_updated):
    # https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/PH_masterlist/FeatureServer/0/query?f=json&where=1%3D1&returnGeometry=false&spatialRel=esriSpatialRelIntersects&outFields=*&orderByFields=FID%20desc&resultOffset=0&resultRecordCount=150&cacheHint=true
    master_list_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/PH_masterlist/FeatureServer/0/query"
    master_list_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'orderByFields':'FID desc',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(master_list_url, params=master_list_params)
    json_response = response.json()
    ncov_cases = json_response['features']

    cases = db.cases_ph

    for ncov_case in ncov_cases:
        ncov_case = ncov_case['attributes']
        ncov_case['location'] = parse_location(ncov_case)
        ncov_case['confirmed'] = parse_date(ncov_case['confirmed'])
        ncov_case['dashboard_last_updated'] = last_updated['dashboard_last_updated']
        ncov_case['dashboard_version'] = last_updated['dashboard_version']
        ncov_case['inserted_at'] = datetime.datetime.now()
        cases.insert_one(ncov_case)

# Get Foreign Cases (people who came and left the PH)
def get_confirmed_cases_fn(last_updated):
    master_list_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/FN_masterlist/FeatureServer/0/query"
    master_list_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'orderByFields':'FID desc',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(master_list_url, params=master_list_params)
    json_response = response.json()
    ncov_cases = json_response['features']

    cases = db.cases_fn

    for ncov_case in ncov_cases:
        ncov_case = ncov_case['attributes']
        ncov_case['location'] = parse_location(ncov_case)
        ncov_case['dashboard_last_updated'] = last_updated['dashboard_last_updated']
        ncov_case['dashboard_version'] = last_updated['dashboard_version']
        ncov_case['inserted_at'] = datetime.datetime.now()
        cases.insert_one(ncov_case)

# Get OFW Cases
def get_confirmed_cases_ofw(last_updated):
    master_list_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/OF_masterlist/FeatureServer/0/query"
    master_list_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'orderByFields':'FID desc',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(master_list_url, params=master_list_params)
    json_response = response.json()
    ncov_cases = json_response['features']

    cases = db.cases_ofw

    for ncov_case in ncov_cases:
        ncov_case = ncov_case['attributes']

        # Fill info
        ncov_case['date_confi'] = parse_date(ncov_case['date_confi'])
        ncov_case['date_repor'] = parse_date(ncov_case['date_repor'])
        ncov_case['location'] = parse_location(ncov_case)
        ncov_case['dashboard_last_updated'] = last_updated['dashboard_last_updated']
        ncov_case['dashboard_version'] = last_updated['dashboard_version']
        ncov_case['inserted_at'] = datetime.datetime.now()
        pp.pprint(ncov_case)
        cases.insert_one(ncov_case)

#######---------------------------- #############

# Get PUI (Persons under Investigation) data from hospitals  (how many PUIs in which hospital)
def get_puis(last_updated):
    pui_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/PUI_fac_tracing/FeatureServer/0/query"
    pui_list_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(pui_url, params=pui_list_params)
    json_response = response.json()

    facilities = json_response['features']

    db_puis = db.facilities_puis

    for facility in facilities:
        facility_pui = parse_facility_data(facility, last_updated)
        db_puis.insert_one(facility_pui)


#######---------------------------- #############

# Get confirmed cases data from hospitals (how many admitted in which hospital)
def get_conf_facility(last_updated):
    conf_facility_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/conf_fac_tracking/FeatureServer/0/query"
    conf_facility_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'orderByFields':'count_ desc',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(conf_facility_url, params=conf_facility_params)
    json_response = response.json()
    facilities = json_response['features']

    fac_confs = db.facilities_conf

    for facility in facilities:
        facility_conf = parse_facility_data(facility, last_updated)
        fac_confs.insert_one(facility_conf)

#######---------------------------- #############
def get_commodities(last_updated):
    commodities_url = "https://services5.arcgis.com/mnYJ21GiFTR97WFg/arcgis/rest/services/commodities/FeatureServer/0/query"
    commodities_params = {
        'f':'json',
        'where':'1=1',
        'returnGeometry': 'false',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields':'*',
        'resultOffset':0,
        # 'resultRecordCount':200,
        'cacheHint':'true'
        }

    response = requests.get(commodities_url, params=commodities_params)
    json_response = response.json()
    commodities = json_response['features']

    db_commodities = db.commodities
    for commodity in commodities:
        commodity = commodity['attributes']

        commodity['dashboard_last_updated'] = last_updated['dashboard_last_updated']
        commodity['dashboard_version'] = last_updated['dashboard_version']
        commodity['inserted_at'] = datetime.datetime.now()
        db_commodities.insert_one(commodity)

    pp.pprint(commodities)

if __name__ == '__main__':
    last_updated = get_last_updated() #dashboard version & last updated
    get_confirmed_cases_fn(last_updated)
    get_confirmed_cases_ph(last_updated)
    get_confirmed_cases_ofw(last_updated)
    get_puis(last_updated)
    get_conf_facility(last_updated)
    get_commodities(last_updated)
