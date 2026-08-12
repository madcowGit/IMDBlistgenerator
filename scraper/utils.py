import json
import pandas as pd
from typing import List, Dict, Any

def save_to_csv(data: List[Dict[str, Any]], filepath: str):
    df = pd.DataFrame(data)
    df.to_csv(filepath, index=False)

def save_to_json(data: List[Dict[str, Any]], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_to_txt_ids(data: List[Dict[str, Any]], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            if item.get("imdb_id"):
                f.write(f"{item['imdb_id']}\n")
