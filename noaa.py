from datetime import datetime as dt
from datetime import date
import time
from datetime import timedelta
import dateutil.relativedelta as rd
from geopy import distance
import json
import lxml.html as lh
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import numpy as np
import pandas as pd
import re
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
convert_col_names = {
    'Temperature (ºF) Air': 'temperature',
    'Temperature (ºF) Dwpt': 'dewpoint',
    'Temperature (ºF) 6 hour Max.': 'maxTemperature',
    'Temperature (ºF) 6 hour Min.': 'minTemperature',
    'RelativeHumidity': 'relativeHumidity',
    'WindChill(°F)': 'windChill',
    'HeatIndex(°F)': 'heatIndex',
    'Precipitation (in.) 1 hr': 'quantitativePrecipitation',
    'Pressure altimeter(in)': 'pressure'
}
cardinal_bearings = {
    'N': 0,
    'NE': 45,
    'E': 90,
    'SE': 135,
    'S': 180,
    'SW': 225,
    'W': 270,
    'NW': 315
}

weather_properties_user_inputs = {
    '1': 'Temperature',
    '2': 'Dewpoint',
    '3': 'High Temperature',
    '4': 'Low Temperature',
    '5': 'Relative Humidity',
    '6': 'Apparent Temperature',
    '7': 'Heat Index',
    '8': 'Wind Chill',
    '9': 'Sky Cover',
    '10': 'Wind Conditions',
    '11': 'Chance of Rain',
    '12': 'Rainfall',
    '13': 'Atmospheric Pressure',
}

user_input_to_df_columns = {
    'Temperature': 'temperature',
    'Dewpoint': 'dewpoint',
    'High Temperature': 'maxTemperature',
    'Low Temperature': 'minTemperature',
    'Relative Humidity': 'relativeHumidity',
    'Apparent Temperature': 'apparentTemperature' ,
    'Heat Index': 'heatIndex' ,
    'Wind Chill': 'windChill' ,
    'Sky Cover': 'skyCover',
    'Wind Conditions': ('windDirection','windSpeed'),
    'Chance of Rain': 'probabilityOfPrecipitation',
    'Rainfall': 'quantitativePrecipitation',
    'Atmospheric Pressure': 'pressure'
}

# gets forecast JSON and returns dataframe.
def forecast():
    # get raw data for corresponding weather station
    with url_request.urlopen(nws_api_data['properties']['forecastGridData']) as forecast_grid_data:
        forecast = forecast_grid_data.read()

    forecast_data = json.loads(forecast)
    """reformats json to use timestamp as data index, where original json uses forecast property."""
    timestamp = {}

    for property in forecast_data['properties']:
        if any(property_name in property for property_name in weather_properties):
            # Convert C to F
            if any(temp_property in property for temp_property in temperature_properties):
                for element in forecast_data['properties'][property]['values']:
                    truncated_timestamp = element['validTime'][:element['validTime'].index('+')]
                    if dt.fromisoformat(truncated_timestamp) - dt.now() > timedelta(days=3):
                        continue
                    elif truncated_timestamp not in timestamp and element['value'] is not None:
                        timestamp[truncated_timestamp] = {property: (element['value'] * (9 / 5)) + 32}
                    elif element['value'] is not None:
                        timestamp[truncated_timestamp][property] = (element['value'] * (9 / 5)) + 32
            else:
                for element in forecast_data['properties'][property]['values']:
                    truncated_timestamp = element['validTime'][:element['validTime'].index('+')]
                    if dt.fromisoformat(truncated_timestamp) - dt.now() > timedelta(days=3):
                        continue
                    elif truncated_timestamp not in timestamp:
                        timestamp[truncated_timestamp] = {property: element['value']}
                    else:
                        timestamp[truncated_timestamp][property] = element['value']
    forecast_df = pd.DataFrame.from_dict(timestamp, orient='index')
    forecast_df = forecast_df.sort_index()
    forecast_df.index = pd.to_datetime(forecast_df.index)
    return forecast_df


# Scraping HTML table and returning dataframe.
def historical_weather():
    # Need to first retrieve list of all US weather stations
    noaa_ws_xml = url_request.urlopen('https://w1.weather.gov/xml/current_obs/index.xml').read()
    noaa_ws_xml_tree = ET.fromstring(noaa_ws_xml)

    # placeholders for function below.
    closest_station_coordinates = ""
    station_id = ""

    # Fixes discrepancy between zip code coordinates and weather station coordinates.
    # Finds where distance between former and latter is shortest, and chooses it.
    for station in noaa_ws_xml_tree.findall('station'):
        noaa_ws_lat_lon = station.find('latitude').text + "," + station.find('longitude').text
        if closest_station_coordinates == "":
            closest_station_coordinates = noaa_ws_lat_lon
            station_id = station.find('station_id').text
        elif distance.distance(closest_station_coordinates, lat_lon_zip) > distance.distance(lat_lon_zip,
                                                                                             noaa_ws_lat_lon):
            closest_station_coordinates = noaa_ws_lat_lon
            station_id = station.find('station_id').text

    # For current weather conditions
    noaa_xml = url_request.urlopen('https://w1.weather.gov/xml/current_obs/' + station_id + '.xml').read()

    # Historical weather data, 3 days prior. Info is in HTML table, re-parsing required.
    noaa_obvhistory = requests.get('https://w1.weather.gov/data/obhistory/' + station_id + '.html')

    noaa_obvhistory_lh = lh.fromstring(noaa_obvhistory.content)

    # populate list with each table row element, then parse that between raw data and column headers. Headers need to be
    # re-formatted because of the 3-tier column nesting format used on the website.
    tr_elements = noaa_obvhistory_lh.xpath('//tr')
    payload = []
    header = []

    for e in tr_elements:
        if len(e) == 18:
            list = []
            for ee in e:
                list.append(str(ee.text_content()).strip('%'))
            payload.append(list)

    # Remove final list element, which are column labels. Payload is now just the raw data from table.
    payload = payload[:-1]

    # consolidating 3-layer table header down to one layer
    for e in tr_elements[4]:
        if tr_elements[4].index(e) == 6:  # 'Temp' subcolumns
            for i, ee in enumerate(tr_elements[5][:3]):
                if i == 2:  # subcolumns Min/max
                    for eee in tr_elements[6]:
                        header.append(e.text_content() + " " + ee.text_content() + " " + eee.text_content())
                else:
                    header.append(e.text_content() + " " + ee.text_content())
        elif tr_elements[4].index(e) == 10:  # 'Pressure' subcolumns
            for ee in tr_elements[5][3:5]:
                header.append(e.text_content() + " " + ee.text_content())
        elif tr_elements[4].index(e) == 11:  # 'Precip.' subcolumns
            for ee in tr_elements[5][5:]:
                header.append(e.text_content() + " " + ee.text_content())
        else:
            header.append(e.text_content())

    # Reverse list order to start it on earliest date.
    historical_weather_df = pd.DataFrame(reversed(payload), columns=header)
    # The one column with a varying title; the timezone. Need a pattern filter for when I retrieve from df.
    time_column_label = historical_weather_df.filter(regex='Time.*').columns.values[0]

    # Used with for loop to concatenate date and time
    today = date.today()
    last_month = (today + rd.relativedelta(months=-1)).month
    last_year = (today + rd.relativedelta(years=-1)).year
    timestamp_list = []

    date_number = [str(e) for e in historical_weather_df['Date']]
    time = [str(e) for e in historical_weather_df[time_column_label]]

    # Concatenates date and time, as well as adding the correct month and year to iso format date.
    for i in range(len(date_number)):

        if int(today.day) < int(date_number[i]):  # Condition for days in previous month
            if today.month == 1:  # ...and for previous year.
                timestamp_list.append(str(last_year) + "-" + str(last_month) + "-" + date_number[i] + " " + time[i])
            else:
                timestamp_list.append(str(today.year) + "-" + str(last_month) + "-" + date_number[i] + " " + time[i])
        else:
            timestamp_list.append(str(today.year) + "-" + str(today.month) + "-" + date_number[i] + " " + time[i])

    # Swapping out the 'date' and 'time' columns for 'Timestamp'
    historical_weather_df.insert(loc=0, column='Timestamp', value=timestamp_list)
    historical_weather_df = historical_weather_df.drop(columns=['Date', time_column_label])
    historical_weather_df.set_index('Timestamp', inplace=True, drop=True)
    historical_weather_df.index = pd.to_datetime(historical_weather_df.index)
    historical_weather_df.rename(columns=convert_col_names, inplace=True)
    for col_name, col_data in historical_weather_df.iteritems():
        if any(col_equivalent in col_name for col_equivalent in convert_col_names):
            historical_weather_df = historical_weather_df.astype({col_name: 'float64'})
    # translate syntax of historical weather wind info to match forecast wind info, drop column with old format.
    for index, row in historical_weather_df.iterrows():
        wind_mph = str(row['Wind(mph)'])
        if wind_mph is not None:
            wind_direction = re.match(r'[NESW]+', wind_mph)
            wind_speed = re.search(r'[0-9]+', wind_mph)
            if wind_direction:
                historical_weather_df.at[index, 'windDirection'] = cardinal_bearings[wind_direction[0]]
            if wind_speed:
                historical_weather_df.at[index, 'windSpeed'] = wind_speed[0]
            else:
                historical_weather_df.at[index, 'windSpeed'] = None
    historical_weather_df.drop(['Wind(mph)'], axis=1, inplace=True)
    return historical_weather_df


# SOAP call to NOAA server converting zip code to Lat+Lon coordinates
while True:
    try:
        zip_code = input('Enter zip code: \n')
        wsdl = Client('https://graphical.weather.gov/xml/DWMLgen/wsdl/ndfdXML.wsdl')
        coordinates = wsdl.service.LatLonListZipCode(zip_code)
    except:
        print('ERROR. TRY AGAIN')
    else:
        break

# Variables used for retrieving correct weather station for both forecast and historical data.
parsed_coordinates = ET.fromstring(coordinates)
lat_lon_zip = parsed_coordinates.find('latLonList').text
lat = lat_lon_zip[:lat_lon_zip.index(',')]
lon = lat_lon_zip[lat_lon_zip.index(',') + 1:]

## Retrieve a coordinate pair and city name
with url_request.urlopen('https://api.weather.gov/points/' + lat_lon_zip) as nws_api:
    nws_api_data = json.loads(nws_api.read())
locale = nws_api_data['properties']['relativeLocation']['properties']['city'] + ", " + \
         nws_api_data['properties']['relativeLocation']['properties']['state']
t1 = time.time()
big_df = pd.concat([historical_weather(), forecast()], sort=True)
t2 = time.time()
big_df.to_csv('check_wind_columns.csv')

for weather_property, property_value in big_df.iteritems():
    if weather_property in weather_properties:
        big_df[weather_property].replace(['', 'NA'], np.nan, inplace=True)
        #big_df = big_df.dropna(subset=[weather_property])
        big_df = big_df.astype({weather_property: 'float64'})

big_df = big_df.interpolate()

while True:
    try:
        print('Choose any combination of weather attributes:')
        weather_properties_user = []
        for k,v in weather_properties_user_inputs.items():
            print(k,v)
        # make attribute a list instead of int, then iterate through each element in list to create multiple data lines.
        attributes = input()
        if ' ' or ',' in attributes:
            attribute_list = re.split('\W+', attributes)
        attribute_list_translated = []
        attributes_legend = []
        for attribute_element in attribute_list:
            if re.search(r'[0-9]', attribute_element):
                attributes_legend.append(weather_properties_user_inputs[attribute_element])
                column = user_input_to_df_columns[weather_properties_user_inputs[attribute_element]]
                print(column)
                if isinstance(column,str) is False:
                    attribute_list_translated.extend(column)
                else:
                    attribute_list_translated.append(column)
                # if ',' in column:
                #     print(column)
                #     attribute_list_translated.append(column[:column.index(',')])
                #     attribute_list_translated.append(column[column.index(',') + 1:])
            else:
                column = user_input_to_df_columns[attribute_element]
                attribute_list_translated.append(attribute_element)
        for e in attribute_list_translated:
            big_df[e] = ss.savgol_filter(big_df[e],9,1)

        #plot = big_df.plot(y=attribute_list_translated, grid='true', kind='line', title=locale)
        fig , ax = plt.subplots()

        # Placeholders for customizing matplotlib formatting for each weather attribute
        if 'temperature' in attribute_list_translated:
            ax.plot(big_df['temperature'])
            pass
        if 'dewpoint' in attribute_list_translated:
            ax.plot(big_df['dewpoint'])
            pass
        if 'maxTemperature' in attribute_list_translated:
            ax.plot(big_df['maxTemperature'])
            pass
        if 'minTemperature' in attribute_list_translated:
            ax.plot(big_df['minTemperature'])
            pass
        if 'relativeHumidity' in attribute_list_translated:
            ax.plot(big_df['relativeHumidity'])
            pass
        if 'apparentTemperature' in attribute_list_translated:
            ax.plot(big_df['apparentTemperature'])
            pass
        if 'heatIndex' in attribute_list_translated:
            ax.plot(big_df['heatIndex'])
            pass
        if 'windChill' in attribute_list_translated:
            ax.plot(big_df['windChill'])
            pass
        if 'skyCover' in attribute_list_translated:
            ax.plot(big_df['skyCover'])
            pass
        if 'windDirection' and 'windSpeed' in attribute_list_translated:
            # plot scatter w/ rotated markers on top of line, pyplot plot function not supporting transformed
            # MarkerStyle, for some reason. Tries to interpret as 'Path'.
            for e in big_df.index:
                if big_df['windDirection'][e] is not None:
                    t = mpl.markers.MarkerStyle(marker=r'$\Uparrow$')
                    t._transform.rotate_deg(big_df['windDirection'][e])
                    plt.scatter(e,big_df['windSpeed'][e],marker=t,s=200,c='blue')
            plt.plot(big_df['windSpeed'])
            plt.xlim(dt.now() - timedelta(days=3) , dt.now() + timedelta(days=3))
            pass
        if 'windSpeed' in attribute_list_translated:
            ax.plot(big_df['windSpeed'])
            pass
        if 'probabilityOfPrecipitation' in attribute_list_translated:
            ax.plot(big_df['probabilityOfPrecipitation'])
            pass
        if 'quantitativePrecipitation' in attribute_list_translated:
            ax.plot(big_df['quantitativePrecipitation'])
            pass
        if 'pressure' in attribute_list_translated:
            ax.plot(big_df['pressure'])
            pass

        plt.tick_params(axis='x', which='minor', labelsize=8)
        plt.tick_params(axis='x', which='major', pad=16, labelrotation=0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
        ax.xaxis.set_minor_formatter(mdates.DateFormatter("%I%p"))
        ax.grid()
        ax.legend(attributes_legend)
        ax.set_title(locale)
        plt.setp(ax.xaxis.get_majorticklabels(), ha="center")
        plt.axvline(x=dt.now(), color='black')      #shows current time on graph
        plt.show()
    except Exception as ex:
        print('ERROR. TRY AGAIN')
        raise ex
    else:
        break