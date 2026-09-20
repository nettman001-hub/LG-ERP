
import os
import re

with open('erp_client_fixed.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the most common broken patterns
# We must use raw strings or escape backslashes if needed, but here simple strings are fine
replacements = {
    'D01 \ufffd\udc9c\ud0dc\ufffd\ufffd day code\ufffd\udcb5 D+01 \ufffd\udc9c\ud0dc\ufffd\ufffd \ubcc0\ufffd\udcb1\ud569\ufffd\udcb4\ub2e4.': 'D01 \ud615\ud0dc\uc758 day code\ub97c D+01 \ud615\ud0dc\ub85c \ubcc0\ud658\ud569\ub2c8\ub2e4.',
    '\ufffd\ud0b0\uacc4\ud68d': '\uc0dd\uc0b0\uacc4\ud68d',
    '\ufffd\ud0b1\ufffd\udcb1\uc18d\ufffd\ufffd\ufffd\ufffd\ud0b0\uacc4\ud68d': '\ub0a9\uae30\uc57d\uc18d\ub41c \uc0dd\uc0b0\uacc4\ud68d',
    '\ufffd\ud0b1\ufffd\udcb1\uc18d \uac00\ufffd\ufffd\ufffd\ufffd\ud0b0\uacc4\ud68d': '\ub0a9\uae30\uc57d\uc18d \uac00\ub2a5 \uc0dd\uc0b0\uacc4\ud68d',
    'Nexacro SSV \ufffd\udcb5\ud0b5 \ufffd\udcb7\udeb7\ufffd\ufffd\ufffd\ufffd\ud0b1\ufffd\ub294 \ufffd\udcb1\ub798\ufffd\ufffd': 'Nexacro SSV \uc751\ub2f5 \ud3ec\ub9b7\uc744 \ud30c\uc2f1\ud558\ub294 \ud074\ub798\uc2a4',
}

# Actually, since I can't easily guess the exact \ufffd sequences, 
# let's look at the file content in erp_client_fixed.py again and see the literal '?' characters.
# The tool view_file showed literal '?' characters.

text = text.replace('D01 ?\udc9c\ud0dc?? day code\udcb5 D+01 ?\udc9c\ud0dc?? \ubcc0?\udcb1\ud569?\udcb4\ub2e4.', 'D01 \ud615\ud0dc\uc758 day code\ub97c D+01 \ud615\ud0dc\ub85c \ubcc0\ud658\ud569\ub2c8\ub2e4.')
text = text.replace('?\ud0b0\uacc4\ud68d', '\uc0dd\uc0b0\uacc4\ud68d')
text = text.replace('?\ud0b1?\uc18d???\ud0b0\uacc4\ud68d', '\ub0a9\uae30\uc57d\uc18d\ub41c \uc0dd\uc0b0\uacc4\ud68d')
text = text.replace('?\ud0b1?\uc18d \uac00???\ud0b0\uacc4\ud68d', '\ub0a9\uae30\uc57d\uc18d \uac00\ub2a5 \uc0dd\uc0b0\uacc4\ud68d')
text = text.replace('Nexacro SSV ?\udcb5\ud0b5 ?\udcb7\udeb7???\ud0b1\ub294 ?\udcb1\ub798??', 'Nexacro SSV \uc751\ub2f5 \ud3ec\ub9b7\uc744 \ud30c\uc2f1\ud558\ub294 \ud074\ub798\uc2a4')
text = text.replace('RS = \'\x1e\'  # Record Separator (ASCII 30) - ??\uad6c\ubd84??', 'RS = \'\x1e\'  # Record Separator (ASCII 30) - \ud51c \uad6c\ubd84\uc790')
text = text.replace('US = \'\x1f\'  # Unit Separator (ASCII 31) - ??\uad6c\ubd84??', 'US = \'\x1f\'  # Unit Separator (ASCII 31) - \uc5f4 \uad6c\ubd84\uc790')
text = text.replace('SSV ?\ud0b5 \ubcc0?? ErrorCode/ErrorMsg ??\udcb5?\ud0b1\uc5ec {?? \udcb5 ?\udc9c\ud0dc\ub85c \ubc18\ud658', 'SSV \uc0c1\ub2e8 \ubcc0\uc218 (ErrorCode/ErrorMsg \ub4f1)\uc744 \ud30c\uc2f1\ud558\uc5ec {\ud0a4: \uac12} \ud615\ud0dc\ub85c \ubc18\ud658')
text = text.replace('SSV ?\udcb9\ud0b5?? ?\ud0b1\uc5ec {?\ud0b4?\udcb7\ud0b5? [\udcb5?\ud0b4?\udcb7\ud0b5?\udcb7\ud0b4\ub9ac, ...]} ?\udc9c\ud0dc\ub85c \ubc18\ud658', 'SSV \uc751\ub2f5\uc744 \ud30c\uc2f1\ud558\uc5ec {\ub370\uc774\ud130\uc14b\uba85: [\ub370\uc774\ud130\ud589 \ub9ac\uc2a4\ud2b8, ...]} \ud615\ud0dc\ub85c \ubc18\ud658')
text = text.replace('?\ud0b4?\udcb7\ud0b5 \ube14\ub85d \ubd84\ub9ac (Dataset: ?\ub85c ?\ud0b1?\ub294 \ubd80\ubd84\ub4e4)', '\ub370\uc774\ud130\uc14b \ube14\ub85d \ubd84\ub9ac (Dataset: \uc73c\ub85c \uc2dc\uc791\ud558\ub294 \ubd80\ubd84\ub4e4)')
text = text.replace('parts[1:]: # ?\ubc88\uc9f8 \ubd80\ubd84\udcb5 SSV ?\udcb5\ud0b1\udcb5?\udcb4\udcb5\ub7b5', 'parts[1:]: # \uccab \ubc88\uc9f8 \ubd80\ubd84\uc740 SSV \ud5e4\ub354\uc774\ubbc0\ub85c \uc0dd\ub7b5')

# Re-applying the known clean code sections is safer
clean_sections = [
    (\"\"\"def _format_day_code(day_code: str) -> str:
    \\\"\\\"\\\"D01 형태의 day code를 D+01 형태로 변환합니다.\\\"\\\"\\\"
    m = re.match(r'^([A-Za-z]+)(\\d+)$', day_code)
    if m:
        return f\\\"{m.group(1)}+{m.group(2)}\\\"
    return day_code\"\"\", re.compile(r'def _format_day_code.*?return day_code', re.S)),

    (\"\"\"def format_production_plan_details(plan: ProductionPlanResult) -> list[str]:
    lines: list[str] = []
    for day in plan.days:
        code = _format_day_code(day.day_code)
        lines.append(
            f\\\"{code}: 생산계획 {day.plan_qty} / \\\"
            f\\\"납기약속된 생산계획 {day.promised_qty} / \\\"
            f\\\"납기약속 가능 생산계획 {day.available_qty}\\\"
        )
    return lines\"\"\", re.compile(r'def format_production_plan_details.*?return lines', re.S)),
]

for replacement, pattern in clean_sections:
    text = pattern.sub(replacement, text)

# Just fix all '?' remaining to some readable text if they are in strings
# Or better, just fix the specific ones we know.

with open('erp_client.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Done')
