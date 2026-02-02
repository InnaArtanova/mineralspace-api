# wikidata_service.py
import requests
from typing import Optional, Dict, Any

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

def fetch_mineral_from_wikidata(wikidata_id: str) -> Optional[Dict[str, Any]]:
    """
    Загружает данные о минерале из Wikidata по ID вида 'Q123456'
    """
    params = {
        "action": "wbgetentities",
        "ids": wikidata_id,
        "format": "json",
        "languages": "en|ru",
        "props": "labels|claims"
    }
    
    try:
        response = requests.get(WIKIDATA_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        entity = data["entities"].get(wikidata_id)
        if not entity or entity.get("missing"):
            return None
            
        return entity
    except Exception as e:
        print(f"Ошибка при загрузке из Wikidata: {e}")
        return None

def extract_mineral_data(entity: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает нужные поля из ответа Wikidata
    """
    labels = entity.get("labels", {})
    name_en = labels.get("en", {}).get("value", "")
    name_ru = labels.get("ru", {}).get("value", name_en)

    claims = entity.get("claims", {})
    
    # Химическая формула (P274)
    chemical_formula = ""
    if "P274" in claims:
        formula_claim = claims["P274"][0]
        chemical_formula = formula_claim.get("mainsnak", {}).get("datavalue", {}).get("value", "")

    # Система кристаллов (P2055)
    crystal_system_id = ""
    if "P2055" in claims:
        crystal_claim = claims["P2055"][0]
        crystal_system_id = f"wikidata:{crystal_claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id', '')}"

    # Твёрдость по Моосу (P189)
    hardness_id = ""
    if "P189" in claims:
        hardness_claim = claims["P189"][0]
        hardness_id = f"wikidata:{hardness_claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id', '')}"

    # Спайность (P2056)
    cleavage_id = ""
    if "P2056" in claims:
        cleavage_claim = claims["P2056"][0]
        cleavage_id = f"wikidata:{cleavage_claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id', '')}"

    # Тип минерала — можно определить по классификации (например, P2057), но для начала оставим пустым
    mineral_type_id = ""

    return {
        "name_ru": name_ru,
        "name_en": name_en,
        "chemical_formula": chemical_formula,
        "mineral_type_id": mineral_type_id,
        "hardness_id": hardness_id,
        "cleavage_id": cleavage_id,
        "crystal_system_id": crystal_system_id,
        "crystal_form_id": "",  # Wikidata не хранит форму напрямую
        "source": "wikidata"
    }