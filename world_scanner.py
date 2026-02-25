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

# --- Perception SETTINGS ---
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

# --- Connection ---
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
    """Creates a unique fingerprint (MD5) of the file contents."""
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
    print("--- I will skip what I already know ---")

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

                # 1. Take a fingerprint (Cache)
                file_hash = compute_file_hash(filepath)
                if not file_hash: continue

                # 2. MEMORY CHECK: Do we know this hash?
                # Searches the database for a record that has the same cache in its metadata
                existing = brain.get(where={"file_hash": file_hash})
                
                if existing['ids']:
                    # We have already seen this file and it has NOT CHANGED
                    # print(f"ySKIPshch ZZF0Z (no changes)") # Can be uncommented for debugging
                    skipped_files += 1
                    continue

                # 3. If there is no hash, then the file is NEW or CHANGED
                # Let's check if we knew a file with the same name before (but with a different hash)?
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
                    "file_hash": file_hash,  # <-- Here is the key mark
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

    print(f"✨ OTCHET O SKANIROVANII ✨")
    print(f"📂 Propuscheno (uzhe znala): {skipped_files}")
    print(f"🆕 Izucheno novykh faylov: {new_files}")
    print(f"📝 Pereosmysleno update: {updated_files}")

if __name__ == "__main__":
    target = input("Enter the path to scan (for example ZZF0ZSERPROFILE%eDownloads):").strip()
    if target:
        scan_drive(target)
    else:
        print("Put ne ukazan.")
    input("Press Enter to exit...")
