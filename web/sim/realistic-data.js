/**
 * Realistic Mock Data System for ESP32 Display Simulator
 * Provides time-aware scenarios, weather progressions, and realistic sensor variations
 */

(function() {
  'use strict';

  // Weather conditions with associated data ranges
  const WEATHER_CONDITIONS = {
    sunny: { 
      tempModifier: 5, 
      humidityRange: [25, 45], 
      pressureRange: [1015, 1025],
      windRange: [0, 8],
      nextConditions: ['sunny', 'sunny', 'partly-cloudy']
    },
    'partly-cloudy': { 
      tempModifier: 2, 
      humidityRange: [35, 55], 
      pressureRange: [1010, 1020],
      windRange: [3, 12],
      nextConditions: ['sunny', 'partly-cloudy', 'cloudy']
    },
    cloudy: { 
      tempModifier: -2, 
      humidityRange: [50, 70], 
      pressureRange: [1005, 1015],
      windRange: [5, 15],
      nextConditions: ['partly-cloudy', 'cloudy', 'rainy', 'fog']
    },
    rainy: { 
      tempModifier: -5, 
      humidityRange: [70, 95], 
      pressureRange: [995, 1010],
      windRange: [8, 20],
      nextConditions: ['rainy', 'cloudy', 'thunderstorm']
    },
    thunderstorm: { 
      tempModifier: -8, 
      humidityRange: [80, 98], 
      pressureRange: [985, 1000],
      windRange: [15, 35],
      nextConditions: ['rainy', 'cloudy']
    },
    snow: { 
      tempModifier: -15, 
      humidityRange: [60, 85], 
      pressureRange: [1000, 1015],
      windRange: [5, 20],
      nextConditions: ['snow', 'cloudy', 'fog']
    },
    fog: { 
      tempModifier: -3, 
      humidityRange: [85, 100], 
      pressureRange: [1010, 1020],
      windRange: [0, 5],
      nextConditions: ['fog', 'cloudy', 'partly-cloudy']
    },
    'clear-night': { 
      tempModifier: -8, 
      humidityRange: [40, 65], 
      pressureRange: [1015, 1025],
      windRange: [0, 8],
      nextConditions: ['clear-night', 'partly-cloudy']
    },
    windy: {
      tempModifier: 0,
      humidityRange: [30, 50],
      pressureRange: [1005, 1015],
      windRange: [20, 45],
      nextConditions: ['windy', 'partly-cloudy', 'cloudy']
    }
  };

  // Seasonal temperature baselines (outdoor, in Fahrenheit)
  const SEASONAL_TEMPS = {
    spring: { baseTemp: 58, variation: 15, humidity: 55 },
    summer: { baseTemp: 78, variation: 12, humidity: 45 },
    fall: { baseTemp: 52, variation: 18, humidity: 60 },
    winter: { baseTemp: 35, variation: 20, humidity: 50 }
  };

  // Geographic presets
  const GEOGRAPHIC_PRESETS = {
    coastal: { 
      tempVariation: 0.7, // Less variation
      humidityBase: 70,
      pressureBase: 1015,
      commonWeather: ['partly-cloudy', 'cloudy', 'fog']
    },
    desert: { 
      tempVariation: 1.5, // More variation
      humidityBase: 20,
      pressureBase: 1010,
      commonWeather: ['sunny', 'sunny', 'partly-cloudy']
    },
    mountain: { 
      tempVariation: 1.3,
      humidityBase: 40,
      pressureBase: 850, // Lower altitude pressure
      commonWeather: ['sunny', 'partly-cloudy', 'snow']
    },
    midwest: { 
      tempVariation: 1.2,
      humidityBase: 55,
      pressureBase: 1013,
      commonWeather: ['sunny', 'partly-cloudy', 'cloudy', 'thunderstorm']
    },
    tropical: {
      tempVariation: 0.5,
      humidityBase: 80,
      pressureBase: 1010,
      commonWeather: ['sunny', 'rainy', 'thunderstorm', 'partly-cloudy']
    }
  };

  // Room name variations
  const ROOM_NAMES = [
    'Office', 'Living Room', 'Bedroom', 'Kitchen', 'Garage',
    'Workshop', 'Studio', 'Den', 'Basement', 'Attic',
    'Guest Room', 'Home Office', 'Lab', 'Server Room', 'Greenhouse'
  ];

  /**
   * SimulatedEnvironment class - generates realistic sensor data
   */
  class SimulatedEnvironment {
    constructor(options = {}) {
      this.season = options.season || this.getCurrentSeason();
      this.geography = options.geography || 'midwest';
      this.roomName = options.roomName || 'Office';
      this.currentWeather = options.weather || 'sunny';
      this.indoorTemp = options.indoorTemp || 72;
      this.batteryPercent = options.batteryPercent || 100;
      this.batteryDrainRate = options.batteryDrainRate || 0.01; // % per minute
      this.daysRunning = options.daysRunning || 0;
      this.lastUpdate = Date.now();
      this.weatherChangeInterval = options.weatherChangeInterval || 30; // minutes
      this.lastWeatherChange = Date.now();
      
      // Sensor noise/drift settings
      this.noiseLevel = options.noiseLevel || 0.5;
      this.driftEnabled = options.driftEnabled !== false;
      
      // Internal state
      this._pressureTrend = 0; // -1 falling, 0 stable, 1 rising
      this._tempDrift = 0;
    }

    getCurrentSeason() {
      const month = new Date().getMonth();
      if (month >= 2 && month <= 4) return 'spring';
      if (month >= 5 && month <= 7) return 'summer';
      if (month >= 8 && month <= 10) return 'fall';
      return 'winter';
    }

    getTimeOfDay(date = new Date()) {
      const hour = date.getHours();
      if (hour >= 5 && hour < 11) return 'morning';
      if (hour >= 11 && hour < 17) return 'afternoon';
      if (hour >= 17 && hour < 21) return 'evening';
      return 'night';
    }

    /**
     * Get time-based temperature modifier
     */
    getTimeModifier(date = new Date()) {
      const hour = date.getHours();
      // Temperature curve: lowest at 5am, highest at 3pm
      const peakHour = 15;
      const lowHour = 5;
      
      // Sine wave approximation of daily temperature cycle
      const hourAngle = ((hour - lowHour) / 24) * 2 * Math.PI;
      return Math.sin(hourAngle) * 8; // +/- 8°F variation
    }

    /**
     * Add realistic sensor noise
     */
    addNoise(value, range = 0.5) {
      if (!this.driftEnabled) return value;
      return value + (Math.random() - 0.5) * 2 * range * this.noiseLevel;
    }

    /**
     * Simulate weather progression
     */
    updateWeather() {
      const now = Date.now();
      const minutesSinceChange = (now - this.lastWeatherChange) / (1000 * 60);
      
      if (minutesSinceChange >= this.weatherChangeInterval) {
        const conditions = WEATHER_CONDITIONS[this.currentWeather];
        if (conditions && conditions.nextConditions) {
          const nextOptions = conditions.nextConditions;
          this.currentWeather = nextOptions[Math.floor(Math.random() * nextOptions.length)];
          this.lastWeatherChange = now;
          
          // Update pressure trend based on weather change
          if (this.currentWeather === 'rainy' || this.currentWeather === 'thunderstorm') {
            this._pressureTrend = -1;
          } else if (this.currentWeather === 'sunny') {
            this._pressureTrend = 1;
          } else {
            this._pressureTrend = 0;
          }
        }
      }
      
      return this.currentWeather;
    }

    /**
     * Simulate battery drain
     */
    updateBattery(elapsedMinutes) {
      this.batteryPercent = Math.max(0, this.batteryPercent - (this.batteryDrainRate * elapsedMinutes));
      return this.batteryPercent;
    }

    /**
     * Generate a complete realistic data snapshot
     */
    generateSnapshot(options = {}) {
      const now = options.date || new Date();
      const elapsed = (Date.now() - this.lastUpdate) / (1000 * 60); // minutes
      this.lastUpdate = Date.now();
      
      // Update weather
      const weather = this.updateWeather();
      const weatherData = WEATHER_CONDITIONS[weather] || WEATHER_CONDITIONS.sunny;
      
      // Update battery
      this.updateBattery(elapsed);
      this.daysRunning += elapsed / (24 * 60);
      
      // Get seasonal and geographic modifiers
      const seasonData = SEASONAL_TEMPS[this.season];
      const geoData = GEOGRAPHIC_PRESETS[this.geography];
      
      // Calculate outdoor temperature
      const timeModifier = this.getTimeModifier(now);
      const baseOutdoorTemp = seasonData.baseTemp + 
                             (weatherData.tempModifier || 0) + 
                             timeModifier * geoData.tempVariation;
      const outdoorTemp = this.addNoise(baseOutdoorTemp, 1.5);
      
      // Indoor temperature (more stable, tends toward thermostat setting)
      const thermostatTarget = 72;
      this.indoorTemp = this.indoorTemp + (thermostatTarget - this.indoorTemp) * 0.1;
      this.indoorTemp = this.addNoise(this.indoorTemp, 0.3);
      
      // Humidity
      const [humMin, humMax] = weatherData.humidityRange;
      const baseHumidity = (humMin + humMax) / 2 + (geoData.humidityBase - 50) * 0.3;
      const outdoorHumidity = Math.min(100, Math.max(0, this.addNoise(baseHumidity, 5)));
      const indoorHumidity = Math.min(100, Math.max(0, this.addNoise(45 + (outdoorHumidity - 50) * 0.2, 3)));
      
      // Pressure (with trend)
      const [pressMin, pressMax] = weatherData.pressureRange;
      let basePressure = geoData.pressureBase + (this._pressureTrend * 3);
      basePressure = Math.min(pressMax, Math.max(pressMin, basePressure));
      const pressure = this.addNoise(basePressure, 2);
      
      // Wind
      const [windMin, windMax] = weatherData.windRange;
      const windMph = this.addNoise((windMin + windMax) / 2, (windMax - windMin) / 4);
      
      // Battery voltage from percentage
      const batteryVoltage = 3.3 + (this.batteryPercent / 100) * 0.9;
      
      // Format time
      const hours = now.getHours();
      const minutes = now.getMinutes();
      const timeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
      
      // Select weather condition for night
      let displayWeather = weather;
      if (hours >= 20 || hours < 6) {
        if (weather === 'sunny') displayWeather = 'clear-night';
        else if (weather === 'partly-cloudy') displayWeather = 'night-partly-cloudy';
      }
      
      return {
        room_name: this.roomName,
        time_hhmm: timeStr,
        inside_temp_f: Math.round(this.indoorTemp * 10) / 10,
        inside_hum_pct: Math.round(indoorHumidity),
        outside_temp_f: Math.round(outdoorTemp * 10) / 10,
        outside_hum_pct: Math.round(outdoorHumidity),
        outside_pressure_hpa: Math.round(pressure * 10) / 10,
        pressure_hpa: Math.round((pressure + this.addNoise(0, 0.5)) * 10) / 10,
        weather: displayWeather,
        wind_mph: Math.round(Math.max(0, windMph) * 10) / 10,
        wind_mps: Math.round(Math.max(0, windMph * 0.447) * 100) / 100,
        battery_percent: Math.round(this.batteryPercent),
        battery_voltage: Math.round(batteryVoltage * 100) / 100,
        days: Math.floor(this.daysRunning).toString(),
        ip: '192.168.1.42',
        fw_version: '1.05'
      };
    }
  }

  /**
   * Quick scenario presets
   */
  const SCENARIO_PRESETS = {
    // Time of day scenarios
    early_morning: () => {
      const env = new SimulatedEnvironment({ weather: 'fog' });
      const data = env.generateSnapshot({ date: new Date(2024, 5, 15, 6, 15) });
      data.inside_temp_f = 68.5;
      data.outside_temp_f = 52.3;
      return data;
    },
    
    hot_afternoon: () => {
      const env = new SimulatedEnvironment({ season: 'summer', weather: 'sunny', geography: 'desert' });
      const data = env.generateSnapshot({ date: new Date(2024, 7, 10, 14, 30) });
      data.inside_temp_f = 76.8;
      data.outside_temp_f = 98.5;
      return data;
    },
    
    rainy_evening: () => {
      const env = new SimulatedEnvironment({ weather: 'rainy' });
      const data = env.generateSnapshot({ date: new Date(2024, 9, 20, 19, 45) });
      data.inside_temp_f = 71.2;
      data.outside_temp_f = 55.8;
      data.outside_hum_pct = 92;
      return data;
    },
    
    cold_night: () => {
      const env = new SimulatedEnvironment({ season: 'winter', weather: 'clear-night' });
      const data = env.generateSnapshot({ date: new Date(2024, 0, 15, 23, 30) });
      data.inside_temp_f = 69.0;
      data.outside_temp_f = 18.5;
      return data;
    },
    
    // Weather scenarios
    thunderstorm: () => {
      const env = new SimulatedEnvironment({ weather: 'thunderstorm' });
      const data = env.generateSnapshot();
      data.wind_mph = 28.5;
      data.pressure_hpa = 992.3;
      return data;
    },
    
    snow_day: () => {
      const env = new SimulatedEnvironment({ season: 'winter', weather: 'snow', geography: 'mountain' });
      const data = env.generateSnapshot({ date: new Date(2024, 11, 20, 10, 0) });
      data.inside_temp_f = 70.0;
      data.outside_temp_f = 28.5;
      data.outside_hum_pct = 78;
      return data;
    },
    
    windy_day: () => {
      const env = new SimulatedEnvironment({ weather: 'windy' });
      const data = env.generateSnapshot();
      data.wind_mph = 32.5;
      return data;
    },
    
    // Battery scenarios
    battery_critical: () => {
      const env = new SimulatedEnvironment({ batteryPercent: 5 });
      const data = env.generateSnapshot();
      data.battery_percent = 5;
      data.battery_voltage = 3.35;
      data.days = '180';
      return data;
    },
    
    battery_charging: () => {
      const data = new SimulatedEnvironment().generateSnapshot();
      data.battery_percent = 65;
      data.battery_voltage = 4.15;
      data.charging = true;
      return data;
    },
    
    // Geographic scenarios  
    coastal_morning: () => {
      const env = new SimulatedEnvironment({ geography: 'coastal', weather: 'fog' });
      const data = env.generateSnapshot({ date: new Date(2024, 6, 15, 7, 30) });
      data.room_name = 'Beach House';
      return data;
    },
    
    tropical_afternoon: () => {
      const env = new SimulatedEnvironment({ geography: 'tropical', season: 'summer', weather: 'partly-cloudy' });
      const data = env.generateSnapshot({ date: new Date(2024, 7, 20, 14, 0) });
      data.room_name = 'Lanai';
      data.inside_temp_f = 79.5;
      data.outside_temp_f = 88.2;
      data.outside_hum_pct = 85;
      return data;
    },
    
    mountain_cabin: () => {
      const env = new SimulatedEnvironment({ geography: 'mountain', weather: 'sunny' });
      const data = env.generateSnapshot();
      data.room_name = 'Cabin';
      data.pressure_hpa = 845.2;
      data.outside_pressure_hpa = 845.0;
      return data;
    },
    
    // Edge case scenarios
    extreme_cold: () => ({
      room_name: 'Arctic Lab',
      time_hhmm: '12:00',
      inside_temp_f: 55.0,
      inside_hum_pct: 20,
      outside_temp_f: -35.5,
      outside_hum_pct: 45,
      outside_pressure_hpa: 1035.0,
      pressure_hpa: 1034.5,
      weather: 'snow',
      wind_mph: 15.0,
      wind_mps: 6.7,
      battery_percent: 42,
      battery_voltage: 3.75,
      days: '90',
      ip: '192.168.1.42',
      fw_version: '1.05'
    }),
    
    extreme_heat: () => ({
      room_name: 'Desert Lab',
      time_hhmm: '15:30',
      inside_temp_f: 82.0,
      inside_hum_pct: 18,
      outside_temp_f: 118.5,
      outside_hum_pct: 8,
      outside_pressure_hpa: 1008.0,
      pressure_hpa: 1008.2,
      weather: 'sunny',
      wind_mph: 5.0,
      wind_mps: 2.24,
      battery_percent: 58,
      battery_voltage: 3.85,
      days: '45',
      ip: '192.168.1.42',
      fw_version: '1.05'
    }),
    
    high_humidity: () => ({
      room_name: 'Greenhouse',
      time_hhmm: '8:45',
      inside_temp_f: 78.5,
      inside_hum_pct: 85,
      outside_temp_f: 72.0,
      outside_hum_pct: 98,
      outside_pressure_hpa: 1002.0,
      pressure_hpa: 1002.5,
      weather: 'rainy',
      wind_mph: 2.5,
      wind_mps: 1.12,
      battery_percent: 88,
      battery_voltage: 4.05,
      days: '12',
      ip: '192.168.1.42',
      fw_version: '1.05'
    })
  };

  /**
   * Live simulation mode - cycles through realistic daily patterns
   */
  class LiveSimulation {
    constructor(options = {}) {
      this.environment = new SimulatedEnvironment(options);
      this.speed = options.speed || 60; // 1 real second = 60 simulated seconds
      this.running = false;
      this.intervalId = null;
      this.onUpdate = options.onUpdate || (() => {});
      this.simulatedDate = options.startDate || new Date();
    }

    start() {
      if (this.running) return;
      this.running = true;
      
      const tick = () => {
        // Advance simulated time
        this.simulatedDate = new Date(this.simulatedDate.getTime() + (this.speed * 1000));
        
        // Generate and emit data
        const data = this.environment.generateSnapshot({ date: this.simulatedDate });
        this.onUpdate(data);
      };
      
      // Initial tick
      tick();
      
      // Continue ticking
      this.intervalId = setInterval(tick, 1000);
    }

    stop() {
      this.running = false;
      if (this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
    }

    setSpeed(speed) {
      this.speed = speed;
    }

    setSeason(season) {
      this.environment.season = season;
    }

    setGeography(geography) {
      this.environment.geography = geography;
    }

    setWeather(weather) {
      this.environment.currentWeather = weather;
      this.environment.lastWeatherChange = Date.now();
    }
  }

  // Export to window
  window.SimulatedEnvironment = SimulatedEnvironment;
  window.LiveSimulation = LiveSimulation;
  window.SCENARIO_PRESETS = SCENARIO_PRESETS;
  window.WEATHER_CONDITIONS = WEATHER_CONDITIONS;
  window.SEASONAL_TEMPS = SEASONAL_TEMPS;
  window.GEOGRAPHIC_PRESETS = GEOGRAPHIC_PRESETS;
  window.ROOM_NAMES = ROOM_NAMES;

})();

