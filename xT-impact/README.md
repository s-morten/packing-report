# xT-impact / Hauptprojekt Morten Stehr

This directory contains the Hauptprojekt of Morten Stehr. The aim is to create a Bayesian Game prediction model in Python. The model uses different data aspects like goalscoring form for and against and xT / xG per team to predict game results of the leagues Bundesliga, Bundesliga 2, La Liga, Ligue 1, Premier League, Serie A. The Data is scraped from WhoScored using the library [soccerdata](https://github.com/probberechts/soccerdata). xT and xG are calculated using a modified version of [socceraction](https://github.com/ML-KULeuven/socceraction).

pymc: Home of the developed Bayesian model and its modifications. Including the evaluation of the models. 

data_aquisation: Scrape and inspect the data, aswell as creating training and test data.

get_2_know_soccerdata: Calculate xT/xG using a for this purposes modified fork of the soccerdata library.  

**Nicht HP relevant**, proto_files: Protobuf is used as a database. The calculated values for players are stored in protobuf files, as well as tables and schedules for the running season. The .proto files and the created .py files are home in this folder.

**Nicht HP relevant**, dnn: First steps for the Master Thesis. 