import os
import chromadb
from chromadb.config import Settings
import shutil
import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- KONFIGURATsIYa ---

ROOT = Path(__file__).resolve().parent

# 1. WHERE it drains (Current active memory of Esther)
TARGET_PATH = str(ROOT / "vstore" / "chroma")

# 2. OTKUDA zabiraem (Spisok starykh baz)
# I use equal-strings so that Pothon can print the % and slashes correctly
SOURCES = [
    os.path.expandvars(str(ROOT / "%ESTER_VSTORE_ROOT%" / "chroma")),
    os.path.expandvars(str(Path(os.getenv("ESTER_HOME", str(ROOT))) / "vstore" / "chroma")),
]

def migrate():
    print("--- ESTER MEMORY MIGRATION TOOL ---")
    
    # Checking the target folder
    if not os.path.exists(TARGET_PATH):
        print(f"⚠️ Target path does not exist, creating: {TARGET_PATH}")
        os.makedirs(TARGET_PATH, exist_ok=True)

    # Connecting to the Target Database
    print(f"\n🔌 Connecting to TARGET (Active Brain): {TARGET_PATH}")
    try:
        target_client = chromadb.PersistentClient(path=TARGET_PATH)
        print("✅ Target connected.")
    except Exception as e:
        print(f"❌ Failed to open target DB: {e}")
        return

    total_migrated = 0

    # Prokhodim po starym bazam
    for src_path in SOURCES:
        print(f"\n🔍 Inspecting SOURCE: {src_path}")
        
        # Check for existence (sometimes a file path, sometimes a folder)
        # ChromaDB requires the path to the FOLDER where chroma.sklit3 is located
        real_src_path = src_path
        if src_path.endswith(".sqlite3"):
            real_src_path = os.path.dirname(src_path)
            
        if not os.path.exists(real_src_path):
            print(f"⚠️ Source path not found (skipping): {real_src_path}")
            continue

        try:
            # Connects to Source
            source_client = chromadb.PersistentClient(path=real_src_path)
            collections = source_client.list_collections()
            print(f"   Found {len(collections)} collections in source.")

            for col in collections:
                print(f"   >> Migrating collection: '{col.name}'...")
                
                # Gets data from a source
                src_col = source_client.get_collection(col.name)
                # Take everything (limit=None may not work in older versions, take get())
                data = src_col.get(include=['documents', 'metadatas', 'embeddings'])
                
                ids = data['ids']
                embeddings = data['embeddings']
                documents = data['documents']
                metadatas = data['metadatas']
                
                count = len(ids)
                if count == 0:
                    print("      (Empty collection, skipping)")
                    continue

                # Create or take a collection in Target
                # Ispolzuem get_or_create_collection
                tgt_col = target_client.get_or_create_collection(
                    name=col.name,
                    metadata=col.metadata # Copies collection settings
                )

                # We insert in packs of 1000 so as not to choke on memory
                batch_size = 1000
                for i in range(0, count, batch_size):
                    end = i + batch_size
                    print(f"Pushing batch {i}..{min(end, count)} / {count}")
                    tgt_col.upsert(
                        ids=ids[i:end],
                        embeddings=embeddings[i:end] if embeddings else None,
                        documents=documents[i:end] if documents else None,
                        metadatas=metadatas[i:end] if metadatas else None
                    )
                
                total_migrated += count
                print(f"      ✅ Done. +{count} memories.")

        except Exception as e:
            print(f"❌ Error migrating from {src_path}: {e}")

    print(f"\n🎉 MIGRATION COMPLETE.")
    print(f"Total memories merged into Active Brain: {total_migrated}")
    print("You can now start Ester.")

if __name__ == "__main__":
    # Checking dependencies
    try:
        import chromadb
        migrate()
    except ImportError:
        print("❌ ChromaDB library not found. Run: pip install chromadb")
