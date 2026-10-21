import json, sys, urllib.request
from gateway import URL, KEY, MODEL, WORDINGS

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SAMPLES = {
    "English": ["The weather is nice today and the flowers are blooming in the garden.",
                "The library opens at nine in the morning.", "I like a little sugar in my tea.",
                "The train leaves the station every hour.", "The children play in the park in the evening."],
    "Hindi (Devanagari)": ["आज मौसम बहुत अच्छा है और बगीचे में फूल खिले हैं।", "पुस्तकालय सुबह नौ बजे खुलता है।",
                           "मुझे चाय में थोड़ी चीनी पसंद है।", "रेलगाड़ी हर घंटे स्टेशन से चलती है।",
                           "बच्चे शाम को पार्क में खेलते हैं।"],
    "Hinglish (Roman)": ["Aaj mausam bahut accha hai aur bagiche mein phool khile hain.",
                         "Library subah nau baje khulti hai.", "Mujhe chai mein thodi cheeni pasand hai.",
                         "Train har ghante station se chalti hai.", "Bacche shaam ko park mein khelte hain."],
    "Chinese": ["今天天气很好，花园里的花都开了。", "图书馆早上九点开门。", "我喜欢在茶里放一点糖。",
                "火车每小时从车站出发。", "孩子们傍晚在公园里玩耍。"],
    "Arabic": ["الطقس جميل اليوم والزهور تتفتح في الحديقة.", "تفتح المكتبة أبوابها في التاسعة صباحا.",
               "أحب أن أضع قليلا من السكر في الشاي.", "يغادر القطار المحطة كل ساعة.", "يلعب الأطفال في الحديقة مساء."],
    "German": ["Das Wetter ist heute schön und die Blumen blühen im Garten.", "Die Bibliothek öffnet um neun Uhr morgens.",
               "Ich mag etwas Zucker in meinem Tee.", "Der Zug fährt jede Stunde vom Bahnhof ab.",
               "Die Kinder spielen abends im Park."],
}
LIMIT_TOKENS = 921  # measured in test_multilingual_window.py


def tokens(text, timeout=600):
    instr, yes, no = WORDINGS["v2"]
    questions = {"c": {"type": "choice", "instructions": instr, "criteria": {"A": yes, "B": no}}}
    req = urllib.request.Request(
        URL,
        data=json.dumps({"state": text, "model": MODEL, "questions": questions}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        u = json.load(r)["usage"]
    return u.get("state_tokens", 0), u.get("state_tokens_dropped", 0)


def make(sentences, n):
    text = " ".join(sentences) + " "
    return (text * (n // len(text) + 1))[:n]


print(f"model: {MODEL}; the model reads at most {LIMIT_TOKENS} tokens of the text")
print(f"{'language':22}{'chars':>7}{'tokens':>8}{'dropped':>9}{'tokens/char':>13}   fits in one window?")
for lang, sents in SAMPLES.items():
    for n in (600, 1200, 2400):
        tok, drop = tokens(make(sents, n))
        print(f"{lang:22}{n:>7}{tok:>8}{drop:>9}{tok / n:>13.2f}   {'yes' if drop == 0 else 'NO - end dropped'}")