import os
import chromadb
from chromadb.config import Settings
import shutil
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- KONFIGURATsIYa ---

# 1. KUDA slivaem (Tekuschaya aktivnaya pamyat Ester)
TARGET_PATH = r"D:\ester-project\vstore\chroma"

# 2. OTKUDA zabiraem (Spisok starykh baz)
# Ya ispolzuyu raw-stroki, chtoby Python sel simvoly % i sleshi korrektno
SOURCES = [
    r"D:\ester-project\%ESTER_VSTORE_ROOT%\chroma",  # Tvoi 3 GB
    r"D:\ester-project\%ESTER_HOME%\vstore\chroma"   # Tvoi 600 MB
]

def migrate():
    print("--- ESTER MEMORY MIGRATION TOOL ---")
    
    # Proveryaem tselevuyu papku
    if not os.path.exists(TARGET_PATH):
        print(f"⚠️ Target path does not exist, creating: {TARGET_PATH}")
        os.makedirs(TARGET_PATH, exist_ok=True)

    # Podklyuchaemsya k TsELEVOY baze
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
        
        # Proverka na suschestvovanie (inogda put k faylu, inogda k papke)
        # ChromaDB trebuet put k PAPKE, gde lezhit chroma.sqlite3
        real_src_path = src_path
        if src_path.endswith(".sqlite3"):
            real_src_path = os.path.dirname(src_path)
            
        if not os.path.exists(real_src_path):
            print(f"⚠️ Source path not found (skipping): {real_src_path}")
            continue

        try:
            # Podklyuchaemsya k ISTOChNIKU
            source_client = chromadb.PersistentClient(path=real_src_path)
            collections = source_client.list_collections()
            print(f"   Found {len(collections)} collections in source.")

            for col in collections:
                print(f"   >> Migrating collection: '{col.name}'...")
                
                # Poluchaem dannye iz istochnika
                src_col = source_client.get_collection(col.name)
                # Berem vse (limit=None v starykh versiyakh mozhet ne rabotat, berem get())
                data = src_col.get(include=['documents', 'metadatas', 'embeddings'])
                
                ids = data['ids']
                embeddings = data['embeddings']
                documents = data['documents']
                metadatas = data['metadatas']
                
                count = len(ids)
                if count == 0:
                    print("      (Empty collection, skipping)")
                    continue

                # Sozdaem ili berem kollektsiyu v TsELI
                # Ispolzuem get_or_create_collection
                tgt_col = target_client.get_or_create_collection(
                    name=col.name,
                    metadata=col.metadata # Kopiruem nastroyki kollektsii
                )

                # Vstavlyaem pachkami po 1000, chtoby ne podavitsya pamyatyu
                batch_size = 1000
                for i in range(0, count, batch_size):
                    end = i + batch_size
                    print(f"      Pushing batch {i}..{min(end, count)} / {count}")
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
    # Proverka zavisimostey
    try:
        import chromadb
        migrate()
    except ImportError:
        print("❌ ChromaDB library not found. Run: pip install chromadb")