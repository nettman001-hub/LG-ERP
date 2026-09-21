from price_compare import fetch_danawa_lowest_price

models_to_test = [
    "W20WHN",
    "AI958WB",
    "이건없는스펙의상품명ASDF",
]

for model in models_to_test:
    print(f"\nTesting: {model}")
    price, kw, url = fetch_danawa_lowest_price(model)
    print(f"Price: {price}")
    print(f"Keyword used: {kw}")
    print(f"URL: {url}")
