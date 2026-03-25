import soccerdata as sd
from pathlib import PosixPath
import toml


class WhoScoredScraper:
    def __init__(self, live, config_path, cache_path, chrome_path):

        run_config = toml.load(config_path)
        self.scraper = sd.WhoScored(
            leagues=run_config["whoscored"]["leagues"],
            seasons=run_config["whoscored"]["seasons"],
            no_cache=live,
            no_store=False,
            data_dir=PosixPath(cache_path),
            path_to_browser=chrome_path,
            headless=False,
        )

    def scrape_games(self):
        events = self.scraper.read_events()