from price_compare import refine_search_keyword

test_cases = [
    # 1. '**' rule
    ("ABC동**DEF", "ABC DEF"),
    # 2. '*' rule
    ("ABC동*DEF", "ABC DEF"),
    # 1 & 2 priority
    ("ABC동**DEF가*HIJ", "ABC DEF HIJ"),
    
    # 3. OLED + S/W -> NA
    ("OLED65C3S/W", "OLED65C3NA"),
    ("oled55b3s/w", "oled55b3NA"), # case insensitive check
    
    # 4. QNED + S/W, 1/2, W or S -> A
    ("100QNED80S/W", "100QNED80A"),
    ("100QNED801/2", "100QNED80A"),
    ("75QNED80W", "75QNED80A"),
    ("75QNED80S", "75QNED80A"),
    ("86qned91w", "86qned91A"),
    
    # 5. No OLED + S/W -> A
    ("75UR8000S/W", "75UR8000A"),
    
    # 6. G/W -> GNA
    ("ABCDEFG/W", "ABCDEFGNA"),
    
    # 0. Dot Rule (Grand Premise)
    ("27ART10AKPL.AKRS/W", "27ART10AKPL"),
    ("OLED65C3.AUB", "OLED65C3"),
    
    # Edge cases
    ("JUSTNORMAL", "JUSTNORMAL"),
    ("   SPACES   ", "SPACES")
]

print("--- Testing Danawa Keyword Refinement ---")
all_passed = True
for original, expected in test_cases:
    result = refine_search_keyword(original)
    status = "OK" if result == expected else "FAIL"
    if status == "FAIL":
        all_passed = False
    print(f"[{status}] Original: '{original}'")
    print(f"      -> Expected: '{expected}'")
    print(f"      -> Got:      '{result}'\n")

if all_passed:
    print("ALL TESTS PASSED!")
else:
    print("SOME TESTS FAILED.")
