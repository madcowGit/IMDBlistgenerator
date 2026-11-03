from imdb_scraper import scrape_imdb_list

IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"
IMDB_WATCHLIST_URL = (
    "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
)
IMDB_URL = IMDB_WATCHLIST_URL


if __name__ == "__main__":
    json_output = scrape_imdb_list(IMDB_URL)

    print(json_output)
