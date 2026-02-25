import re

def clean_ester_response(text: str) -> str:
    """Deep cleaning function for Esther's answers.
    Removes context leaks, system headers and technical signatures."""
    if not text:
        return ""

    # 1. Delete the USYSTEMS REALTIMEsch block and everything inside it to the end of the line or block
    text = re.sub(r'\[SYSTEM REALTIME\].*?(\n|$)', '', text, flags=re.IGNORECASE)
    
    # 2. Delete lines with date and time if they duplicate the system prompt
    # Primer: Data: 13.12.2025...
    text = re.sub(r'Data:\s*\d{2}\.\d{2}\.\d{4}.*?(\n|$)', '', text, flags=re.IGNORECASE)

    # 3. Remove the “Echo” of the beginning of the answer if the model stupidly repeats the input
    # (Deletes lines like "Current time: **...**" if they are at the beginning of the text)
    text = re.sub(r'^Tekuschee vremya:\s*\*\*.*?\*\*.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^Fizicheskoe mestopolozhenie yadra:.*?\n', '', text, flags=re.MULTILINE)

    # 4. Remove the technical signature of LM Studio (in brackets at the end)
    # Primer: (🧠 lokalnaya LM Studio (fast/ctx-budget))
    text = re.sub(r'\(\s*🧠.*?\)', '', text)

    # 5. Remove double line feeds that occurred after cutting
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Final cleaning of spaces
    return text.strip()
