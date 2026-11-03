import json
import os
from typing import Any, Dict, List

import pandas as pd


def _ensure_parent_dir(filepath: str):
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)


def save_to_csv(data: List[Dict[str, Any]], filepath: str):
    _ensure_parent_dir(filepath)
    columns = ["position", "imdb_id", "title", "year", "rating", "imdb_url"]
    pd.DataFrame(data, columns=columns).to_csv(filepath, index=False)


def save_to_json(data: List[Dict[str, Any]], filepath: str):
    _ensure_parent_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as output:
        json.dump(data, output, indent=4, ensure_ascii=False)


def save_to_txt_ids(data: List[Dict[str, Any]], filepath: str):
    _ensure_parent_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as output:
        for item in data:
            imdb_id = item.get("imdb_id")
            if imdb_id:
                output.write(f"{imdb_id}\n")
