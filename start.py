# start_screen.py

# Format: "Topic Name", "Option A (Pro)", "Option B (Against)"
TOPICS = [
    ("Is Venom a Villain?", "Villain", "Anti-Hero"),
    ("Does the End Justify the Means?", "Yes, results matter", "No, morals matter"),
    ("Is Lying Necessary?", "Yes, it lubricates society", "No, truth is absolute"),
    ("Is Batman a Hero?", "Hero", "Mentally ill Vigilante"),
    ("Is Altruism Real?", "Yes, people are good", "No, everyone is selfish")
]

def select_topic():
    print("\n==========================================")
    print("      DR. HOUSE: THE LOGIC BATTLES")
    print("==========================================\n")
    
    option_index = 1
    selection_map = {}

    for i, (topic, side_a, side_b) in enumerate(TOPICS):
        # Option A (User picks Side A)
        print(f"{option_index}. [Topic: {topic}]") 
        print(f"   ↳ You argue: {side_a} (House argues: {side_b})")
        selection_map[option_index] = (topic, side_a, side_b) 
        option_index += 1
        
        # Option B (User picks Side B)
        print(f"{option_index}. [Topic: {topic}]")
        print(f"   ↳ You argue: {side_b} (House argues: {side_a})")
        selection_map[option_index] = (topic, side_b, side_a) 
        option_index += 1
        print("-" * 40)

    while True:
        choice = input("\nChoose a number to start debate: ").strip()
        if choice.isdigit() and int(choice) in selection_map:
            return selection_map[int(choice)]
        print("Invalid choice. Try again.")