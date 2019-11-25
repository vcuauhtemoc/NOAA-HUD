# NOAA-HUD

Important variables:

    historical_weather_df: holds the historical weather information, ordered from oldest to newest datapoint.
    
    humidity_data: list containing humidity forecast data 
    
    datapoint_tuples: tuple list (timestamp, humidity) with concatenated historical weather and forecast weather. Passed to humidity_df to be a plot-able dataframe.
    
    humidity_df: The dataframe used in graphing. contains humidity_datapoint for data. 
