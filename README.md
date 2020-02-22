# NOAA-HUD

Weather display intended to run on an e-ink display, with a focus on aesthetic. What I believe to be unique about this app, is that rather than simply display a forecast, the display gives you 3-day historical weather, 3-day forecast, with the current time centered on the graph. It will also display current conditions outside of the graph. 

## Current status:

User can input a zip code only, to retrieve their closest weather station. This also grabs a city/state location from the weather station. You might get a different city name than corresponds to the zip code, because the chosen weather station may be in close proximity, but in a different city. 

Once the user inputs a valid zip code, the program then retrieves forecast data and historical weather data from the National Weather Service, from two separate databases. After a lot of re-formatting and getting everything to work based on datetime indexes, two pandas databases are merged and fed to Matplotlib. The program again prompts the user, this time asking which weather parameters the user wants displayed on the graph. Any time indexes missing datapoints are dealt with using the DataFrame interpolate() method, which is a linear interpolation. 

## Next steps:

### Refining the display:

    - Fix overlapping weather attribute labels on graph

### Adding a current conditions section

    - use an icon pack for weather conditions
    - more to come :)
