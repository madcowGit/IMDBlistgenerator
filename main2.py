import json
import re
from seleniumbase import SB

IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"


def parse_movie_element(driver, element):
    """
    Parses an IMDb item element and returns a dict formatted in Steven Lu's JSON layout.
    Expected output keys: title, imdb_id, poster_url, year, rating
    """
    movie_data = {
        "title": None,
        "imdb_id": None,
        "poster_url": None,
        "year": None,
        "rating": None,
    }

    try:
        # Extract IMDb ID and Title
        title_el = element.find_element("css selector", "a.ipc-title-link-wrapper")
        href = title_el.get_attribute("href") or ""
        match = re.search(r"tt\d+", href)
        if match:
            movie_data["imdb_id"] = match.group(0)

        # Remove position number prefix (e.g. "1. ") from the title text
        raw_title = title_el.text.strip()
        movie_data["title"] = re.sub(r"^\d+\.\s*", "", raw_title)

        # Extract Poster Image URL
        try:
            img_el = element.find_element("css selector", "img.ipc-image")
            movie_data["poster_url"] = img_el.get_attribute("src")
        except Exception:
            pass

        # Extract Release Year
        try:
            metadata_spans = element.find_elements("css selector", "span.dli-title-metadata-item")
            for span in metadata_spans:
                text = span.text.strip()
                if re.match(r"^\d{4}$", text):
                    movie_data["year"] = int(text)
                    break
        except Exception:
            pass

        # Extract IMDb Rating
        try:
            rating_el = element.find_element("css selector", "span.ipc-rating-star--rating")
            movie_data["rating"] = float(rating_el.text.strip())
        except Exception:
            pass

    except Exception as e:
        print(f"Error parsing item: {e}")

    return movie_data


def scrape_imdb_list():
    movies = []

    # Initialize SeleniumBase in UC (Undetected Chromedriver) mode
    with SB(uc=True, headless=False) as sb:
        print(f"Opening {IMDB_LIST_URL} in UC mode...")
        sb.uc_open_with_reconnect(IMDB_LIST_URL, reconnect_time=4)
        
        # Handle potential anti-bot Turnstile / JavaScript challenges automatically
        sb.uc_gui_click_captcha_if_present()

        # Wait until list items are present
        sb.wait_for_element_present("li.ipc-metadata-list-summary-item", timeout=15)

        # Smooth scroll to ensure all lazy-loaded images render
        sb.scroll_to_bottom()
        sb.sleep(2)

        # Locate all movie elements
        items = sb.find_elements("li.ipc-metadata-list-summary-item")
        print(f"Found {len(items)} items in the IMDb list.")

        for item in items:
            movie_info = parse_movie_element(sb.driver, item)
            if movie_info["imdb_id"] and movie_info["title"]:
                movies.append(movie_info)

    return movies


if __name__ == "__main__":
    scraped_data = scrape_imdb_list()

    # Output formatted JSON (Steven Lu format)
    json_output = json.dumps(scraped_data, indent=2)
    
    print("\n--- Scraped Steven Lu JSON Output ---\n")
    print(json_output)

    # Save to file
    with open("stevenlu_movies.json", "w", encoding="utf-8") as f:
        f.write(json_output)
    
    print(f"\nSuccessfully saved {len(scraped_data)} movies to 'stevenlu_movies.json'")
