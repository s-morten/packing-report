import logging
import socceraction.xthreat as xthreat

# gloabl vars
DEBUG = False
LEAGUE_LIST = [
    "GER-Bundesliga",
    "GER-Bundesliga2",
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "ITA-Serie A",
]


def init_logging():
    logger = logging.getLogger()
    fhandler = logging.FileHandler(filename="mylog.log", mode="a")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fhandler.setFormatter(formatter)
    logger.addHandler(fhandler)
    logger.setLevel(logging.INFO)

    return logger


def get_xT_modell():
    xTModell = xthreat.load_model(
        "/home/morten/Develop/packing-report/xT-impact/models/xT_full_data"
    )
    return xTModell
