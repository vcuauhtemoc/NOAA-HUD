# This file is for working out the functions needed for this program.

from collections import defaultdict
from datetime import datetime as dt
from datetime import date
from datetime import timedelta
import dateutil.relativedelta as rd
from geopy import distance
import json
import lxml.html as lh
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from pandas import DataFrame as df
import requests
import scipy.signal as ss
import urllib.request as url_request
import xml.etree.ElementTree as ET
from zeep import Client

weather_properties = [
    'temperature',
    'dewpoint',
    'maxTemperature',
    'minTemperature',
    'relativeHumidity',
    'apparentTemperature',
    'heatIndex',
    'windChill',
    'skyCover',
    'windDirection',
    'windSpeed',
    'probabilityOfPrecipitation',
    'quantitativePrecipitation',
    'pressure'
]
temperature_properties = [
    'temperature',
    'dewpoint',
    'maxTemperature',
    'minTemperature',
    'apparentTemperature',
    'heatIndex',
    'windChill',
]
# SOAP call to NOAA server converting zip code to Lat+Lon coordinates
while True:
    try:
        zip_code = input('Enter zip code: \n')
        wsdl = Client('https://graphical.weather.gov/xml/DWMLgen/wsdl/ndfdXML.wsdl')
        coordinates = wsdl.service.LatLonListZipCode(zip_code)
    except:
        print('Zip code please, not how much your mom weighs. Or, if you did give a zip code, my bad. Probably '
              'a server error on NWS\'s side.')
    else:
        break

# Variables used for retrieving correct weather station for both forecast and historical data.
parsed_coordinates = ET.fromstring(coordinates)
lat_lon_zip = parsed_coordinates.find('latLonList').text
lat = lat_lon_zip[:lat_lon_zip.index(',')]
lon = lat_lon_zip[lat_lon_zip.index(',') + 1:]

## Retrieving forecast data nearest to zipcode

# NWS JSON containing link to weather station's raw data
with url_request.urlopen('https://api.weather.gov/points/' + lat_lon_zip) as nws_api:
    nws_api_data = json.loads(nws_api.read())

# get raw data for corresponding weather station
with url_request.urlopen(nws_api_data['properties']['forecastGridData']) as forecast_grid_data:
    forecast = forecast_grid_data.read()

# # For offline testing
# with open('31,80.json', 'r') as forecast_json:
#     forecast_data = json.load(forecast_json)

forecast_data = json.loads(forecast)
forecast_data_properties = forecast_data['properties']
nested_forecast_data = pd.DataFrame()

# Create a dict from the list of dicts. Alternative method from earlier 'convert to tuple list' method.
def retrieve_column_as_dict():
    column_dict = defaultdict(set)
    user_string = input('Enter a column name:')
    for property_dict_key,property_dict_value in forecast_data_properties.items():
        if str(property_dict_key) == user_string:

            for list_elements in property_dict_value['values']:
                for k,v in list_elements.items():
                    column_dict[k].add(v)
                # timestamp = []
                # value = []
                # for key,value in values.items():
                #     column_dict.update()
                #     print(str(key) + ": " + str(value))
                #     match = True
    for key,value in column_dict.items():
        print(key,str(value))


# Going to use this to grab all data variables, need to concatenate with historical data.
def forecast_json_reformatted(weather_json):
    """reformats json to use timestamp as data index, where original json uses forecast property."""
    timestamp = {}

    for property in weather_json['properties']:
        if any(property_name in property for property_name in weather_properties):
            # Convert C to F
            if any(temp_property in property for temp_property in temperature_properties):
                print(property)
                for element in weather_json['properties'][property]['values']:
                    truncated_timestamp = element['validTime'][:element['validTime'].index('+')]
                    if truncated_timestamp not in timestamp and element['value'] is not None:
                        timestamp[truncated_timestamp] = {property: (element['value'] * (9/5)) + 32}
                    elif element['value'] is not None:
                        timestamp[truncated_timestamp][property] = (element['value'] * (9/5)) + 32
            else:
                for element in weather_json['properties'][property]['values']:
                    truncated_timestamp = element['validTime'][:element['validTime'].index('+')]
                    if truncated_timestamp not in timestamp:
                        timestamp[truncated_timestamp] = {property:element['value']}
                    else:
                        timestamp[truncated_timestamp][property] = element['value']
    return timestamp

def historical_weather():
    pass

forecast = forecast_json_reformatted(forecast_data)
forecast_df = pd.DataFrame.from_dict(forecast,orient='index')
forecast_df = forecast_df.sort_index()
forecast_df.to_csv('whoohooo.csv')
# forecast_df.plot()
# plt.show()