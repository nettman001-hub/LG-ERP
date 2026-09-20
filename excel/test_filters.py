import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
import sys

# Ensure stdout uses utf-8
sys.stdout.reconfigure(encoding='utf-8')

def parse_danawa(model):
    url = f"https://search.danawa.com/dsearch.php?query={quote_plus(model)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    items = soup.select('li.prod_item')
    
    for item in items:
        name_elem = item.select_one('.prod_name a')
        if not name_elem:
            continue
        name = name_elem.text.strip()
        
        if model.lower() not in name.lower():
            continue
            
        has_rating = False
        star = item.find(string=lambda t: t and '별점' in t)
        if star:
            has_rating = True
            
        mall_count = 0
        mall_texts = []
        # Look for any text containing '몰' and ends with '몰'
        for t in item.find_all(string=True):
            s = t.strip()
            if s.endswith('몰'):
                m = re.search(r'(\d+)몰', s)
                if m:
                    mall_count = max(mall_count, int(m.group(1)))
                    mall_texts.append(s)
                    
        if has_rating and mall_count >= 30:
            print(f"\n--- PERFECT MATCH ---")
            print(f"Name: {name}")
            print(f"Mall Count: {mall_count}")
            prices = []
            # Find closest prices
            # In Danawa, the lowest price in the right side block.
            # Usually .price_sect
            price_elems = item.select('.price_sect strong')
            # Also check if there are list items with prices
            price_list = item.select('.item_info li .price_sect')
            if price_list:
                for pe in item.select('.item_info li .price_sect strong'):
                    try:
                        prices.append(int(pe.text.replace(',', '')))
                    except: pass
            else:
                for pe in price_elems:
                    try:
                        prices.append(int(pe.text.replace(',', '')))
                    except: pass
                    
            print(f"Prices found: {prices}")
            if prices:
                print(f"Lowest Price: {min(prices)}")

if __name__ == "__main__":
    parse_danawa("W20WHN")
