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


class Footballsquads_handler:
    def __init__(self, cache_location) -> None:
        self.SKIP_LINKS = [
            "index.html",
            "forums",
            "search.htm",
            "contact.htm",
            "pripol.htm",
            "tou.htm",
            "squads.htm",
            "national.htm",
            "mailto:info@footballsquads.com",
            "../../pripol.htm",
            "../../tou.htm",
        ]
        # URL to scrape
        self.url_archive = "http://www.footballsquads.co.uk/archive.htm"
        self.cache_location = cache_location
    # How to test?
    def fetch_all_links_on_page(self, url: str) -> list[str]:
        link_list = []
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.find_all("a")
        for link in links:
            href = link.get("href")
            if href:
                if href in self.SKIP_LINKS:
                    continue
                link_list.append(href)
        return link_list
    # How to test?
    def scrape_kit_number_table(self, url: str) -> bytes:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        else:
            print("Failed to fetch the page. Status code:", response.status_code)
            raise ValueError(f"Failed scraping {url}")

    def extract_numbers_from_html_table(self, html_table: str) -> defaultdict[int:list]:
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

    def scrape_archive(self):
        # get top level leagues/seasons
        season_links = self.get_links(self.url_archive)

        # get clubs
        for league_season in season_links:
            teams = self.get_links(f"http://www.footballsquads.co.uk/{league_season}")
            teams = teams[7:]
            for team in teams:
                league_season_url_split = league_season.split("/")
                scrape_url = f"http://www.footballsquads.co.uk/{league_season_url_split[0]}/{league_season_url_split[1]}/{team}"
                team_name = team.split("/")[1].split(".")[0]
                file_path = f"{league_season_url_split[0]}-{league_season_url_split[1]}-{league_season_url_split[2].split('.')[0]}-{team_name}.pckl"
                if file_path not in os.listdir(self.cache_location):
                    print("Scraping ", scrape_url)
                else:
                    print("Data found in cache, skip")
                    continue
                data = self.get_table(scrape_url)
                if not data:
                    print("None Data found!")
                    continue
                with open(self.cache_location + file_path, "wb") as handle:
                    pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
                sleep(1)

    def get_infos_from_filename(self, file_name):
        file_name_split = file_name.split("-")
        team_name = file_name_split[4].split(".")[0]
        league = file_name_split[3]
        season = file_name_split[1] + "/" + file_name_split[2]
        replaced_team_name = False
        replaced_league = False
        name_substitutes = json.load(
            open("/home/morten/soccerdata/config/teamname_replacements.json")
        )
        for replace in name_substitutes:
            for name in name_substitutes[replace]:
                if team_name == name:
                    team_name = replace
                    replaced_team_name = True
        name_substitutes = json.load(
            open("/home/morten/soccerdata/config/league_replacements.json")
        )
        for replace in name_substitutes:
            for name in name_substitutes[replace]:
                if league == name:
                    league = replace
                    replaced_league = True
        if replaced_team_name and not replaced_league:
            print(f"WARNING missing name replacement for team {team_name}")
        if replaced_team_name and replaced_league:
            return True, team_name, league, season
        return False, None, None, None

    def cache_to_db(self, db_path, leagues):
        # create db connection
        db_connection = sqlite3.connect(db_path)
        # get all files already written to db:
        sql = """ SELECT processed from processed_footballsquads """
        cur = db_connection.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        already_processed_files = [i[0] for i in rows]
        # get all files in cache:
        cache_file_list = os.listdir(self.cache_location)
        cache_file_list_removed = [
            i for i in cache_file_list if i not in already_processed_files
        ]
        # get infos like team, league and season.
        for cache_file in cache_file_list_removed:
            success, team_name, league, season = self.get_infos_from_filename(
                cache_file
            )
            if league not in leagues:
                continue
            file = open(self.cache_location + cache_file, "rb")
            table_object = pickle.load(file)
            file.close()
            index = 0
            for idx, row in enumerate(table_object):
                if "Note:" in row[0]:
                    index = idx
                    only_active_players = table_object[:index]
                    break
                if "Players no longer at this club" in row[0]:
                    index = idx
                    only_active_players = table_object[:index]
                    break
            # if ['Players no longer at this club'] in table_object:
            #     index = table_object.index(['Players no longer at this club'])
            #     only_active_players = table_object[:index]
            if index == 0:
                only_active_players = table_object
            complete_player_df = pd.DataFrame(
                columns=[
                    "Number",
                    "Name",
                    "Nat",
                    "Pos",
                    "Height",
                    "Weight",
                    "Date of Birth",
                    "Birth Place",
                    "Previous Club",
                ]
            )
            active_player_df = pd.DataFrame(
                only_active_players[1:], columns=only_active_players[0]
            )
            for col in active_player_df.columns:
                complete_player_df[col] = active_player_df[col]
            complete_player_df = complete_player_df[complete_player_df.Name != ""]
            complete_player_df["Number"] = (
                complete_player_df["Number"]
                .replace("", -1)
                .replace(np.nan, -1)
                .astype(int)
            )
            complete_player_df["Height"] = complete_player_df["Height"].replace("-", "")
            complete_player_df["Weight"] = complete_player_df["Weight"].replace("-", "")
            if success:
                complete_player_df.apply(
                    lambda x: self.player_to_sql(
                        x, team_name, league, season, db_connection
                    ),
                    axis=1,
                )
                # write file update to processed files.
                self.update_processed_table([cache_file], db_connection)
