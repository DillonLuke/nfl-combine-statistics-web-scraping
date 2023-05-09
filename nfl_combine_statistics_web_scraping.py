import numpy as np
import pandas as pd

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

PLAYER_STAT_TABLES = ["passing", "rushing", "receiving", "defense"]

def get_soup(url: str):
    """
    Convert a url into a bs4.BeautifulSoup object.
    
    Parameters
    ----------
    url : str
        String of url for conversion.
    
    Returns
    -------
    soup : bs4.BeautifulSoup
        Object for use with BeautifulSoup library.

    """
    service = EdgeService(EdgeChromiumDriverManager().install())
    
    driver = webdriver.Edge(service=service)
    
    driver.implicitly_wait(1) 
    
    driver.get(url)
        
    soup = BeautifulSoup(driver.page_source, "html.parser")

    driver.quit()
    
    return soup


def get_soups(urls):
    """
    Convert an array of urls into an array of bs4.BeautifulSoup objects.
    
    Parameters
    ----------
    urls : array-like
        Array of strings of urls for conversion.
    
    Returns
    -------
    soups : list
        List of bs4.BeautifulSoup objects for use with BeautifulSoup library.

    """
    service = EdgeService(EdgeChromiumDriverManager().install())
    
    driver = webdriver.Edge(service=service)
    
    driver.implicitly_wait(1) 
    
    soups = []
    for url in urls:
        driver.get(url)
        
        soups.append(BeautifulSoup(driver.page_source, "html.parser"))

    driver.quit()
    
    return soups


def get_pfr_table_data(rows, data_extraction_function=lambda x: x.text):
    """
    Get data from a Pro-Football-Reference statistics table.
    
    Gets data from entries (must have a 'data-stat' attribute) in the rows of 
    a Pro-Football-Reference table according to some specified data 
    extraction function. If no extraction function is specified, then
    the text of each entry in the data table will be extracted.
    
    Parameters
    ----------
    rows : array-like
        Array of rows, which should be of type bs4.element.tag. Each row
        should contain 'th' or 'td' tags which represent row entries. Each
        row entry should have a 'data-stat' attribute.
    data_extraction_function : func, optional
        Function that takes as input a 'th' or 'td' bs4.element.tag and
        returns some piece of information extracted from the tag. By default,
        the text of the tag will be extracted.
    
    Returns
    -------
    row_data : list[dict]
        List of dictionaries, with each dictionary representing the data from
        a row. The keys of each dictionary are 'data-stat' names that characterize
        the entries in the given row and the items of each dictionary are data
        extracted from the row according to the data extraction function.

    """
    row_data = []
    for row in rows:
        row_data.append({})
        
        for entry in row.find_all(["th", "td"]):
            row_data[-1][entry["data-stat"]] = data_extraction_function(entry)
    
    return row_data


def get_pfr_combine_stat(entry):
    if entry["data-stat"] != "college":
        val = entry.text.strip()
    elif entry.a is not None:
        val = entry.a["href"]
    else:
        val = ""
    
    return val


def get_pfr_combine_stats(soup):
    """
    Get data from a Pro-Football-Reference combine results table.
    
    Relies on a bs4.BeautifulSoup object which contains the HTML of a
    Pro-Football-Reference NFL combine results page, the url for which 
    has the pattern: 
    
    https://aws.pro-football-reference.com/draft/year-combine.htm.
    
    Note: The year is replaced by a specific year of the format YYYY.
    
    Extracts all data from the combine results table as is displayed with
    one exception. One column in the combine results table, 'college', is
    a hyperlink to a given player's college statistics. Rather than include
    the hyperlink text, the actual link is extracted instead. 
    
    Parameters
    ----------
    soup : bs4.BeautifulSoup
        Object containing HTML information which is used to locate
        relevant data.
    
    Returns
    -------
    df : pd.DataFrame
        Dataframe that contains the data extracted from the combine
        results table.

    """
    table = soup.find("table", id="combine")

    rows = table.tbody.find_all("tr", class_=lambda c: c != "thead")

    df = (pd.DataFrame(get_pfr_table_data(rows, get_pfr_combine_stat))
          .mask(lambda x: x == "")
          .apply(lambda x: pd.to_numeric(x, errors="ignore")))

    return df


def get_pfr_combines_stats(year_ids, soups):                                                                                
    """
    Get data from Pro-Football-Reference combine results tables across years.
    
    Relies on an array of bs4.BeautifulSoup objects which contain 
    the HTML of a Pro-Football-Reference NFL combine results page for
    different years, the urls of which have the pattern: 
    
    https://aws.pro-football-reference.com/draft/year-combine.htm.
    
    Note: The year is replaced by a specific year of the format YYYY.
    
    Extracts all data from the combine results table in each year as is
    displayed with one exception. One column in the combine results table,
    'college', is a hyperlink to a given player's college statistics. 
    Rather than include the hyperlink text, the actual link is extracted 
    instead. 
    
    Parameters
    ----------
    year_ids : array-like
        Array of years for which combine results data is extracted.
        This array is used for the index of the final dataframe to
        distinguish between results of different years.
    soups : array-like
        Array of bs4.BeautifulSoup objects containing HTML information
        which is used to locate relevant data.
    
    Returns
    -------
    df : pd.DataFrame
        Dataframe that contains the data extracted from the combine
        results table across years with year_ids and player_id used
        as the index. The former is captured by the year_ids parameter 
        and the latter is a sequential number range from 0 to n-1.

    """
    combine_data = []
    
    for soup in soups:
        combine_data.append(get_pfr_combine_stats(soup))
    
    df = (pd.concat(combine_data, keys=year_ids, names=["combine_year", "_"])
          .reset_index(level=1, drop=True)
          .assign(player_id=lambda x: np.arange(len(x)))
          .set_index("player_id", append=True))
    
    return df


def get_pfr_player_stats(soup):
    """
    Get data from Pro-Football-Reference college statistics tables for a player.
    
    Relies on a bs4.BeautifulSoup object which contains the HTML of a
    Pro-Football-Reference college statistics page for a given player,
    the url for which has the pattern: 
    
    https://www.sports-reference.com/cfb/players/fname-lname-num.html
    
    Note: fname and lname is replaced by the given player's first name and
    last name, respectively. 'num' is usually 1, but is incremented if the 
    name has already been taken.
    
    Extracts all data from the college statistics tables for the
    given player. These tables contain (1) passing statistics, (2) rushing/
    receiving statistics, and (3) defense statistics. Each player may not
    have data in all 3 categories, in which case only available data is scraped.
    
    Parameters
    ----------
    soup : bs4.BeautifulSoup
        Object containing HTML information which is used to locate
        relevant data.
    
    Returns
    -------
    df : pd.DataFrame
        Dataframe that contains the data extracted from the college 
        statistics tables for the given player.

    """
    tables = soup.find_all("table", id=lambda i: i in PLAYER_STAT_TABLES)
    
    if len(tables) == 0:
        return pd.DataFrame()

    table_data =[pd.DataFrame()]
    for table in tables:
        rows = table.tbody.find_all("tr")

        table_data.append(pd.DataFrame(get_pfr_table_data(rows)))
    
    df = (pd.concat(table_data, axis=1)
          .loc[:, lambda x: ~x.columns.duplicated()]
          .mask(lambda x: x == "")
          .apply(lambda x: pd.to_numeric(x, errors="ignore")))

    return df 


def get_pfr_players_stats(player_ids, soups):
    """
    Get data from Pro-Football-Reference college statistics tables for players.
    
    Relies on an array of bs4.BeautifulSoup objects which contain 
    the HTML of a Pro-Football-Reference college statistics page for a
    given player, the url for which has the pattern: 
    
    https://www.sports-reference.com/cfb/players/fname-lname-num.html
    
    Note: fname and lname is replaced by the given player's first name and
    last name, respectively. 'num' is usually 1, but is incremented if the 
    name has already been taken.
    
    Extracts all data from the college statistics tables for a set 
    of players. These tables contain (1) passing statistics, (2) rushing/
    receiving statistics, and (3) defense statistics. Each player may not
    have data in all 3 categories, in which case only available data is
    scraped.
    
    Parameters
    ----------
    player_ids : array-like
        Array of player_ids for which college statistics data
        is extracted. This array is used for the index of the final
        dataframe to distinguish between results of different players.
    soups : array-like
        Array of bs4.BeautifulSoup objects containing HTML information
        which is used to locate relevant data.
    
    Returns
    -------
    df : pd.DataFrame
        Dataframe that contains the data extracted from the college statistics
        tables for a set of players with the player_id and year used as index.
        The former is captured by the player_ids parameter and the latter is
        taken from the 'year_id' statistic from the college statistics tables.

    """
    player_data = []
    
    for soup in soups:
        player_data.append(get_pfr_player_stats(soup))
    
    df = (pd.concat(player_data, keys=player_ids, names=["player_id", "_"])
          .reset_index(level=1, drop=True)
          .set_index("year_id", append=True))
    
    return df

