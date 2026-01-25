import redis
import requests
import sys
import json
import re
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq

try:
    r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=False)
    r.ping()
except redis.ConnectionError:
    print("ERROR: Redis is not running. Start it with 'redis-server'.")
    sys.exit()
API_KEY = "YOUR_GROQ_API_KEY" 
client = Groq(api_key=API_KEY)

JUDGE_MODEL_ID = "llama-3.3-70b-versatile"

embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def extract_json(text):
    #Finds JSON in the AI's response even if it chatters.
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match: return json.loads(match.group())
        return json.loads(text)
    except:
        return None

def judge_roast(player_text, last_opponent_line, opponent_name, opponent_weakness):
    cleaned = player_text.strip()
    if not cleaned or len(cleaned) < 3: return 0, "Silence is weak."

    JUDGE_PROMPT = """
    ROLE: Roast Battle Judge.
    TASK: Score the Player's insult (0-100).
    
    SCORING GUIDE:
    - 0-20: Weak/Lazy.
    - 21-50: Solid/Witty.
    - 51-100: Critical/Savage (Psychological damage).

    OUTPUT JSON ONLY: {"damage": int, "reason": "string"}
    """
    
    print(f"Judging...")
    try:
        completion = client.chat.completions.create(
            model=JUDGE_MODEL_ID,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": f"Context: {last_opponent_line}\nInput: {cleaned}"}
            ],
            response_format={"type": "json_object"}
        )
        
        data = extract_json(completion.choices[0].message.content)
        if data:
            return int(data.get('damage', 0)), data.get('reason', ".")
        return 15, "Judge glitch"
            
    except Exception:
        return 0, "Judge Dead"

def pick_best_reply(reply_a, reply_b, context):
    if len(reply_a) < 5: return reply_b
    if len(reply_b) < 5: return reply_a
    try:
        completion = client.chat.completions.create(
            model=JUDGE_MODEL_ID,
            messages=[
                {"role": "system", "content": "Pick the ruder/wittier reply. JSON: {best_index: 0 or 1}"},
                {"role": "user", "content": f"Context: {context}\n\nOpt 0: {reply_a}\nOpt 1: {reply_b}"}
            ],
            response_format={"type": "json_object"}
        )
        data = extract_json(completion.choices[0].message.content)
        idx = data.get("best_index", 0) if data else 0
        return reply_a if idx == 0 else reply_b
    except:
        return reply_a 

# ==========================================
#              3. GENERATION
# ==========================================

def call_ollama(model_name, prompt):
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 60, "stop": ["User:", "Ghost:"]}
            }
        )
        if res.status_code == 200:
            return res.json()["response"].replace("Ghost:", "").replace("Dr. House:", "").strip()
    except:
        pass
    return "..."

def generate_ensemble_reply(prompt):
    print("   -> House is thinking...")
    rude_prompt = prompt + " Be sarcastic, arrogant, and rude. Do not apologize."
    
    reply_qwen = call_ollama("qwen2.5:1.5b", rude_prompt)
    reply_phi = call_ollama("phi3", rude_prompt) 

    return pick_best_reply(reply_qwen, reply_phi, prompt)

# ==========================================
#              4. MAIN GAME LOOP
# ==========================================

USER_HP = 100
GHOST_HP = 100
LAST_GHOST_LINE = "I'm Dr. House. You look like you're about to say something stupid."

print(f"\n👻 HOUSE: {LAST_GHOST_LINE}\n")

while USER_HP > 0 and GHOST_HP > 0:
    # 1. INPUT
    user_query = input(f"[{USER_HP} HP] You: ").strip()
    if not user_query: break

    # 2. JUDGE PLAYER
    damage, reason = judge_roast(user_query, LAST_GHOST_LINE, "Dr. House", "Ego")
    
    # --- BALANCE FIX: 20% NERF (Multiplier 0.8) ---
    actual_damage = int(damage * 0.8)

    # Threshold Check (Still 20 to pass)
    if damage >= 20:
        heal = int(actual_damage * 0.10) # 10% Vampirism on ACTUAL damage
        print(f"💥 SMACK! -{actual_damage} HP ({reason})")
        print(f"🩸 +{heal} HP")
        
        GHOST_HP -= actual_damage
        USER_HP = min(100, USER_HP + heal)
    else:
        # Punishment
        print(f"🛡️ BLOCKED! Weak roast ({damage} pts).")
        print(f"💔 You take -5 HP.")
        USER_HP -= 5
        GHOST_HP = min(100, GHOST_HP + 2)

    if GHOST_HP <= 0: break
    if USER_HP <= 0: break

    # 3. RETRIEVAL
    q_vec = embed_model.encode(user_query).astype(np.float32).tobytes()
    anchor = "You are boring me."
    try:
        res = r.execute_command("FT.SEARCH", "ghost_idx", "*=>[KNN 30 @embedding $vec AS vector_score]", "PARAMS", 2, "vec", q_vec, "RETURN", 2, "text", "vector_score", "DIALECT", 2)
        valid_anchors = [res[i+1][1].decode("utf-8") for i in range(1, len(res), 2) if len(res[i+1][1]) > 15]
        if valid_anchors: anchor = valid_anchors[0]
    except: pass

    # 4. HOUSE REPLY
    prompt = f"Roleplay Dr. House. Reply to '{user_query}'. Style: '{anchor}'."
    LAST_GHOST_LINE = generate_ensemble_reply(prompt)
    
    print(f"\n👻 HOUSE [{GHOST_HP} HP]: {LAST_GHOST_LINE}\n")

    # 5. HOUSE COUNTER-ATTACK
    enemy_dmg, _ = judge_roast(LAST_GHOST_LINE, user_query, "Player", "Ego")
    
    if enemy_dmg > 25:
        # House hits you for 20% of the Judge's score
        ai_hit = int(enemy_dmg * 0.20)
        
        # House heals 50% of what he hits you for
        ai_heal = int(ai_hit * 0.5) 

        print(f"⚡ COUNTER! House hits -{ai_hit} HP! He heals +{ai_heal} HP.")
        
        USER_HP -= ai_hit
        GHOST_HP = min(100, GHOST_HP + ai_heal)
    
    if USER_HP <= 0:
        print("\n💀 GAME OVER.")
        break