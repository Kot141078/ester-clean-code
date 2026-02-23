from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    from modules.thinking import loop_full as lf
    print("status:", lf.status())
    print("start:", lf.start("verify"))
    print("pause:", lf.pause("verify"))
    print("resume:", lf.resume("verify"))
    print("stop:", lf.stop("verify"))
if __name__ == "__main__":
    main()