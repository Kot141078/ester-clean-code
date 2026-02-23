# -*- coding: utf-8 -*-
import os
import sys
import uuid
import time
import logging
import hashlib
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- NASTROYKI VOSPRIYaTIYa ---
IGNORE_DIRS = {
    'Windows', 'Program Files', 'Program Files (x86)', 'ProgramData', 
    '$RECYCLE.BIN', 'System Volume Information', 'AppData', 
    'node_modules', '.git', '__pycache__', 'venv', 'env', '.idea', '.vscode'
}

INTERESTING_EXTS = {
    '.txt', '.md', '.markdown',          
    '.py', '.js', '.json', '.html', '.css',      
    '.csv', '.xml', '.yaml', '.yml',     
    '.pdf',                              
    '.log', '.ini', '.cfg', '.bat', '.ps1'
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB (podnyali limit)

# --- PODKLYuChENIE ---
load_dotenv()
USER_PROFILE = os.environ.get("USERPROFILE")
raw_path = os.environ.get("CHROMA_PERSIST_DIR", r"%USERPROFILE%\.ester\vstore\chroma")
VECTOR_DB_PATH = os.path.expandvars(raw_path.replace("%USERPROFILE%", USER_PROFILE))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')

def get_brain():
    print(f"🔌 Podklyuchenie k pamyati: {VECTOR_DB_PATH}")
    client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return client.get_or_create_collection(name="ester_long_term", embedding_function=ef)

def compute_file_hash(filepath):
    """Sozdaet unikalnyy otpechatok (MD5) soderzhimogo fayla."""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None

def scan_drive(start_path):
    brain = get_brain()
    print(f"🚀 Ester nachinaet umnoe skanirovanie: {start_path}")
    print("--- Ya budu propuskat to, chto uzhe znayu ---")

    new_files = 0
    skipped_files = 0
    updated_files = 0

    for root, dirs, files in os.walk(start_path):
        # Filtratsiya papok
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in INTERESTING_EXTS: continue
            if file.startswith('.'): continue

            filepath = os.path.join(root, file)

            try:
                if os.path.getsize(filepath) > MAX_FILE_SIZE: continue

                # 1. Snimaem otpechatok (Khesh)
                file_hash = compute_file_hash(filepath)
                if not file_hash: continue

                # 2. PROVERKA PAMYaTI: Znaem li my etot khesh?
                # Ischem v baze zapis, u kotoroy v metadannykh takoy zhe khesh
                existing = brain.get(where={"file_hash": file_hash})
                
                if existing['ids']:
                    # My uzhe videli etot fayl, i on NE IZMENILSYa
                    # print(f"[SKIP] {file} (bez izmeneniy)") # Mozhno raskommentit dlya debaga
                    skipped_files += 1
                    continue

                # 3. Esli khesha net, znachit fayl NOVYY ili IZMENENNYY
                # Proverim, znali li my fayl s takim imenem ranshe (no s drugim kheshem)?
                old_version = brain.get(where={"source": filepath})
                is_update = len(old_version['ids']) > 0

                # Chitaem tekst
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()

                if len(content) < 10: continue

                # Formiruem vospominanie
                memory_text = f"Fayl: {filepath}\nSoderzhimoe:\n{content[:4000]}" # Chitaem pervye 4000 simvolov
                
                doc_id = str(uuid.uuid4())
                meta = {
                    "source": filepath,
                    "file_hash": file_hash,  # <-- Vot klyuchevaya metka
                    "type": "world_scan", 
                    "drive": os.path.splitdrive(filepath)[0],
                    "ts": time.time()
                }

                brain.add(documents=[memory_text], metadatas=[meta], ids=[doc_id])
                
                if is_update:
                    print(f"[UPDATE] 📝 Fayl izmenilsya: {file}")
                    updated_files += 1
                else:
                    print(f"[NEW] ✨ Izucheno novoe: {file}")
                    new_files += 1

            except KeyboardInterrupt:
                print("\n🛑 Skanirovanie prervano.")
                return
            except Exception as e:
                continue

    print(f"\n✨ OTChET O SKANIROVANII ✨")
    print(f"📂 Propuscheno (uzhe znala): {skipped_files}")
    print(f"🆕 Izucheno novykh faylov: {new_files}")
    print(f"📝 Pereosmysleno obnovleniy: {updated_files}")

if __name__ == "__main__":
    target = input("Vvedite put dlya skanirovaniya (naprimer %USERPROFILE%\\Downloads): ").strip()
    if target:
        scan_drive(target)
    else:
        print("Put ne ukazan.")
    input("\nNazhmite Enter, chtoby vyyti...")
