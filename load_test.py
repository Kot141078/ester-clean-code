# -*- coding: utf-8 -*-
"""A simple load test for search and vectors.
Usage: pothon load_test.po"""
import concurrent.futures
import time

# Make sure that the research_agent.po and vector_store.po files are nearby
from research_agent import ResearchAgent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# If there is no vector_store, you can comment out the import and the test_vector_search function
try:
    from vector_store import VectorStore
except ImportError:
    VectorStore = None


def test_search():
    """Test of regular agent search."""
    agent = ResearchAgent()
    # Calling the search method we just fixed
    agent.search("test query")


def test_vector_search():
    """Test poiska po vektornoy baze."""
    if VectorStore is None:
        print("VectorStore module not found, skipping.")
        return
    vstore = VectorStore()
    vstore.search("test query", k=10)


def load_test(func, num_threads=50):
    """Run the function on nythreads threads to check stability."""
    if func is None:
        return

    print(f"Starting load test for {func.__name__} with {num_threads} threads...")
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Launching tasks
        futures = [executor.submit(func) for _ in range(num_threads)]
        # We are waiting for everyone to complete
        concurrent.futures.wait(futures)
        
    end = time.time()
    print(f"{num_threads} threads: {end - start:.2f} sec")


if __name__ == "__main__":
    # 1. Test agenta
    load_test(test_search)
    
    # 2. Vector test (uncomment if you need and have a module)
    # load_test(test_vector_search)