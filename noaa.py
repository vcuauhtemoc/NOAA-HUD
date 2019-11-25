#
#	Takes JSON from NWS API and generates a graph of humidity data for a chosen weather station.
#	Next objective is to have a 6 day weather report, but starting 3 days in the past, so the current moment
# 	sits in the middle of the graph.
#

from datetime import datetime as dt
from datetime import date
import dateutil.relativedelta as rd
from geopy import distance
import json
import lxml.html as lh
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import requests
import urllib.request as url_request
import xml.etree.ElementTree as ET
from zeep import Client

# make sure to create exception condition here. What's the try/catch/throw equivalent?

zip_code = input('Enter zip code: \n')


# SOAP call to NOAA server converting zip code to Lat+Lon coordinates

wsdl = Client('https://graphical.weather.gov/xml/DWMLgen/wsdl/ndfdXML.wsdl')
coordinates = wsdl.service.LatLonListZipCode(zip_code)
parsed_coordinates = ET.fromstring(coordinates)
lat_lon_zip = parsed_coordinates.find('latLonList').text
lat = lat_lon_zip[:lat_lon_zip.index(',')]
lon = lat_lon_zip[lat_lon_zip.index(',') + 1:]

# NWS JSON local weather info

nws_api = url_request.urlopen('https://api.weather.gov/points/' + lat_lon_zip).read()
nws_api_data = json.loads(nws_api)

# get raw data for corresponding weather station

forecast = url_request.urlopen(nws_api_data['properties']['forecastGridData']).read()
forecast_data = json.loads(forecast)
humidity_data = forecast_data['properties']['relativeHumidity']['values']
locale = nws_api_data['properties']['relativeLocation']['properties']['city'] + ", " + \
         nws_api_data['properties']['relativeLocation']['properties']['state']

## This section retrieves historical weather data and current conditions.

#List of all weather stations
noaa_ws_xml = url_request.urlopen('https://w1.weather.gov/xml/current_obs/index.xml').read()
noaa_ws_xml_tree = ET.fromstring(noaa_ws_xml)
closest_station_coordinates = ""
station_id = ""

# Get the nearest weather station based on lat/long coordinates in relation to a zipcode pseudocoordinates.
for station in noaa_ws_xml_tree.findall('station'):
    noaa_ws_lat_lon = station.find('latitude').text + "," + station.find('longitude').text
    if closest_station_coordinates == "":
        closest_station_coordinates = noaa_ws_lat_lon
        station_id = station.find('station_id').text
    elif distance.distance(closest_station_coordinates, lat_lon_zip) > distance.distance(lat_lon_zip, noaa_ws_lat_lon):
        closest_station_coordinates = noaa_ws_lat_lon
        station_id = station.find('station_id').text

# For current weather conditions
noaa_xml = url_request.urlopen('https://w1.weather.gov/xml/current_obs/' + station_id + '.xml').read()

# Historical weather data, 3 days prior.
noaa_obvhistory = requests.get('https://w1.weather.gov/data/obhistory/' + station_id + '.html')

noaa_obvhistory_lh = lh.fromstring(noaa_obvhistory.content)

tr_elements = noaa_obvhistory_lh.xpath('//tr')
payload = []
header = []

for e in tr_elements:
    if len(e) == 18:
        list = []
        for ee in e:
            list.append(ee.text_content())
        payload.append(list)
payload = payload[:-1]
# consolidating nested table header into a one-layered header
for e in tr_elements[4]:
    if tr_elements[4].index(e) == 6:  # Temp supergroup
        for i, ee in enumerate(tr_elements[5][:3]):
            if i == 2:  # Min/max
                for eee in tr_elements[6]:
                    header.append(e.text_content() + " " + ee.text_content() + " " + eee.text_content())
            else:
                header.append(e.text_content() + " " + ee.text_content())
    elif tr_elements[4].index(e) == 10:  # Pressure supergroup
        for ee in tr_elements[5][3:5]:
            header.append(e.text_content() + " " + ee.text_content())
    elif tr_elements[4].index(e) == 11:  # Precip. supergroup
        for ee in tr_elements[5][5:]:
            header.append(e.text_content() + " " + ee.text_content())
    else:
        header.append(e.text_content())

historical_weather_df = pd.DataFrame(reversed(payload), columns=header)

# The one column with a varying title; the timezone changes. Need a pattern filter.
time_column_label = historical_weather_df.filter(regex='Time.*').columns.values[0]

# Used with for loop to concatenate date and time
today = date.today()
last_month = (today + rd.relativedelta(months=-1)).month
last_year = (today + rd.relativedelta(years=-1)).year
timestamp_list = []

# Why do I have different syntaxes here?
humidity = str([e for e in historical_weather_df['RelativeHumidity']])
date_number = [str(e) for e in historical_weather_df['Date']]
time = [str(e) for e in historical_weather_df[time_column_label]]



# Concatenates date and time, as well as adding the correct month and year to iso format date.
for i in range(len(date_number)):

    if int(today.day) < int(date_number[i]):  # Condition for days in previous month
        if today.month == 1:
            timestamp_list.append(str(last_year) + "-" + str(last_month) + "-" + date_number[i] + " " + time[i])
        else:
            timestamp_list.append(str(today.year) + "-" + str(last_month) + "-" + date_number[i] + " " + time[i])
    else:
        timestamp_list.append(str(today.year) + "-" + str(today.month) + "-" + date_number[i] + " " + time[i])

# We'll throw the newly formed timestamp column into the dataframe and chuck the date and time columns.
historical_weather_df.insert(loc=0, column='Timestamp', value=timestamp_list)
historical_weather_df = historical_weather_df.drop(columns=['Date', time_column_label])
rel_humidity_array = []
for e in historical_weather_df['RelativeHumidity']:
    rel_humidity_array.append(e[:-1])


#historical_weather_df.to_csv('historical_weather_' + station_id + '.csv')

humidity_datapoint = []
dt_now_hr = dt.now().replace(minute=0, second=0, microsecond=0)  # dt object current time, truncating to current hr.
historical_weather_timestamp = historical_weather_df['Timestamp']
for i in range(len(historical_weather_timestamp)):
    dt_timestamp = dt.fromisoformat(historical_weather_timestamp[i])
    humidity = rel_humidity_array[i]
    humidity_datapoint.append((dt_timestamp,int(humidity)))

# Populate a new dataframe, concatenating the historical data with forecast.
for e in humidity_data:

    dt_timestamp = dt.fromisoformat(e['validTime'][:e['validTime'].index('+')])  # turn timestamp into datetime object.

    timedelta_timestamps = dt_timestamp - dt_now_hr  # Difference in hours between timestamp and current time

    #if (timedelta_timestamps.seconds / 3600) % 6 == 0:  # 6h intervals

    humidity_datapoint.append((dt_timestamp, e['value']))

humidity_df = pd.DataFrame(data=humidity_datapoint, columns=['Date', 'Humidity (%)'])

plot = humidity_df.plot(x='Date', y='Humidity (%)', kind='line', grid='true', title=locale)

plot.tick_params(axis='x', which='minor', labelsize=8)
plot.tick_params(axis='x', which='major', pad=16, labelrotation=0)
plot.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plot.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
plot.xaxis.set_minor_formatter(mdates.DateFormatter("%I%p"))
plt.setp(plot.xaxis.get_majorticklabels(), ha="center")
plt.show()