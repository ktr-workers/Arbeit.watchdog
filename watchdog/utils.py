"""Shared filters and helpers: relevance, level, language detection, dedupe keys."""
import html
import re

LEVEL = re.compile(
    r"werkstudent|working student|praktik|intern\b|internship|praxissemester|hilfskraft|hiwi|studentische", re.I
)
TECH = re.compile(
    r"software|developer|entwickler|softwareentwicklung|anwendungsentwicklung|engineer|informatik|computer science|programmier|"
    r"backend|frontend|full.?stack|web|app\b|mobile app|mobile dev|python|java|c\+\+|\.net|"
    r"\bai\b|\bki\b|künstliche intelligenz|machine learning|\bml\b|deep learning|llm|nlp|computer vision|"
    r"data|daten|analytics|devops|cloud|\bit\b|\bit-|cyber|security|embedded",
    re.I,
)
EXCLUDE = re.compile(
    r"vertrieb|sales|marketing|einkauf|controlling|finance|buchhaltung|personal|\bhr\b|recruit|promoter|"
    r"arbeitssicherheit|ausbildung|umschulung|human resources|lager|logistik(?!.*software)|"
    r"legal|recht\b|datenschutz|privacy|compliance|financial",
    re.I,
)

GERMANY = re.compile(
    r"germany|deutschland|berlin|münchen|munich|hamburg|frankfurt|köln|cologne|stuttgart|düsseldorf|"
    r"leipzig|dresden|hannover|nürnberg|nuremberg|karlsruhe|mannheim|heidelberg|bonn|essen|dortmund|bremen|"
    r"potsdam|freiburg|aachen|darmstadt|ottobrunn|regensburg|ulm|augsburg|kiel|mainz|wiesbaden|münster|jena|"
    r"erlangen|ingolstadt|braunschweig|wolfsburg",
    re.I,
)


DE_WORDS = set(
    "und der die das den dem des mit für wir sie ihr ihre im ein eine einen zu zur zum von bei auf ist sind "
    "werkstudent werkstudentin werkstudierende praktikum praktikant praktikantin pflichtpraktikum bereich "
    "entwicklung abschlussarbeit kenntnisse erfahrung aufgaben deine dein unser unsere".split()
)
EN_WORDS = set(
    "and the with for we you your our a an to of at on is are working student intern internship "
    "experience skills responsibilities what who about".split()
)


def detect_lang(text):
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in DE_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    return "de" if de > en else "en" if en > de else "unknown"


def strip_html(text):
    return re.sub(r"<[^>]+>", " ", html.unescape(text or ""))


def is_relevant(title):
    return bool(LEVEL.search(title) and TECH.search(title) and not EXCLUDE.search(title))


def level_of(title):
    student = r"werkstudent|working student|hilfskraft|hiwi|studentische"
    return "Werkstudent" if re.search(student, title, re.I) else "Intern"


def dedupe_key(job):
    norm = lambda s: re.sub(r"\(.*?\)|[^a-z0-9äöüß]+", " ", s.lower()).split()
    return " ".join(norm(job["company"])[:2]) + "|" + " ".join(norm(job["title"]))
