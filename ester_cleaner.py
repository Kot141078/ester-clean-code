import re

def clean_ester_response(text: str) -> str:
    """
    Funktsiya glubokoy ochistki otvetov Ester.
    Udalyaet utechki konteksta, sistemnye zagolovki i tekhnicheskie podpisi.
    """
    if not text:
        return ""

    # 1. Udalyaem blok [SYSTEM REALTIME] i vse, chto vnutri nego do kontsa stroki ili bloka
    text = re.sub(r'\[SYSTEM REALTIME\].*?(\n|$)', '', text, flags=re.IGNORECASE)
    
    # 2. Udalyaem stroki s datoy i vremenem, esli oni dubliruyut sistemnyy prompt
    # Primer: Data: 13.12.2025...
    text = re.sub(r'Data:\s*\d{2}\.\d{2}\.\d{4}.*?(\n|$)', '', text, flags=re.IGNORECASE)

    # 3. Udalyaem "Ekho" nachala otveta, esli model tupo povtoryaet vvodnye
    # (Udalyaet stroki vida "Tekuschee vremya: **...**", esli oni v nachale teksta)
    text = re.sub(r'^Tekuschee vremya:\s*\*\*.*?\*\*.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^Fizicheskoe mestopolozhenie yadra:.*?\n', '', text, flags=re.MULTILINE)

    # 4. Udalyaem tekhnicheskuyu podpis LM Studio (v skobkakh v kontse)
    # Primer: (🧠 lokalnaya LM Studio (fast/ctx-budget))
    text = re.sub(r'\(\s*🧠.*?\)', '', text)

    # 5. Udalyaem dvoynye perevody strok, voznikshie posle vyrezaniya
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Finalnaya zachistka probelov
    return text.strip()
