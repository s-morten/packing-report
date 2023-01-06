# GP_Stehr - Football InGame Live-Win-Probability
## Zeitplan
- [x] Finish Data Preparation until 10.04 
  - [x] xT has no carry  
  - [x] goal scroing opportunities
  - [x] duel strength
  - [x] Daten aquise/umwandlung performanter machen
- [x] statistische Grundlagen until ~~17.04~~ 01.05
  - [x] poisson verteilung
  - [x] bayes
  - [x] probabilistic programming pymc3
- [ ] Modelle entwickeln bis 15.05
  - [x] Heim Model bauen und trainieren
  - [x] Auswärts Model bauen und trainieren
  - [x] save traces
  - [ ] Modelle evaluieren
  - [ ] mcmc vs advi
- [ ] More Data Preperation bis ???
  - [ ] Duel Strength -> is used TakeOn event the same es the stasbomb duel stat. Is it enough? Add recovery?  
  - [x] change Cards to card diff
  - [x] try statsbomb xG for xT calc
  - [ ] t in feature space
  - [ ] more data?
- [ ] Model visualization similar to paper
  - [ ] create probability matrix
  - [x] create "gameflow" chart

## Ziel
Das Ziel ist es das beiliegende Paper von Robberechts et al. nachzuimplementieren. Das Resultat ist ein Modell zur Live Vorhersage des Gewinners eines Fussballspiels.

### Modell
Modellierung / Berechnung der Anzahl der Tore, die ein Team (noch) schiessen wird. Also die Wahrscheinlchkeitsverteilung der Anzahl der Tore die jedes Team schiessen wird für den Zeitraum t+1 und EoM. Daraus werden die Sieg-Unentschieden-Niederlage Wahrscheinlichkeiten abgeleitet. Die erwartete Anzahl der Tore nach Zeitpunkt t wird als unabhängige Poisson-Verteilung modelliert. Um die Features/"scoring intensity parameters" darzustellen wird ein zeitlicher stochastischer Prozess (temporal stochastic process) verwendet. Dieser Ansatz erlaubt das teilen von Informationen zwischen den Zeitschritten. Diese werden als mathematische Verteilungen in einem Bayeschen Programm implementiert. Variational Inference Algorithmen werden genutzt um die Parameter mittels historischer Daten zu inferieren.  

### Features
Basic Features: Game Time, Score differential  
Team Strength Features: (ELO)?  
Contextual Features: Team Goals, Red Cards, Yellow Cards, Goal Scoring Opportunities, Attacking Passes, xT, Duel Strength  

### Daten
Als Daten werden die freizugänglichen Eventdaten von Statsbomb verwendet. Diese Umfassen die letzten drei Saisons der Englischen Frauen Liga.   