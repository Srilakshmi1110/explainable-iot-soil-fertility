SOILAI COMPLETE BUILD
=====================

1. Keep the original .tif files in backend/data/:
   ph.tif, moisture.tif, nitrogen.tif, cec.tif

2. Replace your project files with these versions.
3. Activate the Python 3.10 virtual environment.
4. Install requirements:
   python -m pip install -r requirements.txt
5. Edit config.py if your Arduino COM port is not COM3.
6. Start:
   python backend/app.py
7. Open:
   http://localhost:5000

FIRST USE:
- Create an account.
- Click "Use my current location".
- Connect/upload the Arduino sketch.
- Do not open Arduino Serial Monitor while Flask is using the COM port.
- The dashboard will remain blank until real Arduino data arrives.
