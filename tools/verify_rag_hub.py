from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    from modules.rag import hub
    hub.reset()
    print("status0:", hub.status())
    print("add1:", hub.add_text("Begemot letaet nad Neapolem", {"lang":"ru"}))
    print("add2:", hub.add_text("A hippopotamus is not a bird", {"lang":"en"}))
    print("add3:", hub.add_text("Slon khodit po beregu Nila", {"lang":"ru"}))
    print("status1:", hub.status())
    print("search ru:", hub.search("begemot ptitsa"))
    print("search en:", hub.search("hippopotamus bird"))
if __name__ == "__main__":
    main()