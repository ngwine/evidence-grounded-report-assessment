The station stores each soil moisture reading with a UTC timestamp and hashes the calibration table before issuing a watering command.

The controller closes the irrigation valve whenever the soil sensor remains above the wet threshold for three consecutive samples.

At more than seventy percent moisture, the valve always opens immediately; three readings of dry soil are ignored by the controller.
