import pandas as pd
import os
import matplotlib
matplotlib.use('Agg') 

from matplotlib import pyplot as plt

def generate_reports(csv_path):
    # load data sets from csvpath
    try:
        data_file = pd.read_csv(csv_path)

        if data_file.empty:
            print("ERROR: CSV_FILE EMPTY")
            return 
    except FileNotFoundError:
        print(f"CRITICAL ERROR: FILE NOT FOUND '{csv_path}'.")
        return
    except Exception as e:
        print(f"UNEXPECTED ERROR WHILE READING FILE: {e}")
        return
    
    # preprocesing -> erase '%' adn replace N/A with 0
    data_file['Coverage_Num'] = data_file['Coverage'].astype(str).str.replace('%','')
    data_file['Coverage_Num'] = pd.to_numeric(data_file['Coverage_Num'], errors='coerce').fillna(0)

    # create director for visual results
    output_dir = "../results/plots"
    os.makedirs(output_dir, exist_ok=True)

    try:
        plt.style.use('ggplot') 
    except:
        pass

    # plotting COVERAGE EVOLUTION
    plt.figure(figsize=(10, 5))
    plt.plot(data_file['Iteration'], data_file['Coverage_Num'], marker='s', markersize=8, linestyle='-', color='#2c3e50', linewidth=2, label='Current Coverage')

    #plotting target line
    plt.axhline(y=90, color='#e74c3c', linestyle='--', label='Target Goal (90%)')

    plt.title('Functional Coverage Progress', fontsize=14, fontweight='bold')
    plt.xlabel('Iteration Number', fontsize=12)
    plt.ylabel('Coverage (%)', fontsize=12)
    plt.ylim(0, 105) 
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(f"{output_dir}/1_coverage_evolution.png", dpi=300)
    plt.close()
            
    # plotting TIME EVOLUTION
    plt.figure(figsize=(10, 5))
    plt.bar(data_file['Iteration'].astype(str), data_file['Time_Execution_sec'], color='#3498db', alpha=0.8)
    
    plt.title('Execution Time per Iteration', fontsize=14, fontweight='bold')
    plt.xlabel('Iteratie', fontsize=12)
    plt.ylabel('Sec(s)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.savefig(f"{output_dir}/3_timing_analysis.png", dpi=300)
    plt.close()
    
    print(f"GRAPHICS SAVED IN: {os.path.abspath(output_dir)}")

if __name__ == "__main__":
    FILE_PATH = "../results/experimental_metrics_FIFO2.csv"
    generate_reports(FILE_PATH)