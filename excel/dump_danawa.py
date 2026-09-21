import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

def dump_html(model):
    query = quote_plus(model)
    url = f"https://search.danawa.com/dsearch.php?query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    resp = requests.get(url, headers=headers)
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    products = soup.select('li.prod_item')
    
    with open('danawa_debug.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total products found: {len(products)}\n\n")
        for i, p in enumerate(products):
            f.write(f"--- Product {i} ---\n")
            # Remove scripts and styles for cleaner output
            for s in p(['script', 'style']):
                s.extract()
            # Just write the text representation and some key HTML parts
            name_a = p.select_one('.prod_name a')
            name = name_a.text.strip() if name_a else "NO NAME"
            f.write(f"Name: {name}\n")
            
            # Print text of the whole item to see what we have
            text_lines = [line.strip() for line in p.text.split('\n') if line.strip()]
            f.write("Text Content:\n" + "\n".join(text_lines) + "\n\n")
            
            # Write raw HTML of price section
            price_sect = p.select_one('.price_sect')
            if price_sect:
                f.write("Price Section HTML:\n" + str(price_sect) + "\n\n")

if __name__ == "__main__":
    dump_html("W20WHN")
