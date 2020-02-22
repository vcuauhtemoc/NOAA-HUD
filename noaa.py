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
from pandas.plotting import register_matplotlib_converters
# from PyQt5 import Qapplication, Qlabel
import re
import requests
import scipy.signal as ss
from scipy.interpolate import interp1d
import urllib.request as url_request
import xml.etree.ElementTree as ET
from zeep import Client

register_matplotlib_converters()

class Noaa:
    def __init__(self,zip_code):
        self.zip_code = str(zip_code)
        self.weather_properties = [
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
        self.temperature_properties = [
            'temperature',
            'dewpoint',
            'maxTemperature',
            'minTemperature',
            'apparentTemperature',
            'heatIndex',
            'windChill',
        ]
        self.convert_col_names = {
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
        self.cardinal_bearings = {
            'N': 0,
            'NE': 45,
            'E': 90,
            'SE': 135,
            'S': 180,
            'SW': 225,
            'W': 270,
            'NW': 315
        }

        self.weather_properties_user_inputs = {
            '1': 'Temperature',
            '2': 'Dewpoint',
            '3': 'High Temperature',
            '4': 'Low Temperature',
            '5': 'Relative Humidity',
            '6': 'Wind Chill',
            '7': 'Sky Cover',
            '8': 'Wind Conditions',
            '9': 'Chance of Rain',
            '10': 'Rainfall',
            '11': 'Atmospheric Pressure',
        }

        self.user_input_to_df_columns = {
            'Temperature': 'temperature',
            'Dewpoint': 'dewpoint',
            'High Temperature': 'maxTemperature',
            'Low Temperature': 'minTemperature',
            'Relative Humidity': 'relativeHumidity',
            'Wind Chill': 'windChill',
            'Sky Cover': 'skyCover',
            'Wind Conditions': ('windDirection', 'windSpeed'),
            'Chance of Rain': 'probabilityOfPrecipitation',
            'Rainfall': 'quantitativePrecipitation',
            'Atmospheric Pressure': 'pressure'
        }

    def get_locale(self,lat_lon_zip):
        with url_request.urlopen('https://api.weather.gov/points/' + lat_lon_zip) as nws_api:
            nws_api_data = json.loads(nws_api.read())
        locale = nws_api_data['properties']['relativeLocation']['properties']['city'] + ", " + \
                 nws_api_data['properties']['relativeLocation']['properties']['state']
        return locale

    # gets forecast JSON and returns dataframe.
    def forecast(self,lat_lon_zip):
        ## Retrieve a coordinate pair and city name
        with url_request.urlopen('https://api.weather.gov/points/' + lat_lon_zip) as nws_api:
            nws_api_data = json.loads(nws_api.read())
        locale = nws_api_data['properties']['relativeLocation']['properties']['city'] + ", " + \
                 nws_api_data['properties']['relativeLocation']['properties']['state']
        print('Retrieving weather data for nearest NWS weather station, located in ' + locale)
        # get raw data for corresponding weather station
        with url_request.urlopen(nws_api_data['properties']['forecastGridData']) as forecast_grid_data:
            forecast = forecast_grid_data.read()

        forecast_data = json.loads(forecast)
        """reformats json to use timestamp as data index, where original json uses forecast property."""
        # Can we just make this into a dataframe from the start, not convert dict to df?
        timestamp = {}

        for property in forecast_data['properties']:
            if any(property_name in property for property_name in self.weather_properties):
                # Convert C to F
                if any(temp_property in property for temp_property in self.temperature_properties):
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
        forecast_df['windSpeed'] = forecast_df['windSpeed'].apply(lambda x: x * 2.23694)
        return forecast_df


    # Scraping HTML table and returning dataframe.
    def historical_weather(self,lat_lon_zip):
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
        historical_weather_df['Timestamp'] = pd.to_datetime(historical_weather_df['Timestamp'])
        historical_weather_df['Timestamp'] = historical_weather_df['Timestamp'].dt.round('H')
        historical_weather_df.set_index('Timestamp', inplace=True, drop=True)
        # historical_weather_df.index = pd.to_datetime(historical_weather_df.index)
        historical_weather_df.rename(columns=self.convert_col_names, inplace=True)
        for col_name, col_data in historical_weather_df.iteritems():
            if any(col_equivalent in col_name for col_equivalent in self.convert_col_names):
                historical_weather_df = historical_weather_df.astype({col_name: 'float64'})
        # translate syntax of historical weather wind info to match forecast wind info, drop column with old format.
        for index, row in historical_weather_df.iterrows():
            wind_mph = str(row['Wind(mph)'])
            if wind_mph is not None:
                wind_direction = re.match(r'[NESW]+', wind_mph)
                wind_speed = re.search(r'[0-9]+', wind_mph)
                if wind_direction:
                    historical_weather_df.at[index, 'windDirection'] = self.cardinal_bearings[wind_direction[0]]
                if wind_speed:
                    historical_weather_df.at[index, 'windSpeed'] = wind_speed[0]
                else:
                    historical_weather_df.at[index, 'windSpeed'] = None
        historical_weather_df.drop(['Wind(mph)'], axis=1, inplace=True)
        return historical_weather_df


    # SOAP call to NOAA server converting zip code to Lat+Lon coordinates
    def get_weather_station(self):
        while True:
            try:
                zip_code = self.zip_code
                print(zip_code)
                print('Finding weather station nearest to ' + zip_code + '...')
                wsdl = Client('https://graphical.weather.gov/xml/DWMLgen/wsdl/ndfdXML.wsdl')
                coordinates = wsdl.service.LatLonListZipCode(zip_code)
                parsed_coordinates = ET.fromstring(coordinates)
                lat_lon_zip = parsed_coordinates.find('latLonList').text
                return lat_lon_zip
            except Exception as ex:
                print(ex)
            else:
                break
        # Variables used for retrieving correct weather station for both forecast and historical data.

        # lat = lat_lon_zip[:lat_lon_zip.index(',')]
        # lon = lat_lon_zip[lat_lon_zip.index(',') + 1:]

    def make_graph(self):
        coordinates = self.get_weather_station()
        locale = self.get_locale(coordinates)
        big_df = pd.concat([self.historical_weather(coordinates), self.forecast(coordinates)], sort=True)

        for weather_property, property_value in big_df.iteritems():
            if weather_property in self.weather_properties:
                big_df[weather_property].replace(['', 'NA'], np.nan, inplace=True)
                # big_df = big_df.dropna(subset=[weather_property])
                big_df = big_df.astype({weather_property: 'float64'})

        index_list = []
        indexes_to_drop = []
        for df_row in big_df.index:
            index_list.append(df_row)
        big_df = big_df.loc[~big_df.index.duplicated(keep='last')]

        # # Deals with zero values at beginning of df, which interpolate doesn't manage.
        # for e in big_df.columns:
        #     if isinstance(big_df.loc[big_df.index[0], e], np.float64):
        #         if np.isnan(big_df.loc[big_df.index[0], e]):
        #             big_df.loc[big_df.index[0], e] = big_df.loc[big_df.index[1], e]

        # easy way to deal with any zero values on a given weather property.
        big_df = big_df.drop(
            columns=['apparentTemperature', 'Precipitation (in.) 3 hr', 'Precipitation (in.) 6 hr',
                     'Pressure sea level(mb)',
                     'Sky Cond.', 'Vis.(mi.)', 'heatIndex'])
        # big_df = big_df.dropna()
        big_df = big_df.interpolate(method='time')
        big_df.to_csv('big_df.csv')
        while True:
            try:
                print('Choose any combination of weather attributes to display:')
                weather_properties_user = []
                for k, v in self.weather_properties_user_inputs.items():
                    print(k, v)
                # make attribute a list instead of int, then iterate through each element in list to create multiple data lines.
                attributes = input()
                if ' ' or ',' in attributes:
                    attribute_list = re.split('\W+', attributes)
                attribute_list_translated = []
                attributes_legend = []
                for attribute_element in attribute_list:
                    if re.search(r'[0-9]', attribute_element):
                        attributes_legend.append(self.weather_properties_user_inputs[attribute_element])
                        column = self.user_input_to_df_columns[self.weather_properties_user_inputs[attribute_element]]
                        if isinstance(column, str) is False:
                            attribute_list_translated.extend(column)
                        else:
                            attribute_list_translated.append(column)
                        # if ',' in column:
                        #     print(column)
                        #     attribute_list_translated.append(column[:column.index(',')])
                        #     attribute_list_translated.append(column[column.index(',') + 1:])
                    else:
                        column = self.user_input_to_df_columns[attribute_element]
                        attribute_list_translated.append(attribute_element)
                # for e in attribute_list_translated:
                #     big_df[e] = ss.savgol_filter(big_df[e],9,1)

                # plot = big_df.plot(y=attribute_list_translated, grid='true', kind='line', title=locale)
                fig, ax_list = plt.subplots(3)

                # Conditions for customizing matplotlib formatting for each weather attribute
                # **Find a better way to deal with NaN values, historical weather sometimes not plotting now**
                if 'temperature' in attribute_list_translated:
                    attr = 'temperature'
                    big_df[attr].fillna(method='bfill', inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[0].plot(new_x, new_y, label='Temperature (F)')
                if 'dewpoint' in attribute_list_translated:
                    attr = 'dewpoint'
                    big_df[attr].fillna(method='bfill', inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[0].plot(new_x, new_y, label='Dewpoint')
                if 'maxTemperature' in attribute_list_translated:
                    attr = 'maxTemperature'
                    big_df[attr].fillna(method='bfill', inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[0].plot(new_x, new_y, label='Hi Temp')
                if 'minTemperature' in attribute_list_translated:
                    attr = 'minTemperature'
                    big_df[attr].fillna(method='bfill', inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[0].plot(new_x, new_y, label='Low Temp')
                if 'relativeHumidity' in attribute_list_translated:
                    attr = 'relativeHumidity'
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[1].plot(new_x, new_y, label='Relative Humidity (%)')
                if 'windChill' in attribute_list_translated:
                    attr = 'windChill'
                    big_df[attr].fillna(method='bfill', inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[0].plot(new_x, new_y, label='Windchill')
                if 'skyCover' in attribute_list_translated:
                    attr = 'skyCover'
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[1].plot(new_x, new_y, label='Sky Cover', color='grey')
                    ax_list[1].fill_between(new_x, new_y, y2=0, color='grey', alpha=0.3, hatch='-')
                if 'windDirection' and 'windSpeed' in attribute_list_translated:
                    # plot scatter w/ rotated markers on top of line, pyplot plot function not supporting transformed
                    # MarkerStyle, Tries to interpret as 'Path'. Also, setting marker angle is counterclockwise...
                    attr = 'windSpeed'
                    #big_df[attr] = big_df[attr].apply(lambda x: x * 2.23694)
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    # ax_list[2].plot(new_x,new_y,c='blue', linewidth=.5, zorder=0, label='Wind Speed')
                    for e in big_df.index:
                        if not np.isnan(big_df['windDirection'][e]):
                            t = mpl.markers.MarkerStyle(marker=r'$\longrightarrow$')
                            # print(mpl.dates.date2num(e))
                            t._transform.rotate_deg(270 - int(round(big_df['windDirection'][e])))
                            # t._transform.rotate_deg_around(x=mpl.dates.date2num(e),y=big_df['windSpeed'][e],degrees=360 - int(round(big_df['windDirection'][e])))
                            ax_list[2].scatter(e, big_df['windSpeed'][e], marker=t, s=150, c='lightseagreen', zorder=10)
                        else:
                            print('you have a problem here: ' + str(e))
                if 'probabilityOfPrecipitation' in attribute_list_translated:
                    attr = 'probabilityOfPrecipitation'
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[1].plot(new_x, new_y, label='Chance of Rain', c='#2c80ffff')
                    ax_list[1].fill_between(new_x, new_y, y2=0, color='#2c80ffff',
                                            alpha=0.3, hatch='|')
                if 'quantitativePrecipitation' in attribute_list_translated:
                    attr = 'quantitativePrecipitation'
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[2].plot(new_x, new_y, label='Rainfall (in)', c='#2c80ffff')
                    ax_list[2].fill_between(new_x, new_y, y2=0, color='#2c80ffff',
                                            alpha=0.3)
                if 'pressure' in attribute_list_translated:
                    attr = 'pressure'
                    big_df[attr].fillna(0, inplace=True)
                    num_index = mdates.date2num(big_df[attr].index)
                    new_x = np.linspace(num_index[0], num_index[-1], num=1000, endpoint=True)
                    f = interp1d(num_index, big_df[attr].values, kind='cubic')
                    new_y = f(new_x)
                    ax_list[1].plot(new_x, new_y, label='Pressure (in)')
                for ax in ax_list:

                    ax.tick_params(axis='x', which='minor', labelsize=8)
                    ax.tick_params(axis='x', which='major', pad=16, labelrotation=0)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
                    ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
                    ax.xaxis.set_minor_formatter(mdates.DateFormatter("%I%p"))
                    ax.grid()
                    for line in ax.lines:
                        new_x = []
                        new_x_reconverted = []
                        new_y = []
                        # for e in line.get_xdata():
                        #     new_x.append(mdates.date2num(e))
                        # new_y = interp1d(line.get_xdata(),line.get_ydata(), kind='cubic')
                        # new_x = np.linspace(new_x[1],new_x[-1],num=200,endpoint=True)
                        #
                        # for e in new_x:
                        #     new_x_reconverted.append(mdates.num2date(e))
                        # print(line.get_xdata()[0])
                        y = line.get_ydata()[-1]
                        line_str = str(line)
                        line_label = line_str[line_str.index('(') + 1:-1]
                        ax.annotate(line_label, xy=(1, y), xytext=(6, 0), color=line.get_color(),
                                    xycoords=ax.get_yaxis_transform(), textcoords="offset points",
                                    size=14, va="center")
                    ax.set_xlim(big_df.index[0], big_df.index[-1])
                    labels = ax.get_xticklabels()
                    # for e in labels:
                    #     e.set_rotation()
                    # ax.setp(ax.xaxis.get_majorticklabels(), ha="center")
                    ax.axvline(x=dt.now(), color='black')  # shows current time on graph
                fig.suptitle(locale)
                big_df.to_csv('big_df_manip.csv')
                return fig
            except Exception as ex:
                print('ERROR. TRY AGAIN')
                raise ex
            else:
                break


if __name__ == '__main__':
    zip_code = input("Enter zip code: ")
    new_noaa = Noaa(zip_code)
    new_noaa.make_graph()
    plt.show()
    pass