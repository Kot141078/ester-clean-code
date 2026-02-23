# -*- coding: utf-8 -*-
"""
Prostoy nagruzochnyy test dlya poiska i vektorki.
Ispolzovanie: python load_test.py
"""
import concurrent.futures
import time

# Ubedis, chto fayly research_agent.py i vector_store.py lezhat ryadom
from research_agent import ResearchAgent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Esli vector_store net, mozhno zakommentirovat import i funktsiyu test_vector_search
try:
    from vector_store import VectorStore
except ImportError:
    VectorStore = None


def test_search():
    """Test obychnogo poiska agenta."""
    agent = ResearchAgent()
    # Vyzov metoda search, kotoryy my tolko chto pochinili
    agent.search("test query")


def test_vector_search():
    """Test poiska po vektornoy baze."""
    if VectorStore is None:
        print("VectorStore module not found, skipping.")
        return
    vstore = VectorStore()
    vstore.search("test query", k=10)


def load_test(func, num_threads=50):
    """Zapusk funktsii v num_threads potokakh dlya proverki stabilnosti."""
    if func is None:
        return

    print(f"Starting load test for {func.__name__} with {num_threads} threads...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Zapuskaem zadachi
        futures = [executor.submit(func) for _ in range(num_threads)]
        # Zhdem zaversheniya vsekh
        concurrent.futures.wait(futures)
        
    end = time.time()
    print(f"{num_threads} threads: {end - start:.2f} sec")


if __name__ == "__main__":
    # 1. Test agenta
    load_test(test_search)
    
    # 2. Test vektorki (raskommentiruy, esli nuzhen i est modul)
    # load_test(test_vector_search)