import requests
from urllib.parse import quote_plus
import sys

def get_danawa_html(model):
    search_keyword = model.strip()
    query = quote_plus(search_keyword)
    url = f"https://search.danawa.com/dsearch.php?query={query}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.danawa.com/"
    }

    resp = requests.get(url, headers=headers, timeout=10.0)
    print(f"Status Code: {resp.status_code}")
    
    with open("danawa_test.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"Saved HTML to danawa_test.html")

if __name__ == "__main__":
    test_model = sys.argv[1] if len(sys.argv) > 1 else "삼성 전자레인지"
    print(f"Testing model: {test_model}")
    get_danawa_html(test_model)
