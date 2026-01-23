# pip install numpy scipy matplotlib

import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import chisquare

def analyze_dice_distribution(rolls, die_name="Unknown Die", show_graph=True):
    n = len(rolls)
    if n < 6: return None

    counts = np.bincount(rolls, minlength=7)[1:]
    _, p = chisquare(counts)
    confidence = (1 - p) * 100
    evenchance = p * 100
    one_in_x = round(1 / p) if p > 0 else "never"
    
    if not show_graph:
        return confidence

    print(f"--- Analysis for {die_name} ---")
    analysis_msg = (
        f"Chance the die is not balanced (unbalanced if >95%): {confidence:.2f}%\n"
        f"Chance the die is too balanced (fake if >95%): {evenchance:.2f}%\n"
        f"A perfect die should have this or worse deviations, roughly one in {one_in_x} games"
    )
    print(analysis_msg)
    
    rel = "High" if n >= 300 else "Medium" if n >= 60 else "Low"
    verdict = "LIKELY BIASED" if confidence > 95 else "SUSPICIOUS" if confidence > 80 else "LIKELY BALANCED"
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(range(1, 7), counts, color='#3498db', edgecolor='#2c3e50')
    plt.axhline(y=n/6, color='#e74c3c', linestyle='--', label='Expected (Fair)')
    
    plt.suptitle(f"{die_name}: {verdict}", fontsize=16, fontweight='bold', color='red' if confidence > 95 else 'black')
    plt.title(analysis_msg, fontsize=12)
    
    stats_box = f"N: {n}\nReliability: {rel}\nConfidence: {confidence:.1f}%"
    plt.gca().text(0.95, 0.05, stats_box, transform=plt.gca().transAxes, 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
                   ha='right', va='bottom')
    
    plt.xlabel("Die Face")
    plt.ylabel("Frequency")
    plt.xticks(range(1, 7))
    plt.legend(loc='upper left')
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.1, int(yval), ha='center', fontweight='bold')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(f"analysis_{die_name.replace(' ', '_')}.png")
    plt.show()
    return confidence

def analyze_from_string(data_string):
    non_digits = [d for d in data_string if d not in "123456"]
    if non_digits:
        raise Exception(f"got non-d6 digits:{",".join(non_digits)}")
    rolls = [int(d) for d in data_string if d in "123456"]
    name = data_string[:4] if len(data_string) >= 4 else data_string
    return analyze_dice_distribution(rolls, die_name=name)

def run_fairness_simulation(iterations=1000, rolls_per_test=300, threshold=95.0):
    results = [analyze_dice_distribution(np.random.randint(1, 7, rolls_per_test), show_graph=False) for _ in range(iterations)]
    fps = sum(1 for thr in results if thr >= threshold)
    overfits = sum(1 for thr in results if thr <= 100-threshold)
    print("--------------------------------------")
    print(f"--- Fairness FP Simulation Results ({iterations} tests, {rolls_per_test} rolls) ---")
    print(f"False Positives at {threshold}%: {fps} ({(fps/iterations)*100:.2f}%)")
    print(f"Fake/overfit results (too good to be true) at {100-threshold}%: {overfits} ({(overfits/iterations)*100:.2f}%)")
    print(f"Expected Rate: {100-threshold:.2f}%")
    print("--------------------------------------")

if __name__ == "__main__":
    run_fairness_simulation()
    if len(sys.argv) > 1:
        analyze_from_string(sys.argv[1])
    else:
        print("Usage: python dice_analyzer.py <rolls_string like 4612232142526>")