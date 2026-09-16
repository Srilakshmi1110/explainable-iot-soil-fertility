// =====================================================
// Soil Fertility Project - Arduino Sensor Reader
// Sensors:
//   Moisture sensor  -> A0
//   pH sensor        -> A1
//   10K thermistor   -> A2
//
// Serial output:
//   pH,moisture,temperature
//
// Example:
//   6.50,65.20,27.40
// =====================================================

const int MOISTURE_PIN = A0;
const int PH_PIN = A1;
const int THERMISTOR_PIN = A2;

// ---------- Thermistor settings ----------
const float SERIES_RESISTOR = 10000.0;
const float NOMINAL_RESISTANCE = 10000.0;
const float NOMINAL_TEMPERATURE = 25.0;
const float BETA_COEFFICIENT = 3950.0;

// ---------- pH settings ----------
// These are initial calibration values.
// Calibrate later using pH buffer solutions.
const float PH_NEUTRAL_VOLTAGE = 2.50;
const float PH_SLOPE = 0.18;


// =====================================================
// SETUP
// =====================================================

void setup() {
  Serial.begin(9600);

  pinMode(MOISTURE_PIN, INPUT);
  pinMode(PH_PIN, INPUT);
  pinMode(THERMISTOR_PIN, INPUT);

  delay(1000);

  Serial.println("SOIL_SENSOR_READY");
  Serial.println("pH,moisture,temperature");
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // ---------------------------------------------------
  // 1. READ MOISTURE
  // ---------------------------------------------------

  int moistureRaw = analogRead(MOISTURE_PIN);

  // Convert raw ADC value to percentage.
  // Adjust these values after testing your actual sensor.
  float moisture = map(moistureRaw, 1023, 0, 0, 100);

  moisture = constrain(moisture, 0, 100);


  // ---------------------------------------------------
  // 2. READ pH
  // ---------------------------------------------------

  int phRaw = analogRead(PH_PIN);

  float phVoltage = phRaw * (5.0 / 1023.0);

  float ph = 7.0 +
             ((PH_NEUTRAL_VOLTAGE - phVoltage) / PH_SLOPE);

  ph = constrain(ph, 0, 14);


  // ---------------------------------------------------
  // 3. READ 10K NTC THERMISTOR
  // ---------------------------------------------------

  int thermistorRaw = analogRead(THERMISTOR_PIN);

  if (thermistorRaw <= 0) {
    thermistorRaw = 1;
  }

  if (thermistorRaw >= 1023) {
    thermistorRaw = 1022;
  }

  float resistance =
      SERIES_RESISTOR /
      ((1023.0 / thermistorRaw) - 1.0);

  float steinhart;

  steinhart =
      resistance / NOMINAL_RESISTANCE;

  steinhart =
      log(steinhart);

  steinhart /= BETA_COEFFICIENT;

  steinhart +=
      1.0 / (NOMINAL_TEMPERATURE + 273.15);

  steinhart =
      1.0 / steinhart;

  float temperature =
      steinhart - 273.15;


  // ---------------------------------------------------
  // 4. SEND DATA TO PYTHON
  // ---------------------------------------------------

  Serial.print(ph, 2);
  Serial.print(",");

  Serial.print(moisture, 2);
  Serial.print(",");

  Serial.println(temperature, 2);


  // Send a reading every second
  delay(1000);
}