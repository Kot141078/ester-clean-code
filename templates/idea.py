from modules.memory.facade import memory_add, ESTER_MEM_FACADE

## 1) Upravlenie granitsey konteksta (preduprezhdat zaranee, ne «prygat» molcha)

**Chto nuzhno**

* Zhivoy schetchik tokenov i dva poroga: `WARN` (napr. ostalos <15%) i `HARD` (<5%).
* Pered `WARN` — nenavyazchivyy banner/tost + zvukovoy «ping» dlya golosovogo rezhima.
* Knopki vybora:

  1. **«Summirovat i prodolzhit»** (avtosvodka → perenos v novuyu sessiyu),
  2. **«Nachat chistuyu sessiyu»**,
  3. **«Umestit v tekuschuyu»** (szhat khvost istorii: remove/compact).
* Dlya **golosovogo vvoda**: ne nachinat novuyu sessiyu, poka polzovatel govorit; dogovarivat — i tolko potom pokazyvat modalku. Esli «umeem» raspoznavat rech — buferizovat, zatem pokazat modalku s tremya variantami.

**Psevdokod yadra monitoringa**

```python
class ContextBudget:
    def __init__(self, max_tokens:int, warn_ratio:float=0.85, hard_ratio:float=0.95):
        self.max = max_tokens
        self.warn = int(max_tokens*warn_ratio)
        self.hard = int(max_tokens*hard_ratio)

    def remaining(self, used:int)->int:
        return max(self.max - used, 0)

    def state(self, used:int)->str:
        r = self.remaining(used)
        if r <= self.hard: return "HARD"
        if r <= self.warn: return "WARN"
# return "OK"  # Fixed: invalid character '—' (U+2014) (<unknown>, line 7)