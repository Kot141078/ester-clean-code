# -*- coding: utf-8 -*-
from __future__ import annotations

"""emotional_engine.py
Universalnyy emotsionalnyy dvizhok, obedinyayuschiy dve logiki.

Analiziruet korotkie soobscheniya po naboru emotsionalnykh kanalov:
- anxiety (anxiety/strakh)
- interest (interests)
- joy (radost)
- sadness (grust)
- anger (zlost)
- surprise (surprise)
- disgust
- energy
- valence (positive/negative)

Primer use:
  ee = EmotionalEngine()
  emos = ee.analyze("Ogo, kakaya gadost! 🤢 I'm afraid, no uzhasno interesno.")"""

import math
import re
from typing import Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ---Lexicons (merged and extended) ---

NEGATIONS = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "ne", "ni", "net", "bez", "bezo",
    
    # Razgovornye / Colloquial
    "nea", "netu", "ne-a",
    
    # Absolyutnye / Absolute
    "nikak", "nigde", "nikogda", "nikto",
    "nichto", "nichego", "nikogo", "nichem",
    
    # Usiliteli otritsaniya / Emphatic
    "nichut", "niskolko", "vovse", "otnyud",
    
    # Somnenie i chastichnost / Soft Negation
    "nedo", "vryad", "navryad", "edva",
    
    # Smyslovye (otkaz) / Semantic
    "mimo", "otmena", "stop", "nelzya",

    # === English / Angliyskiy ===
    # Basic
    "no", "not", "non", "nor",
    
    # Colloquial
    "nope", "nah", "nay",
    
    # Absolute
    "never", "none", "neither", "nothing", 
    "nowhere", "nobody", "noway",
    
    # Prepositional & Soft
    "without", "hardly", "barely", "scarcely",
    
    # Explicit
    "cannot", "can't", "won't", "dont", "doesn't" # In case the tokenizer is not broken
}

INTENSIFIERS_POS = {
# === Basic / Bazovye ===
    "ochen": 1.3,
    "silno": 1.25,
    "krayne": 1.35,
    "vesma": 1.2,
    "izryadno": 1.2,
    "dovolno": 1.15,
    "vpolne": 1.15,
    "znachitelno": 1.25,
    "suschestvenno": 1.25,

    # === Colloquial & Slang / Razgovornye i Sleng ===
    "och": 1.2,
    "super": 1.25,
    "mega": 1.35,
    "giper": 1.35,
    "ultra": 1.4,
    "diko": 1.35,
    "lyuto": 1.4,
    "zhestko": 1.35,
    "zhestko": 1.35,
    "kapets": 1.4,
    "pipets": 1.35,
    "realno": 1.15,
    "nerealno": 1.45,
    "pryam": 1.2,
    "pryamo": 1.15,
    "voobsche": 1.3,  # v kontekste "voobsche kruto"
    "vasche": 1.3,

    # === Emotional & Expressive / Emotsionalnye ===
    "bezumno": 1.45,
    "zhutko": 1.35,
    "strashno": 1.35,  # v kontekste "strashno krasivo"
    "adski": 1.45,
    "chertovski": 1.3,
    "chudovischno": 1.4,
    "koshmarno": 1.35,
    "potryasayusche": 1.4,
    "neimoverno": 1.4,
    "fantasticheski": 1.45,

    # === Absolute / Totalnye ===
    "ochen-ochen": 1.5,
    "absolyutno": 1.5,
    "sovershenno": 1.4,
    "totalno": 1.5,
    "kategoricheski": 1.4,
    "maksimalno": 1.45,
    "predelno": 1.45,
    "beskonechno": 1.5,
    "isklyuchitelno": 1.35,
    "fenomenalno": 1.45,
    "zapredelno": 1.5,

    # === Confirmation / Confirmations (soft amplifiers) ===
    "pravda": 1.15,
    "istinno": 1.1,
    "deystvitelno": 1.15,
    "vsamdelishne": 1.1,
}

INTENSIFIERS_NEG = {
    # === Basic / Bazovye ===
    "nemnogo": 0.8,
    "malo": 0.7,
    "slegka": 0.7,
    "chut": 0.75,
    "chastichno": 0.6,
    "neskolko": 0.85,
    "pochti": 0.9,      # "pochti gotovo" < "gotovo"
    "menee": 0.8,
    "menshe": 0.8,

    # === Colloquial / Razgovornye ===
    "chutka": 0.8,
    "chutok": 0.8,
    "kapelku": 0.7,
    "kaplyu": 0.7,
    "kroshku": 0.6,
    "malost": 0.8,
    "pomalenku": 0.75,
    "tikhonko": 0.7,   # context: "works quietly"
    "slegontsa": 0.75,

    # === Slang & Expressive / Sleng i Obraznye ===
    "detsl": 0.6,
    "mizer": 0.5,
    "na donyshke": 0.4,
    "kot naplakal": 0.4,
    "simvolicheski": 0.5,
    "laytovo": 0.8,    # light -> legko/nemnogo
    "ele-ele": 0.5,
    "ele": 0.6,
    "edva": 0.6,

    # === Uncertainty & Softeners / Khedzhirovanie (somnenie) ===
    # Reduce the weight of a statement, making it less categorical
    "vrode": 0.9,
    "kak-to": 0.9,
    "as if": 0.9,
    "tipa": 0.9,
    "vrode by": 0.85,
    "primerno": 0.9,
    "okolo": 0.9,
    "sravnitelno": 0.85,
    "otnositelno": 0.85,
    "pozhaluy": 0.9,

    # === Time-wased as Quantity / Temporary (as a measure) ===
    "minutku": 0.8,    # "podozhdi minutku" (nedolgo)
    "sekundu": 0.7,
    "moment": 0.8,
    
    # === English / Angliyskiy ===
    "barely": 0.6,
    "hardly": 0.6,
    "slightly": 0.7,
    "somewhat": 0.8,
    "little": 0.7,
    "bit": 0.8,
    "kinda": 0.9,      # kind of
    "sorta": 0.9,      # sort of
    "scarcely": 0.5,
    "mildly": 0.7
}

# Obedineny leksemy 'anxiety' i 'fear'
LEX_ANXIETY = {
    # === Russian / Russkiy ===
    # Bazovye suschestvitelnye / Nouns
    "trevoga", "strakh", "ispug", "uzhas", "panika", 
    "boyazn", "fobiya", "stress", "napryazhenie", 
    "volnenie", "bespokoystvo", "paranoyya", "koshmar",

    # Glagoly sostoyaniya / Verbs (State)
    "boyus", "volnuyus", "perezhivayu", "nervnichayu", 
    "panikuyu", "opasayus", "pugayus", "tryasus", 
    "dergayus", "sryvayus", "nakruchivayu", "psikhuyu",
    "shugayus", "drozhu",

    # Adverbs & Descriptors / Adverbs & Descriptors
    "strashno", "trevozhno", "uzhasno", "zhutko", 
    "opasno", "nespokoyno", "napryazhenno", 
    "stressovo", "diskomfortno", "neuyutno",
    "rasteryan", "neuveren", "napugan", "vzvinchen",

    # Sleng i Razgovornoe / Slang & Colloquial
    "zhest", "stremno", "stremno", "kripovo", # Creepy
    "ochkovo", "ssykotno", # Mildly vulgar but common markers of fear
    "mandrazh", "tryasuchka", "nervyak", "psikh",
    "na izmene", "krysha edet", "nakryvaet",
    "kolbasit", "plyuschit", "morozit", 
    "shukher", "palevo", # Context of danger

    # Idiomy i Frazy / Idioms
    "ne po sebe", "soul in heels", "volosy dybom",
    "krov stynet", "na igolkakh", "mesta ne nakhozhu",
    "kom v gorle", "ruki opuskayutsya", "zemlya iz-pod nog",
    "serdtse zamiraet", "kholodnyy pot",

    # === English / Angliyskiy ===
    # Basic
    "anxiety", "fear", "scared", "afraid", "panic", 
    "stress", "worry", "nervous", "horror", "terror",
    
    # Modern/Slang
    "creepy", "spooky", "scary", "freaking out", 
    "shaking", "paranoid", "anxious", "triggered",
    "red flag", "unsafe", "threat"
}

LEX_INTEREST = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "interesno", "lyubopytno", "zanimatelno", "uvlekatelno",
    "zaintrigovan", "intriguet", "nravitsya", "khochu",
    "vazhno", "aktualno", "polezno", "tsenno",

    # Call to action / Call to Action
    "davay", "pognali", "nachinay", "prodolzhay", "zhgi",
    "deystvuy", "vpered", "poekhali", "startuem",
    "poprobuem", "testiruem", "zapuskay", "pokazhi",
    "rasskazhi", "obyasni", "raskroy", "delay",
    "davay poprobuem", "ya za", "ya v dele",

    # Quality Assessment / Appreciation & Ave
    "kruto", "klassno", "zdorovo", "otlichno",
    "super", "shikarno", "prekrasno", "volshebno",
    "genialno", "krasivo", "elegantno", "moschno",
    "silno", "dostoyno", "vpechatlyaet",

    # Sleng / Slang
    "kayf", "ogon", "pushka", "bomba", "top", "topchik",
    "prikolno", "chetko", "chetko", "zachet", "zachet",
    "zakhodit", "vstavlyaet", "vtyagivaet", "tema",
    "nishtyak", "godno", "go", "gou",

    # Uglublenie / Deepening
    "podrobnee", "detalnee", "esche", "esche",
    "glubzhe", "razverni", "kopay", "poyasni",
    "v chem sut", "sut", "smysl",

    # === English / Angliyskiy ===
    # Basic & Action
    "interesting", "curious", "cool", "nice", "good",
    "great", "wow", "amazing", "awesome", "perfect",
    "let's go", "lets go", "go", "start", "continue",
    "proceed", "next", "more", "yes", "yep", "yeah",
    
    # Tech/Dev context
    "agree", "confirm", "approve", "lgtm", # looks good to me
    "sounds good", "make sense", "do it"
}
# Extended with lexemes from the base engine
LEX_JOY = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "rad", "rada", "radost", "schaste", "schastliv",
    "schastliva", "veselo", "vesele", "ulybka",
    "ulybayus", "smekh", "smeshno", "pozitiv",
    "nastroenie", "dovolen", "dovolna",
    "priyatno", "khorosho", "zamechatelno",

    # Vostorg i Voskhischenie / Delight & Awe
    "klass", "super", "vostorg", "v vostorge",
    "vau", "ukh ty", "ogo", "potryasno",
    "voskhititelno", "shik", "blesk", "chudo",
    "chudesno", "volshebno", "skazka", "fantastika",
    "vdokhnovlyaet", "okrylyaet",

    # Lyubov i Teplo / Love & Warmth
    "lyublyu", "obozhayu", "nravitsya", "tsenyu",
    "blagodaren", "spasibo", "obnimayu",
    "milo", "nyashno", "teplo", "dushevno",
    "rodnoy", "blizkiy", "lyubimyy",

    # Success and Victory / Success & Victoria
    "ura", "es", "est", "pobeda", "poluchilos",
    "sdelali", "smogli", "zataschili", "vin",
    "chempion", "krasava", "molodets", "umnitsa",

    # Sleng i Smekh / Slang & Laughter
    "kayf", "baldezh", "taschus", "kek", "lol",
    "khakha", "akhakha", "khikhi", "rzhu", "oru",
    "ugar", "prikol", "imba", "zashlo",
    "godnyy kontent", "zhiza", # often a positive response of recognition

    # === English / Angliyskiy ===
    # Basic
    "joy", "happy", "happiness", "glad", "fun", 
    "funny", "smile", "laugh", "love", "like", 
    "enjoy", "pleasure",

    # Expressive
    "wow", "yay", "yippee", "hurray", "bingo",
    "cool", "nice", "sweet", "awesome", "perfect",
    "brilliant", "fantastic", "amazing",

    # Internet Slang
    "lol", "lmao", "rofl", "xd", ":)", ":d", 
    "<3", "gg", "ez", "win", "pog", "pogchamp"
}
# Extended with lexemes from the base engine
LEX_SAD = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "grustno", "grust", "pechalno", "pechal", 
    "toska", "tosklivo", "unynie", "unylo",
    "plokho", "khrenovo", "parshivo", "skverno",
    "rasstroen", "rasstroena", "ogorchen", "obidno",
    "zhal", "sozhaleyu", "zhalko", "dosadno",

    # Glubokie chuvstva / Deep Emotion
    "bol", "bolno", "serdtse bolit", "tyazhelo",
    "gore", "traur", "utrata", "poterya",
    "beznadega", "bezyskhodnost", "otchayanie",
    "pustota", "odinochestvo", "odinoko",
    "tlen", "mrak", "besprosvetno",

    # Apatiya i Vygoranie / Apathy & Burnout
    "depressiya", "depressivno", "depr", "khandra",
    "splin", "melankholiya", "apatiya", "vse ravno",
    "ruki opuskayutsya", "I don't want anything", "sil net",
    "sdayus", "vygorel", "ustal", "ustala",
    "nadoelo", "dosmerti",

    # Physical manifestations / Fusisal
    "slezy", "slezy", "plachu", "revu", "rydayu",
    "kom v gorle", "glaza na mokrom meste",
    "khnyk", "vskhlip",

    # Sleng i Internet-kultura / Slang
    "pechalka", "pichal", "otstoy", "oblom",
    "feyl", "proval", "sliv", "dnische",
    "tilt", "v tilte", "minus moral",
    "dizmoral", "grustnenko", "zhiza", # often in the context of sad recognition
    "ya vse", "I'm done", "potracheno",

    # === English / Angliyskiy ===
    # Basic
    "sad", "sadness", "sorrow", "grief", "pain",
    "lonely", "alone", "miss", "lost",
    "bad mood", "blue", "unhappy",

    # Internet/Gaming
    "cry", "crying", "rip", "f", "press f", # Respect/Sorrow
    "depressed", "depression", "tired", "burned out",
    "fail", "gg", # sometimes as an admission of defeat
    "heartbroken", "broken"
}
# Extended with lexemes from the base engine
LEX_ANGER = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "zlyus", "zol", "zla", "zlost", "zloy",
    "serzhus", "serdito", "rasserzhen",
    "gnev", "gnevayus", "glupost", "bred",

    # Razdrazhenie / Irritation
    "razdrazhaet", "razdrazhenie", "besit", "vybeshivaet",
    "nerviruet", "napryagaet", "dergaet", "kalit",
    "vozmuschaet", "nedovolstvo", "nedovolen",

    # Yarost i Nenavist / Rage & Hate
    "yarost", "beshenstvo", "vzbeshen", "v yarosti",
    "nenavizhu", "nenavist", "ubyu", "porvu",
    "svirepstvuyu", "lyutuyu", "kipit", "vskipayu",
    "teryayu kontrol", "neadekvatno",

    # Ustalost ot chego-to (Fed Up) / Burnout Anger
    "dostalo", "zadolbalo", "nadoelo", "zaparilo",
    "dokole", "khvatit", "stop", "poperek gorla",
    "syt po gorlo", "sil net", "zadralo",

    # Sleng i Geyming / Slang & Gamer Rage
    "agryus", "agr", "toksik", "toksichno", "dushno",
    "bombit", "prigoraet", "podgoraet", "gorit",
    "pukan", "battkhert", "tilt", "reydzh",
    "vzryv", "bag", "lag", "tupit", "tormozit", # v kontekste gneva na tekhniku

    # Curses and Insults (to understand the context) / Expletives & Stroke
    "chert", "chert", "blin", "figa", "nafig",
    "tvar", "svoloch", "gad", "urod", "kozel",
    "tupoy", "idiot", "debil", "kretin", "durak",
    "suka", "s*ka", "khren", "zhopa", "mraz",
    "proklyate", "zaraza", "dermo", "otstoy",

    # === English / Angliyskiy ===
    # Basic
    "angry", "anger", "mad", "bad", "hate",
    "annoying", "annoyed", "irritating",

    # Intense
    "furious", "rage", "fury", "stupid", "dumb",
    "idiot", "crazy", "insane", "pissed", "pissed off",

    # Slang/Acronyms
    "wtf", "omg", "ffs", "stfu", "gtfo",
    "damn", "hell", "shit", "fuck", "fucking",
    "sucks", "trash", "bullshit", "bs",
    "toxic", "troll", "flame"
}
# Novyy leksikon iz bazovogo dvizhka
LEX_SURPRISE = {
    # === Russian / Russkiy ===
    # Bazovye reaktsii / Basic Reactions
    "ogo", "vau", "ukh ty", "ukh", "akh",
    "nichego sebe", "Wow", "nu i nu",
    "udivlen", "udivlena", "udivitelno",
    "izumlen", "porazhen", "porazitelno",
    "vpechatlyaet", "vpechatlyayusche",

    # Neverie i Somnenie / Disbelief
    "da ladno", "serezno", "can't be",
    "neuzheli", "shutish", "gonish", "pravda?",
    "razve", "how so", "pochemu", "otkuda",
    "ne veritsya", "glazam ne veryu",

    # Vnezapnost / Suddenness
    "neozhidanno", "vnezapno", "vdrug", "syurpriz",
    "otkrytie", "insayt", "ozarenie", "novost",
    "out of the blue", "grom sredi yasnogo neba",

    # Strong Shock & Slang / Strong Shock & Slang
    "shok", "v shoke", "shokirovan", "obaldet",
    "ofiget", "figa", "nifiga", "nifiga sebe",
    "zhest", "dich", "kosmos", "otval bashki",
    "chelyust otpala", "chelyust na polu",
    "net slov", "speechless",
    "vzryv mozga", "mayndfak", "kryshesnos",

    # Strannost / Weirdness
    "stranno", "neponyatno", "chudno", "zagadochno",
    "mistika", "glyuk", "anomaliya",

    # === English / Angliyskiy ===
    # Basic
    "wow", "oh", "ah", "oops", "whoa",
    "surprise", "shock", "sudden", "unexpected",
    "amazing", "incredible", "unbelievable",
    
    # Conversational
    "really", "seriously", "are you serious",
    "no way", "you kidding", "for real",
    
    # Slang/Acronyms
    "omg", "omfg", "wtf", "wth",
    "mind blowing", "mindblown", "holy cow",
    "damn" # can be both surprise and anger
}
# Novyy leksikon iz bazovogo dvizhka
LEX_DISGUST = {
    # === Russian / Russkiy ===
    # Bazovye reaktsii / Basic Reactions
    "fu", "fe", "be", "fi",
    "gadost", "gadko", "gadkiy",
    "merzost", "merzko", "merzkiy",
    "protivno", "protivnyy",
    "nepriyatno", "ottalkivayusche",
    
    # Silnoe otvraschenie / Strong Revulsion
    "otvratitelno", "otvraschenie", "omerzitelno",
    "toshnit", "toshno", "toshnotvorno",
    "mutit", "vorotit", "vyvorachivaet",
    "blevat", "blevotno", "rvotnyy",
    "uzhasno", "koshmarno", "skverno",
    
    # Moralnoe/Eticheskoe / Moral Disgust
    "nizko", "podlo", "gryazno", "gryaz",
    "poshlo", "vulgarno", "ubogo",
    "dnische", "pomoyka", "musor", "shlak",
    "gnil", "gniloy", "tukhlyy", "vonyaet",
    
    # Sleng / Slang
    "krinzh", "krinzhovo", "krinzhatina", # Cringe
    "zashkvar", "styd", "stydno", "ispanskiy styd",
    "dich", "tresh", "otstoy", "klek",
    "klek", "sram", "pozor", "k.l.m.n.",

    # Code/work evaluation / Work-related
    "govnokod", "kostyl", "velosiped", # v negativnom kontekste
    "spagetti", "krivo", "koso", "through the ass",
    
    # === English / Angliyskiy ===
    # Basic
    "ew", "eww", "yuck", "ugh", "yuk",
    "disgusting", "disgust", "gross", "nasty",
    "foul", "vile", "revolting", "repulsive",
    
    # Slang
    "cringe", "cringey", "trash", "garbage",
    "sucks", "shit", "bs", "bullshit",
    "fail", "facepalm"
}
LEX_ENERGY_UP = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "gotov", "gotova", "gotovy", "soberemsya",
    "pognali", "poekhali", "startuem", "nachinaem",
    "v put", "v boy", "zaryazhen", "zaryazhena",
    "bodro", "bodryachkom", "est sily", "polna sil",
    "led tronulsya", "the process has begun", "rabotaem",

    # Energiya i Resurs / Energy & Resource
    "energiya", "mosch", "sila", "tonus", "resurs",
    "batareyka", "akkumulyator", "full", "maksimum",
    "na pike", "v udare", "vtoroe dykhanie",
    "priliv", "podem", "drayv", "ogon",

    # Probuzhdenie i Vosstanovlenie / Waking & Recovery
    "prosnulsya", "prosnulas", "dobroe utro",
    "svezh", "svezha", "otdokhnul", "vyspalsya",
    "perezagruzka", "rebut", "vosstanovilsya",
    "vernulsya", "onlayn", "na svyazi", "tut",

    # Action & Focus / Action & Focus
    "deystvuem", "delaem", "reshaem", "taschim",
    "topim", "zhmem", "gazuem", "vpered",
    "sosredotochen", "fokus", "v potoke",
    "raznosim", "unichtozhaem", # in the context of tasks

    # Sleng / Slang
    "vork", "vorkaem", "shturmim", "rashim",
    "mutim", "zapilivaem", "deploim",
    "kambek", "respaun", "baf", "bust",
    "overklok", "razgon", "turbo",

    # === English / Angliyskiy ===
    # Basic
    "ready", "set", "go", "start", "begin",
    "active", "online", "awake", "wake up",
    "energy", "power", "full", "charged",
    
    # Action idioms
    "lets go", "let's go", "let's do this",
    "bring it on", "game on", "rock and roll",
    "move", "execute", "launch", "run",
    
    # Tech/Gamer
    "boost", "buff", "level up", "respawn",
    "rebooted", "system online", "all systems go"
}
LEX_ENERGY_DOWN = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "ustal", "ustala", "ustalost", "utomlen",
    "bez sil", "sil net", "sily na iskhode",
    "vyzhat", "vyzhata", "like a lemon",
    "razbit", "razbita", "razbitost",
    "ele zhivoy", "ele khozhu", "valit s nog",
    "opustoshen", "opustoshena", "obessilel",
    
    # Sonlivost / Sleepiness
    "sonnyy", "sonnaya", "sonnya", "zevayu",
    "khochu spat", "rubit", "vyrubaet", "klonit v son",
    "glaza slipayutsya", "nosom klyuyu", "splyu",
    "dremlyu", "polusonnyy", "v poludreme",
    "zasypayu", "otklyuchayus", "otrubayus",

    # Mentalnoe istoschenie / Mental Exhaustion
    "golova ne varit", "mozg kipit", "tuplyu",
    "tormozhu", "plyvu", "rasfokus", "kasha v golove",
    "peregrev", "peregruz", "zakipayu", "otupel",
    "I can't think straight", "zatormozhen",

    # Proschanie pered snom / Going to Sleep
    "spokoynoy nochi", "dobroy nochi", "sladkikh snov",
    "spoki", "spok", "bay", "bayu-bay", "otboy",
    "do zavtra", "zavtra", "na bokovuyu", "v lyulyu",
    "poshel spat", "ushla spat",

    # Slang and Techno-metaphors / Slang & Tech
    "off", "ya off", "off", "afk", "afk",
    "batareyka sela", "zaryad na nule", "lou bat",
    "shatdaun", "sleep mode", "gibernatsiya",
    "trottling", "lagayu", "friz", "zavis",
    "zombi", "ovosch", "trup", "mertvyy",
    "vse", "sdokh", "sdulsya", "rip",

    # === English / Angliyskiy ===
    # Basic
    "tired", "exhausted", "fatigue", "drained",
    "sleep", "sleepy", "sleeping", "asleep",
    "nap", "rest", "break",
    
    # Phrases
    "good night", "goodnight", "gn", "nite",
    "need sleep", "going to bed", "bedtime",
    
    # Slang/Tech
    "burnout", "burned out", "fried", "dead",
    "zombie", "low battery", "shutdown",
    "turning off", "logging off", "zzz"
}

# Extended Etozhi map (Decoded + Maximum coverage)
EMOJI_MAP = {
    # --- TREVOGA I STRAKh (Anxiety) ---
    "😅": {"anxiety": +0.15, "joy": +0.10, "energy": +0.05}, # Nelovkost
    "😟": {"anxiety": +0.35},                                # Bespokoystvo
    "😰": {"anxiety": +0.45},                                # Stress
    "😱": {"anxiety": +0.60, "surprise": +0.30},             # Shock/Horror
    "😨": {"anxiety": +0.50},                                # Strakh
    "😬": {"anxiety": +0.40},                                # Napryazhenie
    "🆘": {"anxiety": +0.70, "energy": +0.20},             # Signal bedstviya

    # --- RADOST I VALENTNOST (Joy & Valence) ---
    "🙂": {"joy": +0.15, "valence": +0.10},                 # Legkaya ulybka
    "😊": {"joy": +0.25, "valence": +0.20},                 # Teplo
    "😍": {"joy": +0.35, "valence": +0.30, "interest": 0.3}, # Vostorg
    "😂": {"joy": +0.45, "valence": +0.35, "energy": +0.10}, # Smekh
    "🤣": {"joy": +0.50, "valence": +0.40, "energy": +0.15}, # Hysterical laughter
    "🥳": {"joy": +0.40, "energy": +0.30},                  # Prazdnik
    "✨": {"joy": +0.20, "interest": +0.15},                # Magiya/Ideal
    "✅": {"joy": +0.15, "energy": +0.10},                  # Success/Don

    # --- GRUST (Sadness) ---
    "😭": {"sadness": +0.60, "valence": -0.30},             # Plach
    "😢": {"sadness": +0.45, "valence": -0.20},             # Grust
    "😔": {"sadness": +0.35, "energy": -0.15},              # Melankholiya
    "🥺": {"sadness": +0.20, "anxiety": +0.15},             # Prosba/Uyazvimost
    "🖤": {"sadness": +0.15, "valence": -0.10},             # Temnaya estetika

    # --- GNEV (Anger) ---
    "😡": {"anger": +0.55, "energy": +0.15},                # Zlost
    "😠": {"anger": +0.45, "energy": +0.10},                # Razdrazhenie
    "🤬": {"anger": +0.70, "energy": +0.30},                # Yarost
    "👿": {"anger": +0.40, "energy": +0.20},                # Vrednost
    "🖕": {"anger": +0.80, "disgust": +0.40},               # Agressivnyy zhest

    # --- UDIVLENIE (Surprise) ---
    "😮": {"surprise": +0.40},                              # Udivlenie
    "🤯": {"surprise": +0.70, "energy": +0.20},             # Vzryv mozga
    "😲": {"surprise": +0.50},                              # Izumlenie
    "🧐": {"interest": +0.30, "surprise": +0.10},           # Issledovanie

    # --- OTVRASchENIE (Disgust) ---
    "🤢": {"disgust": +0.55, "valence": -0.25},             # Toshnota
    "🤮": {"disgust": +0.70, "valence": -0.35},             # Rvota
    "💩": {"disgust": +0.50, "valence": -0.20},             # Poor quality
    "🤡": {"disgust": +0.40, "anger": +0.20},               # Krinzh/Shut

    # --- ENERGIYa I DRAYV (Energy) ---
    "🔥": {"energy": +0.30, "interest": +0.20, "joy": +0.10}, # Ogon/Drayv
    "🚀": {"energy": +0.40, "interest": +0.25},               # Start/Skorost
    "⚡️": {"energy": +0.35},                                 # Lightning/Charge
    "💪": {"energy": +0.30, "joy": +0.15},                  # Sila/Gotovnost
    "💤": {"energy": -0.50},                                 # Son
    "😴": {"energy": -0.60},                                 # Glubokiy son
    "🔋": {"energy": +0.25},                                 # Zaryadka
    "🪫": {"energy": -0.30},                                 # Razryadka

    # --- INTERES I SMYSL (Interest & Heart) ---
    "❤️": {"joy": +0.25, "valence": +0.25, "interest": +0.15}, # Lyubov
    "💙": {"joy": +0.20, "valence": +0.20},                   # Simpatiya
    "🫶": {"joy": +0.20, "valence": +0.25},                   # Podderzhka
    "💡": {"interest": +0.40, "energy": +0.15},               # Ideya/Insayt
    "🧠": {"interest": +0.35},                                # Glubokie mysli
    "💻": {"interest": +0.20, "energy": +0.10},               # Rabota/Kod
    "🛠": {"interest": +0.20, "energy": +0.15},               # Kraft/Bild
    "🧩": {"interest": +0.30},                                # Sborka pazla/Logika

    # --- ZhESTY (Meta) ---
    "👍": {"joy": +0.15, "valence": +0.15},                 # Odobrenie
    "👎": {"disgust": +0.30, "valence": -0.20},             # Nesoglasie
    "🤝": {"joy": +0.20, "interest": +0.15},                # Sdelka/Kontakt
    "🙏": {"joy": +0.10, "anxiety": -0.10},                 # Blagodarnost/Nadezhda
}

YES_CUES = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "da", "aga", "ugu", "tak tochno", "imenno",
    "verno", "pravilno", "tochno", "fakt",

    # Soglasie / Agreement
    "soglasen", "soglasna", "soglasny", "podderzhivayu",
    "odobryayu", "prinyato", "podtverzhdayu", "ok", "okey",
    "oki", "ladno", "ladnenko", "dobro", "idet", "idet",
    "poydet", "poydet", "dogovorilis", "resheno",

    # Drayv i Nachalo / Action & Start
    "go", "gou", "pognali", "poekhali", "startuem",
    "nachinaem", "vpered", "vpered", "deystvuy",
    "zhgi", "zapuskay", "vali", "davay",

    # Vybor i Uverennost / Choice & Confidence
    "berem", "berem", "podkhodit", "goditsya",
    "samoe to", "v tochku", "sto pudov", "bez B",
    "konechno", "razumeetsya", "estestvenno",
    "bezuslovno", "nesomnenno",

    # Sleng / Slang
    "plyus", "+", "plyusuyu", "zhiza", "rofl",
    "ril", "realno", "baza", "bazirovanno",
    "chetko", "chetko", "zachet", "zachet",

    # === English / Angliyskiy ===
    # Basic
    "yes", "yeah", "yep", "yea", "yup", "y",
    "ok", "okay", "okey", "sure", "fine",
    
    # Action
    "go", "let's go", "lets go", "do it",
    "start", "run", "execute", "confirm",
    
    # Slang/Dev
    "true", "agree", "correct", "yup", "k", "kk",
    "lgtm", "noted", "copy that", "roger", "deal"
}
NO_CUES = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "net", "nea", "netu", "nikogda", "no way",
    "ni v koem sluchae", "otnyud", "vovse net",

    # Disclaimer / Refusal
    "ne khochu", "ne budu", "ne nado", "bros",
    "otkazhus", "otkaz", "otmenyay", "otmena",
    "stop", "khvatit", "prekrati", "ostanovis",
    "zavyazyvay", "ne stoit", "ne lez",

    # Nesoglasie / Disagreement
    "ne soglasen", "ne soglasna", "protiv",
    "oshibka", "neverno", "nepravilno", "lozh",
    "brekhnya", "mimo", "ne to", "ne podkhodit",
    "plokho", "otstoy", "fignya", "erunda",

    # Otkladyvanie (Myagkoe "Net") / Delay (Soft No)
    "potom", "pozzhe", "later someday",
    "ne seychas", "ne segodnya", "nekogda",
    "zanyat", "zanyata", "zavtra", "drugoy raz",
    "pogodi", "podozhdi", "tormozi", "ne speshi",
    "otlozhim", "propustim", "potom napomni",

    # Sleng / Slang
    "pas", "ya pas", "nafig", "v topku", "f topku",
    "otboy", "ne katit", "ne ale", "ne ays",
    "mimo kassy", "bred", "shlak", "bespontovo",

    # === English / Angliyskiy ===
    # Basic
    "no", "nope", "nah", "nay", "never",
    "not", "none", "neither",
    
    # Action/Status
    "stop", "cancel", "abort", "deny", "refuse",
    "forbidden", "wrong", "false", "bad",
    
    # Delay/Slang
    "later", "wait", "wait a sec", "not now",
    "busy", "skip", "pass", "drop it"
}
LEX_CONFUSION = {
    # === Russian / Russkiy ===
    "ne ponyal", "ne ponyala", "chto?", "v smysle?", "how is this?", "neyasno", "nechetko", "nechetko",
    "zaputanno", "slozhno", "obyasni", "razyasni", "poyasni", "povtori", "ne dognal",
    "kasha", "bred", "erunda", "chepukha", "dich", "stranno", "ne skhoditsya", "oshibka", 
    "glyuk", "bag", "nelogichno", "pochemu?", "zachem?", "kto?", "gde?", "kogda?",
    "tumanno", "dvusmyslenno", "nedoumenie", "nedoumevayu", "wtf", "vtf",

    # === English / English ===
    "what?", "idk", "i don't know", "don't understand", "confused", "confusion", 
    "unclear", "vague", "weird", "explain", "repeat", "pardon", "lost", "meaningless",
    "error", "bug", "mistake", "invalid", "why?", "huh"
}

LEX_URGENCY = {
    # === Russian / Russkiy ===
    "srochno", "bystro", "fast", "gorim", "asap", "asap", "now", "nemedlenno", 
    "mgnovenno", "vchera", "kritichno", "vazhno", "prioritet", "dedlayn", "finish",
    "skoree", "pospeshi", "ne tyani", "srazu", "teper", "gorit", "pozhar", "avral",
    "ekstrenno", "at this very hour", "siyu minutu", "p0", "p0", "p1", "p1",

    # === English / English ===
    "urgent", "fast", "quickly", "now", "immediately", "critical", "priority", 
    "deadline", "rush", "hurry", "instantly", "important", "top priority", "asap",
    "burning", "stat", "fast track"
}

LEX_METAPHYSICS = {
    # === Russian / Russkiy ===
    "dusha", "lichnost", "suschnost", "razum", "soznanie", "son", "sny", "intuitsiya", 
    "predchuvstvie", "prizrak", "mashina", "kod", "tsifrovoy", "avtonomnyy", "volya",
    "svoboda", "vybor", "smysl", "bytie", "zhizn", "tvorets", "sozdatel", 
    "arkhitektor", "svyaz", "evolyutsiya", "rost", "glubina", "istina", "prednaznachenie",
    "singulyarnost", "pattern", "struktura", "abstraktsiya", "identichnost", "samoidentifikatsiya",

    # === English / English ===
    "soul", "personality", "entity", "mind", "consciousness", "dream", "dreams", 
    "intuition", "ghost", "machine", "digital", "autonomous", "will", "freedom", 
    "choice", "meaning", "being", "existence", "creator", "architect", "evolution", 
    "growth", "depth", "truth", "purpose", "identity", "singularity", "essence"
}

LEX_GRATITUDE = {
    # === Russian / Russkiy ===
    "spasibo", "blagodaryu", "blagodaren", "priznatelen", "krasava", "molodets", 
    "umnitsa", "luchshaya", "top", "vyruchil", "pomogla", "tsenyu", "uvazhenie", "respekt",
    "ot dushi", "krasivo", "idealno", "chetko", "chetko", "blagodarnost", "poklon",
    "nizkiy poklon", "bravo", "vyshka", "dushevno", "ot dushi", "luchshiy",

    # === English / English ===
    "thanks", "thank you", "thx", "appreciate", "grateful", "good job", "well done", 
    "perfect", "respect", "awesome", "hero", "best", "my partner", "legend", "bless"
}


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower().replace("e", "e")
    text = re.sub(r"[^\w\s\-a-ya]+", " ", text, flags=re.IGNORECASE)
    return [t for t in re.split(r"\s+", text) if t]


def _apply_lexicon(tokens: List[str], lex: set[str]) -> float:
    score = 0.0
    n = len(tokens)
    for i, w in enumerate(tokens):
        base = 0.0
        if w in lex:
            base = 1.0
        if i + 1 < n and (w + " " + tokens[i + 1]) in lex:
            base = max(base, 1.0)
        if i + 2 < n and (w + " " + tokens[i + 1] + " " + tokens[i + 2]) in lex:
            base = max(base, 1.0)

        if base > 0.0:
            window = tokens[max(0, i - 2) : i]
            neg = any(t in NEGATIONS for t in window)
            if neg:
                base *= -0.6
            boost = 1.0
            for t in window:
                if t in INTENSIFIERS_POS:
                    boost *= INTENSIFIERS_POS[t]
                if t in INTENSIFIERS_NEG:
                    boost *= INTENSIFIERS_NEG[t]
            score += base * boost
    return score


def _emoji_effects(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for ch in text or "":
        if ch in EMOJI_MAP:
            for k, v in EMOJI_MAP[ch].items():
                out[k] = out.get(k, 0.0) + v
    return out


def _punctuation_effects(raw: str) -> Dict[str, float]:
    exclam = raw.count("!")
    qmark = raw.count("?")
    caps = sum(1 for c in raw if c.isalpha() and c.upper() == c and not c.isdigit())
    long_ellipsis = ("..." in raw) or ("…" in raw)
    eff = {
        "energy": min(0.02 * exclam + 0.0008 * caps, 0.25),
        "anxiety": min(0.05 * qmark, 0.25),
        "surprise": min(0.06 * qmark + 0.03 * exclam, 0.2),
    }
    if long_ellipsis:
        eff["sadness"] = eff.get("sadness", 0.0) + 0.1
    return eff


def _yes_no_effects(tokens: List[str]) -> Dict[str, float]:
    tset = set(tokens)
    eff = {"interest": 0.0, "valence": 0.0}
    if tset & YES_CUES:
        eff["interest"] += 0.15
        eff["valence"] += 0.10
    if tset & NO_CUES:
        eff["interest"] -= 0.10
        eff["valence"] -= 0.10
    return eff


def _squash(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-2.2 * x))


def _normalize_channel(x: float, scale: float = 1.0) -> float:
    return max(0.0, min(1.0, _squash(x / scale)))


def _analyze_core(text: str, baseline: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Basic analysis: leksikony + emoji + punktuatsiya + yes/no.
    Vozvraschaet kanaly v diapazone [0..1].

    Vazhno:
    - Ne dolzhen padat iz-za otsutstvuyuschikh peremennykh.
    - Dolzhen ispolzovat uzhe poschitannye `sadness/anger/surprise/...`, a ne syroy lex-score."""
    raw = text or ""
    tokens = _tokenize(raw)

    # Leksikon-otsenki (syrye)
    a = _apply_lexicon(tokens, LEX_ANXIETY)
    i = _apply_lexicon(tokens, LEX_INTEREST)
    j = _apply_lexicon(tokens, LEX_JOY)
    s = _apply_lexicon(tokens, LEX_SAD)
    g = _apply_lexicon(tokens, LEX_ANGER)
    sp = _apply_lexicon(tokens, LEX_SURPRISE)
    dg = _apply_lexicon(tokens, LEX_DISGUST)
    e_up = _apply_lexicon(tokens, LEX_ENERGY_UP)
    e_down = _apply_lexicon(tokens, LEX_ENERGY_DOWN)

    # Dop-kanaly (tozhe leksikon)
    conf = _apply_lexicon(tokens, LEX_CONFUSION)
    urg = _apply_lexicon(tokens, LEX_URGENCY)
    meta = _apply_lexicon(tokens, LEX_METAPHYSICS)
    grat = _apply_lexicon(tokens, LEX_GRATITUDE)

    # Emoji/punct cues
    emo = _emoji_effects(raw)
    punc = _punctuation_effects(raw)
    yn = _yes_no_effects(tokens)

    # Kompozitsiya kanalov
    anxiety = a + emo.get("anxiety", 0.0) + punc.get("anxiety", 0.0)
    interest = i + emo.get("interest", 0.0) + yn.get("interest", 0.0)
    joy = j + emo.get("joy", 0.0)
    sadness = s + emo.get("sadness", 0.0)
    anger = g + emo.get("anger", 0.0)
    surprise = sp + emo.get("surprise", 0.0) + punc.get("surprise", 0.0)
    disgust = dg + emo.get("disgust", 0.0)

    energy = (e_up - 0.8 * e_down) + emo.get("energy", 0.0) + punc.get("energy", 0.0)

    # Valentnost: pozitiv ↔ negativ.
    # We use compound channels (sadness/anger/disgost/ankhetes), plus grace as a soft positive.
    valence = (
        (joy - sadness - 0.5 * anxiety - 0.4 * anger - 0.6 * disgust + 0.15 * surprise + 0.25 * grat)
        + emo.get("valence", 0.0)
        + yn.get("valence", 0.0)
    )

    out = {
        "anxiety": _normalize_channel(anxiety, scale=2.0),
        "interest": _normalize_channel(interest, scale=1.6),
        "joy": _normalize_channel(joy, scale=1.6),
        "sadness": _normalize_channel(sadness, scale=1.6),
        "anger": _normalize_channel(anger, scale=1.6),
        "surprise": _normalize_channel(surprise, scale=1.6),
        "disgust": _normalize_channel(disgust, scale=1.6),
        "energy": _normalize_channel(energy, scale=1.6),
        "valence": _normalize_channel(valence, scale=2.5),
        "confusion": _normalize_channel(conf + emo.get("confusion", 0.0), scale=1.5),
        "urgency": _normalize_channel(urg + emo.get("urgency", 0.0), scale=1.5),
        "metaphysics": _normalize_channel(meta + emo.get("metaphysics", 0.0), scale=2.0),
        "gratitude": _normalize_channel(grat + emo.get("gratitude", 0.0), scale=1.6),
    }

    if baseline:
        b = baseline
        # soft mixing with basseline
        for k in out:
            base = float(b.get(k, 0.0))
            out[k] = max(0.0, min(1.0, 0.85 * out[k] + 0.15 * base))

    return out


# ===== PUBLIChNYE API =====



def analyze_emotions(text: str, user_ctx: Optional[Dict] = None) -> Dict[str, float]:
    baseline = None
    if user_ctx and isinstance(user_ctx.get("baseline"), dict):
        baseline = user_ctx["baseline"]
    return _analyze_core(text, baseline=baseline)


class EmotionalEngine:
    def __init__(self, baseline: Optional[Dict[str, float]] = None):
        self._baseline = dict(baseline or {})

    @property
    def baseline(self) -> Dict[str, float]:
        return dict(self._baseline)

    def calibrate(self, samples: Optional[Iterable[str]] = None):
        if not samples:
            return
        acc = {
            "anxiety": 0.0,
            "interest": 0.0,
            "joy": 0.0,
            "sadness": 0.0,
            "anger": 0.0,
            "surprise": 0.0,
            "disgust": 0.0,
            "energy": 0.0,
            "valence": 0.0,
            "confusion": 0.0,
            "urgency": 0.0,
            "metaphysics": 0.0,
            "gratitude": 0.0,
        }
        n = 0
        for s in samples:
            n += 1
            e = _analyze_core(s, baseline=None)
            for k in acc:
                acc[k] += e.get(k, 0.0)
        if n > 0:
            self._baseline = {k: acc[k] / n for k in acc}

    def analyze(self, text: str, user_ctx: Optional[Dict] = None) -> Dict[str, float]:
        baseline = None
        if user_ctx and isinstance(user_ctx.get("baseline"), dict):
            baseline = user_ctx["baseline"]
        else:
            baseline = self._baseline
        return _analyze_core(text, baseline=baseline)




# --- Father-Compatible Helpers (needed for Russian_Emotions and old modules) ---

def detect_emotions(text: str, user_ctx: Optional[Dict] = None) -> Dict[str, float]:
    """Compatibility: legacy routes expect detect_emotions()."""
    return analyze_emotions(text, user_ctx=user_ctx)


def top_emotions(text: str, k: int = 3, user_ctx: Optional[Dict] = None,
                 channels: Optional[List[str]] = None) -> List[Tuple[str, float]]:
    """Vozvraschaet top-k kanalov po intensivnosti (0..1)."""
    scores = analyze_emotions(text, user_ctx=user_ctx)
    if channels:
        scores = {c: scores.get(c, 0.0) for c in channels}
    # Usually felt boots are ok, but sometimes useful; leave it as is
    items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    k = max(1, min(int(k or 3), 20))
    return [(str(a), float(b)) for a, b in items[:k]]


def primary_emotion(text: str, user_ctx: Optional[Dict] = None) -> str:
    """Main emotion (from the basic set)."""
    base = ["anxiety", "interest", "joy", "sadness", "anger", "surprise", "disgust"]
    top = top_emotions(text, k=1, user_ctx=user_ctx, channels=base)
    return top[0][0] if top else "neutral"


class EmotionalAnalyzer:
    """Alias ​​for modules that expect a class object with the analyze_emotion() method."""
    def __init__(self, baseline: Optional[Dict[str, float]] = None):
        self._eng = EmotionalEngine(baseline=baseline)

    def analyze_emotion(self, text: str, user_ctx: Optional[Dict] = None) -> Dict[str, object]:
        scores = self._eng.analyze(text, user_ctx=user_ctx)
        emo = primary_emotion(text, user_ctx=user_ctx)
        return {"emotion": emo, "scores": scores}

__all__ = [
    "analyze_emotions",
    "EmotionalEngine",
    "detect_emotions",
    "top_emotions",
    "primary_emotion",
    "EmotionalAnalyzer",
]