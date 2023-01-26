# xT-impact

V-0.3
Game prediction Framework in Python. The model uses different data aspects like goalscoring form for and against and xT / xG per team to predict game results of the leagues Bundesliga, Bundesliga 2, La Liga, Ligue 1, Premier League, Serie A. The Data is scraped from WhoScored using the library [soccerdata](https://github.com/probberechts/soccerdata). xT and xG are calculated using a modified version of [socceraction](https://github.com/ML-KULeuven/socceraction).


automation: This folder contains scripts to execute the prediction of games automatically. 

data_aquisation: Notebook to scrape and inspect the data, aswell as creating training and test data.

get_2_know_soccerdata: notebooks to calculate xT/xG using socceraction.

proto_files: The calculated values for players are stored in protobuf files, as well as tables and schedules for the running season. The .proto files and the created .py files are home in this folder.

pymc: Development of the Baysian prediction model used to predict the games. 