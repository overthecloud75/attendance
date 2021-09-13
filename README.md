# ATTENDANCE
### 1. Result
![attendance](https://user-images.githubusercontent.com/30888482/114798899-6c8f7a00-9dd1-11eb-87ce-b51c11469fce.PNG)
### 2. How to check attendance?
Fingerprint recognition is connected to Access file. <br>
When a smartphone is connected to wifi-network in the company, the server can check mac-address in the wifi-network.
### 3. Usage
py -3.7 main.py <br>
http://127.0.0.1:5000
### 4. Acknowledgements
To connect 32bit Access file, this implementation has been tested with 32bit Python 3.7.9 <br>
Npcap (https://nmap.org/npcap/) is needed To use scapy library in Windows.
### 5. References
https://wikidocs.net/book/4542 (flask)<br>
https://pypi.org/project/pyodbc/ (to connect Access file of ADT ADserver) <br>
https://pypi.org/project/Office365-REST-Python-Client/ (to get sharepoint calendar data) <br>
https://stackoverflow.com/questions/39902405/fullcalendar-in-django (fullcalendar.js with flask) <br>
https://gist.github.com/doobeh/3e685ef25fac7d03ded7 (datepicker with flask)
