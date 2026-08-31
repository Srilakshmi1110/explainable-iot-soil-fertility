/*
  SOIL FERTILITY IoT READER
  Sends REAL pH + moisture readings to the Flask backend over USB serial.

  Serial format:
      pH,moisture
  Example:
      6.82,47.5

  IMPORTANT:
  The pH calibration constants below are placeholders from the original
  project and MUST be calibrated for your actual pH sensor before use.
  Nitrogen and CEC are NOT fabricated by Arduino; the backend reads those
  values from the supplied soil raster layers at the field location.
*/

const int PH_PIN = A0;
const int MOISTURE_PIN = A1;

const float PH_OFFSET = -1.889;
const float PH_SLOPE = 0.0178;

const int MOISTURE_DRY_VALUE = 1023;
const int MOISTURE_WET_VALUE = 300;

void setup() {
  Serial.begin(9600);
  delay(1000);
  Serial.println("SOIL_IOT_READY");
}

void loop() {
  int rawPH = analogRead(PH_PIN);
  int rawMoisture = analogRead(MOISTURE_PIN);

  float ph = PH_OFFSET + (PH_SLOPE * rawPH);
  ph = constrain(ph, 0.0, 14.0);

  float moisture = ((float)(MOISTURE_DRY_VALUE - rawMoisture) /
                    (MOISTURE_DRY_VALUE - MOISTURE_WET_VALUE)) * 100.0;
  moisture = constrain(moisture, 0.0, 100.0);

  Serial.print(ph, 2);
  Serial.print(",");
  Serial.println(moisture, 1);

  delay(2000);
}
