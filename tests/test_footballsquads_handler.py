import pytest
import sys
from collections import defaultdict
from database_io.db_handler import DB_handler

from scraper.footballsquads_scraper import Footballsquads_scraper

# setup test environment, setting up a database handler
dbh = DB_handler()

def test_extract_numbers_from_html_table():
    fh = Footballsquads_scraper("./../.cache_footballsquads", dbh)
    table_dict = fh.extract_numbers_from_html_table(open("./data_for_tests/FootballSquads-BorussiaMoenchengladbach-2020_2021.html").read())
    assert type(table_dict) is defaultdict
    assert len(table_dict.keys()) == 34
    assert table_dict["11"][0] == "Hannes Wolf"

def test_validate_row_data():
    fh = Footballsquads_scraper("./../.cache_footballsquads", dbh)
    assert fh.validate_row_data([]) == False
    assert fh.validate_row_data(None) == False
    assert fh.validate_row_data(["1", "Maier"]) == True

def test_scrape_kit_number_table():
    fh = Footballsquads_scraper("./../.cache_footballsquads", dbh)
    url_list = ["./arsenal.htm", "./../index.html", "./../werder.html", "squads.htm/werder_again"]
    assert len(fh.remove_unwanted_urls(url_list)) == 2
    assert fh.remove_unwanted_urls(url_list) == ["./arsenal.htm", "./../werder.html"]

def test_integration():
    fh = Footballsquads_scraper("./../.cache_footballsquads", dbh)
    table_html = fh.scrape_kit_number_table("http://www.footballsquads.co.uk/ger/2020-2021/bundes/monchen.htm")
    table_dict = fh.extract_numbers_from_html_table(table_html)
    assert type(table_dict) is defaultdict
    assert len(table_dict.keys()) == 34
    assert table_dict["11"][0] == "Hannes Wolf"