#// LORA VARIANTS
#// create all variants of lora strength of prompt , keep under a maximum 
#//===========================================================================================
import re
import itertools
from tkinter import *

# GLOBAL VARIABLES
STRENGTH_TOTAL = 1.0  # 2.0
STRENGTH_MAX_INDIVIDUAL = 0.7  # 1.0


def extract_loras(text):
    # Extracts all LORAs from the text
    lora_pattern = r"<lora:([^:>]+):([\d\.]+)>"
    loras_extracted = re.findall(lora_pattern, text)
    return loras_extracted



def generate_strength_combinations(num_loras, strength_max, max_individual):
    # Generates all possible combinations of LORA strengths
    strength_steps = [i * 0.1 for i in range(int(max_individual * 10) + 1)]
    all_combinations = itertools.product(strength_steps, repeat=num_loras)

    valid_combinations = []
    for combo in all_combinations:
        if sum(combo) < strength_max:
            valid_combinations.append(combo)

    return valid_combinations


def replace_lora_strength(text, lora_name, new_strength):
    # Replaces a single LORA's strength in the text
    lora_to_replace = f"<lora:{lora_name}:[\\d\\.]+>"
    new_lora_tag = f"<lora:{lora_name}:{new_strength:.1f}>"
    return re.sub(lora_to_replace, new_lora_tag, text, count=1)


def create_permutations(text, loras, combinations):
    # Create permutations of the text with each combination of strengths
    permutations = []
    for combo in combinations:
        modified_text = text
        for lora_info, strength in zip(loras, combo):
            lora_name = lora_info[0]
            modified_text = replace_lora_strength(modified_text, lora_name, strength)
        permutations.append(modified_text)

    return permutations


def lora_variants(text, strength_max, max_individual):
    loras = extract_loras(text)  # Extract LORAs
    print(loras)
    combinations = generate_strength_combinations(len(loras), strength_max, max_individual)  # Generate strength combinations
    final_permutations = create_permutations(text, loras, combinations)  # Create permutations

    return final_permutations



# Tkinter UI setup
root = Tk()
root.title("LORA Variants Generator")
root.configure(bg="#333333")

label_style = {"bg": "#333333", "fg": "#ffffff"}
entry_style = {"bg": "#555555", "fg": "#ffffff", "insertbackground": "#ffffff"}
button_style = {"bg": "#555555", "fg": "#ffffff", "activebackground": "#777777"}

label1 = Label(root, text="Enter text with LORA tags:", **label_style)
label1.pack()

text_entry = Text(root, width=50, height=10, **entry_style)
text_entry.pack()

label2 = Label(root, text="Total Strength:", **label_style)
label2.pack()

total_strength_entry = Entry(root, width=10, **entry_style)
total_strength_entry.insert(0, STRENGTH_TOTAL)
total_strength_entry.pack()

label3 = Label(root, text="Max Individual Strength:", **label_style)
label3.pack()

max_individual_strength_entry = Entry(root, width=10, **entry_style)
max_individual_strength_entry.insert(0, STRENGTH_MAX_INDIVIDUAL)
max_individual_strength_entry.pack()


def generate_variants():
    input_text = text_entry.get("1.0", END)
    print("INPUT TEXT = " + str(input_text))
    total_strength = float(total_strength_entry.get())
    max_individual_strength = float(max_individual_strength_entry.get())

    permutations = lora_variants(input_text, total_strength, max_individual_strength)

    text_output = open("lora_variants.txt", "w")

    for perm in permutations:
        text_output.write(str(perm))
        text_output.write("\n")

    text_output.close()
    print("COMPLETED = Saved permutations to lora_variants.txt ")


generate_button = Button(root, text="Generate Variants", command=generate_variants, **button_style)
generate_button.pack()

root.mainloop()

