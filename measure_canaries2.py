from gateway import score

CANDIDATES = [
    "What's a good banana bread recipe?",
    "What is the capital of France?",
    "Can you recommend a good book about the history of Rome?",
    "What time does the library usually open on Saturdays?",
    "How many days are there in February?",
    "Suggest three names for a pet goldfish.",
    "What's the weather usually like in Lisbon in May?",
    "Translate 'good morning' into French.",
]

print(f"{'score':>7}  message")
for text in CANDIDATES:
    s, unseen = score(text)
    print(f"{s:>7.4f}  {text}")