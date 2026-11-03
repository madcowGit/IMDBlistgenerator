import re
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

app = FastAPI(title="IMDb Steven Lu Format API")

def init_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--window-size=1920,1080")
    
    # Initialize headlessly inside Xvfb
    return uc.Chrome(options=options, version_main=None)

def parse_imdb_list(html_content: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_content, "html.parser")
    items = soup.select("li.ipc-metadata-list-summary-item")
    
    results = []
    
    for item in items:
        # 1. Title & IMDb ID
        title_el = item.select_one("a.ipc-title-link-wrapper")
        if not title_el:
            continue
        
        href = title_el.get("href", "")
        imdb_id_match = re.search(r"tt\d+", href)
        imdb_id = imdb_id_match.group(0) if imdb_id_match else None
        
        # Clean up title text (strips ranking numbers like "1. ")
        raw_title = title_el.get_text(strip=True)
        title = re.sub(r"^\d+\.\s*", "", raw_title)
        
        # 2. Release Year
        year_el = item.select_one(".cli-title-metadata-item, .sc-d5ea4b9d-7")
        year = None
        if year_el:
            year_match = re.search(r"\b(19|20)\d{2}\b", year_el.get_text())
            if year_match:
                year = year_match.group(0)

        # 3. Poster URL
        img_el = item.select_one("img.ipc-image")
        poster_url = img_el.get("src") if img_el else None
        
        # Steven Lu format JSON structure
        results.append({
            "title": title,
            "imdb_id": imdb_id,
            "poster_url": poster_url,
            "year": year
        })
        
    return results

@app.get("/api/scrape")
def scrape_list(url: str = Query(..., description="Full IMDb list or chart URL")):
    if "imdb.com" not in url:
        raise HTTPException(status_code=400, detail="URL must be a valid IMDb link")
        
    driver = None
    try:
        driver = init_driver()
        driver.get(url)
        
        # Give page time to load dynamic JavaScript contents
        time.sleep(5)
        
        # Scroll down to trigger lazy-loaded items/images
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        data = parse_imdb_list(driver.page_source)
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if driver:
            driver.quit()