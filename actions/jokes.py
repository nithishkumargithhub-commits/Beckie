import random

JOKES_LIST = [
    "Why do programmers wear glasses? Because they can't C sharp.",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem.",
    "There are 10 types of people in the world: those who understand binary, and those who don't.",
    "What is a programmer's favorite place to hang out? Foo Bar.",
    "Why did the programmer quit their job? Because they didn't get arrays.",
    "A SQL query walks into a bar, walks up to two tables and asks, 'Can I join you?'",
    "How do you comfort a JavaScript bug? You console it.",
    "Why did the database administrator leave his wife? She had one-to-many relationships.",
    "What do you call a developer who doesn't comment code? A developer.",
    "Why was the computer cold? It left its Windows open.",
    "What is a computer's favorite beat? An algo-rhythm.",
    "How does a programmer open a jar? They read the documentation.",
    "What's a database's favorite song? 'Drop it like it's hot'.",
    "Why did the developer go broke? Because they used up all their cache.",
    "Why was the robot tired? It had a hard drive."
]

def get_random_joke() -> str:
    return random.choice(JOKES_LIST)
