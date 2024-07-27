import pandas as pd
import numpy as np
import sqlite3

import requests
from bs4 import BeautifulSoup
from time import sleep
import pickle
import os
import json

from collections import defaultdict
import filesystem_io.filesystem_io as filesystem_io
from database_io.db_handler import DB_handler

class Footballsquads_scraper:
    def __init__(self, cache_location:str, db_handler: DB_handler) -> None:
        self.FORBIDDEN_URLS = [
            "index.html",
            "forums",
            "search.htm",
            "contact.htm",
            "pripol.htm",
            "tou.htm",
            "squads.htm",
            "national.htm",
            "mailto:info@footballsquads.com", 
            "features.htm",
            "credits.htm",
            "links.htm"
        ]
        # URL to scrape
        self.url_archive = "http://www.footballsquads.co.uk/archive.htm"
        self.cache_location = cache_location
        self.db_handler = db_handler
    # How to test?
    def fetch_all_links_on_page(self, url: str) -> list[str]:
        link_list = []
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.find_all("a")
        
        for link in links:
            href = link.get("href")
            if href:
                link_list.append(href)
        return self.remove_unwanted_urls(link_list)
    
    # How to test?
    def scrape_kit_number_table(self, url: str) -> bytes:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        else:
            print("Failed to fetch the page. Status code:", response.status_code)
            raise ValueError(f"Failed scraping {url}")

    def extract_numbers_from_html_table(self, html_table: bytes) -> defaultdict[int:list]:
        kit_numbers = defaultdict(list)
        soup = BeautifulSoup(html_table, "html.parser")
        table = soup.find("div", {"id": "main"})
        if table:
            rows = table.find_all("tr")
            # Loop through rows and extract data
            for row in rows:
                # Extract table data from each row
                cells = row.find_all(["th", "td"])
                row_data = []
                for cell in cells:
                    # Check if the cell contains italic text
                    italic_text = cell.find("i")
                    if italic_text:
                        # If italic text is present, add it to row_data
                        row_data.append(italic_text.get_text(strip=True))
                    else:
                        # If no italic text, add the regular text
                        row_data.append(cell.get_text(strip=True))
                    # Print row data
                if (
                    self.validate_row_data(row_data)
                    and (key := row_data[0]) not in kit_numbers
                ):
                    kit_numbers[key] = row_data[1:]
        else:
            raise ValueError("Table not found on the page.")
        return kit_numbers

    def validate_row_data(self, row: list[str]) -> bool:
        if (row is None) or len(row) < 2:
            return False
        return (row[0].isdigit() and bool(row[1]))
    
    def remove_unwanted_urls(self, url_list: list[str]) -> list[str]:
        allowed_urls = url_list.copy()
        for url in url_list:
            for forbidden_fruit in self.FORBIDDEN_URLS:
                if forbidden_fruit in url:
                    allowed_urls.remove(url)
        return allowed_urls
              
    def scrape_archive(self):
        # get top level leagues/seasons
        season_links = self.fetch_all_links_on_page(self.url_archive)
        # get clubs
        for league_season in season_links:
            teams = self.fetch_all_links_on_page(f"http://www.footballsquads.co.uk/{league_season}")
            league_str = league_season.split("/")[2].split(".")[0]
            season_str = league_season.split("/")[1]
            country_str = league_season.split("/")[0]
            for team_url in teams:
                scrape_url = f"http://www.footballsquads.co.uk/{country_str}/{season_str}/{team_url}"
                team_name = team_url.split("/")[1].split(".")[0]
                file_path = f"{season_str}_{country_str}_{league_str}_{team_name}.pckl"
                if not filesystem_io.file_in_directory(file_path, self.cache_location):
                    print(f"Fetching {scrape_url}")
                    kit_number_table_bytes = self.scrape_kit_number_table(scrape_url)
                    kit_number_table = self.extract_numbers_from_html_table(kit_number_table_bytes)
                else:
                    print("Data found in cache, skip")
                    continue
                if not kit_number_table:
                    raise ValueError("No kit number table found!")
                filesystem_io.footballsquads_table_to_file(kit_number_table, 
                                     self.cache_location + "/" + file_path)
                sleep(1)



    def cache_to_db(self, leagues: list[str] | None=None):

        # get already processed files
        already_processed_files = self.db_handler.player_age.get_processed_player_age_files()
        cache_file_list = filesystem_io.directory_files(self.cache_location)
        # remove already processed files
        cache_file_list_removed = [
            i for i in cache_file_list if i not in already_processed_files
        ]
        # get infos like team, league and season.
        for cache_file in cache_file_list_removed:
            scraped_infos = self.scrape_infos_from_filename(
                cache_file
            )
            if (scraped_infos is None):
                continue
            replaced_team_name = scraped_infos[0]
            replaced_league = scraped_infos[1]
            scraped_season = scraped_infos[2]


            if (leagues is not None) and (replaced_league not in leagues):
                continue
            age_table = filesystem_io.footballsquads_table_from_file(self.cache_location + cache_file)
            for kit_number in age_table:
                player_information = age_table[kit_number]
                if len(player_information) < 8:
                    # errorenous data, skip
                    continue
                self.db_handler.player_age.player_age_to_sql([kit_number, *player_information, replaced_team_name, replaced_league, scraped_season])
            self.db_handler.player_age.update_processed_player_age(cache_file)


    def scrape_infos_from_filename(self, file_name):
        file_name_split = file_name.split("_")
        team_name = file_name_split[3].split(".")[0]
        league = file_name_split[2]
        season = file_name_split[0].replace("-", "/")
        replaced_league = replace_from_config(league, "league")
        replaced_team_name = replace_from_config(team_name, "teamname")
        
        if (replaced_team_name is None) and (replaced_league is not None):
            return None
        if (replaced_team_name is None) and (replaced_league is not None):
            print(f"WARNING missing name replacement for team {team_name}")
            return None
        if (replaced_team_name is not None) and (replaced_league is not None):
            return replaced_team_name, replaced_league, season    
            
def replace_from_config(initial_name: str, what: str):
    if what not in ["league", "teamname"]:
        raise ValueError("Only replacement options are league and teamname")
    name_substitutes = json.load(
        open(f"/home/morten/soccerdata/config/{what}_replacements.json")
    )
    for replacement in name_substitutes:
        for to_replace in name_substitutes[replacement]:
            if initial_name == to_replace:
                return replacement
    return None