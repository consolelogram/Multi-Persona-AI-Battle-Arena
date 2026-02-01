import redis
import sys
import json
import re
import numpy as np
from difflib import SequenceMatcher
from sentence_transformers import SentenceTransformer
from groq import Groq
from start import select_topic  # Importing your menu

# ==========================================
#              1. SETUP & INIT
# ==========================================

# PASTE YOUR KEY BELOW
API_KEY = "API KEY HERE"
client = Groq(api_key=API_KEY)
MODEL_ID = "llama-3.3-70b-versatile"

print("Loading Embedding Model...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

try:
    r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=False)
    r.ping()
except redis.ConnectionError:
    print("ERROR: Redis is not running.")
    sys.exit()

# ==========================================
#              2. HELPER FUNCTIONS
# ==========================================

def extract_json(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match: return json.loads(match.group())
        return json.loads(text)
    except:
        return None

def judge_debate(player_text, opponent_text):
    # Hard filter for nonsense/short inputs
    if len(player_text) < 5 or len(player_text.split()) < 2: 
        return 0, "Silence/Nonsense."

    JUDGE_PROMPT = """
    ROLE: Logic & Debate Referee.
    TASK: Analyze the Player's argument against the Opponent's previous line.
    
    SCORING RUBRIC:
    - "NONSENSE" (0 pts): Grammatically broken, irrelevant, or a typo.
    - "WEAK" (10 pts): Pure ad hominem, "No U", or subjective opinion without proof.
    - "VALID" (40 pts): A coherent point that addresses the opponent's argument.
    - "CRITICAL" (80 pts): Exposes a specific logical fallacy (Strawman, Circular Logic) or provides a counter-example.
    
    OUTPUT JSON ONLY: {"category": "NONSENSE"|"WEAK"|"VALID"|"CRITICAL", "reason": "short explanation"}
    """
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": f"Opponent: {opponent_text}\nPlayer: {player_text}"}
            ],
            response_format={"type": "json_object"}
        )
        data = extract_json(completion.choices[0].message.content)
        
        category = data.get('category', 'WEAK')
        points_map = {"NONSENSE": 0, "WEAK": 10, "VALID": 40, "CRITICAL": 80}
        
        return points_map.get(category, 10), data.get('reason', "No reasoning provided.")
    except Exception as e:
        print(f"Judge Error: {e}")
        return 0, "Judge Error"

# ==========================================
#              3. HOUSE GENERATION (GROQ)
# ==========================================

def generate_opening_statement(topic, house_stance, user_stance):
    print(f"   -> House is preparing his opening argument on '{topic}'...")
    
    prompt = f"""
    You are Dr. Gregory House.
    We are starting a debate.

    [SCENARIO]
    TOPIC: "{topic}"
    TRUTH: "{house_stance}"
    LIE: "{user_stance}"

    [INSTRUCTIONS]
    1. Dismantle the User's view ("{user_stance}") using logic, not name-calling.
    2. Assert your view ("{house_stance}") as the only rational conclusion.
    3. Use a metaphor about biology, physics, or medicine.
    4. **BE CONCISE.**

    [LENGTH CONSTRAINT]
    - MAXIMUM 3 SENTENCES.
    - MAXIMUM 50 WORDS.
    """
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.6, # Lower temp = more logical, less unhinged
            max_tokens=80
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"House is silent (API Error: {e})"

def generate_debate_reply(user_input, topic, house_stance, anchor):
    print(f"   -> House is formulating an argument...")
    
    prompt = f"""
    [ROLE]
    YOU are Dr. Gregory House.
    THE USER is a Patient with a flawed worldview.

    [SCENARIO]
    Topic: "{topic}"
    User's Argument: "{user_input}"
    YOUR Stance: "{house_stance}" (Defend this).
    Your Philosophy: "{anchor}"

    [CRITICAL RULES]
    1. ATTACK THE ARGUMENT, NOT THE PERSON.
    2. Do not use ad hominem attacks (e.g. "You are stupid").
    3. Instead, call the *idea* naive, dangerous, or a placebo.
    4. Identify the logical fallacy in the user's input.
    5. Keep it under 3 sentences.
    6. Tone: Clinical, cold, intellectually superior.
    """
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.6 # Lower temp keeps him focused on the argument
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"House is silent (API Error: {e})"

# ==========================================
#              4. MAIN GAME LOOP
# ==========================================

# 1. SETUP PHASE
topic, user_stance, house_stance = select_topic()

print(f"\nLocked In: You ({user_stance}) vs House ({house_stance})\n")

# 2. HOUSE OPENS
LAST_GHOST_LINE = generate_opening_statement(topic, house_stance, user_stance)
print(f"\n HOUSE: {LAST_GHOST_LINE}\n")

USER_HP = 350
GHOST_HP = 350

# 3. START LOOP
while USER_HP > 0 and GHOST_HP > 0:
    # A. INPUT
    user_query = input(f"[{USER_HP} HP] You: ").strip()
    if not user_query: break

# B. JUDGE PLAYER (Logic Mode)
    damage, reason = judge_debate(user_query, LAST_GHOST_LINE)
    
    actual_damage = int(damage * 0.75) # Your new 75% power

    if damage >= 20:
        # SUCCESSFUL HIT
        heal = int(actual_damage * 0.10)
        print(f"SMACK! -{actual_damage} HP ({reason})")
        print(f"+{heal} HP")
        GHOST_HP -= actual_damage
        USER_HP = min(350, USER_HP + heal) # Updated to your new 350 max
        
        # Game continues to Section C & D (House Reply) below...

    else:
        # FAILED HIT (Nonsense/Weak)
        print(f" BLOCKED! Weak argument ({damage} pts).")
        print(f" You take -5 HP.")
        USER_HP -= 5
        GHOST_HP = min(350, GHOST_HP + 5) # He heals a bit from your stupidity
        
        # HOUSE MOCKS YOU (No API call needed, just snark)
        import random
        snarks = [
            "I'm still waiting for an actual argument.",
            "Silence would have been smarter.",
            "Is that the best your brain can produce?",
            "Boring.",
            "You're wasting my time.",
            "Try again, but with logic this time."
        ]
        LAST_GHOST_LINE = random.choice(snarks)
        print(f"\n HOUSE: {LAST_GHOST_LINE}\n")
        
        # CRITICAL: Restart loop immediately. 
        # Prevents him from debating "nothing" and dealing 32 damage.
        continue

    # C. RETRIEVAL (Context)
    q_vec = embed_model.encode(user_query).astype(np.float32).tobytes()
    anchor = "The truth is a moving target." 
    try:
        res = r.execute_command("FT.SEARCH", "ghost_idx", "*=>[KNN 2 @embedding $vec AS vector_score]", "PARAMS", 2, "vec", q_vec, "RETURN", 1, "text", "DIALECT", 2)
        if res and len(res) > 1:
            candidate = res[2][1].decode("utf-8")
            if SequenceMatcher(None, user_query, candidate).ratio() < 0.6:
                anchor = candidate
    except: pass

    # D. HOUSE REPLY (Groq Logic)
    LAST_GHOST_LINE = generate_debate_reply(user_query, topic, house_stance, anchor)
    print(f"\n HOUSE [{GHOST_HP} HP]: {LAST_GHOST_LINE}\n")

    # E. HOUSE COUNTER-ATTACK
    enemy_dmg, _ = judge_debate(LAST_GHOST_LINE, user_query)
    
    if enemy_dmg > 20:
        ai_hit = int(enemy_dmg * 0.40)
        ai_heal = int(ai_hit * 0.3) 
        print(f"⚡ COUNTER! House hits -{ai_hit} HP! He heals +{ai_heal} HP.")
        USER_HP -= ai_hit
        GHOST_HP = min(100, GHOST_HP + ai_heal)
    
    if USER_HP <= 0:
        print("\n GAME OVER.")
        break
