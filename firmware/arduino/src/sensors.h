#pragma once

struct InsideReadings {
    float temperatureC = NAN;
    float humidityPct = NAN;
};

// TODO: implement SHT40/BME280 read helpers in subsequent increments
inline InsideReadings read_inside_sensors() {
    InsideReadings r;
    return r;
}


