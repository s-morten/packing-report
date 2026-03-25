# packing-report

This project aims to rate football players on different metrics, but on a player basis. Meaning only the time of a player on the pitch is counted. However the action the player is rated on doesnt necessarily needs to be executed by him. A goal counts for the complete team, as does a goal conceded. This furthers the idea of indirect impact of a football player on the pitch that isnt directly observable from direct actions.  
This calculated metrics could be used for player evaluation or comparison and later for team comparison and score prediction. 

### Metrics
- GDE - Goal Difference Elo. An ELO like system, rating players on their margin of victory results in games. Should be an advancement of the plus-minus score known from basketball. 
- xT-impact - The proportional expected Thread impact of a player during a game.

### Metric Backlog
- time to ball recovery
- average distance to opposition / seperation (tracking data needed)

### Code functionality. 
The code downloads and scrapes necessary data for the analysis.  
For each game the metrics are calculated on a per player base and stored in an Oracle Database in the Oracle cloud.
