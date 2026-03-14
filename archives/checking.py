import sys
import os

def check_dependencies():
    packages = [
        "langgraph", 
        "langchain", 
        "llama_index", 
        "dotenv"
    ]
    
    print(f"--- Verificare Dependențe (Python {sys.version.split()}) ---")
    missing =[] 
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"✅ {pkg}: Instalat")
        except ImportError:
            print(f"❌ {pkg}: LIPSEȘTE")
            missing.append(pkg)
            
    if missing:
        print(f"\nInstalează-le folosind:\npip install {' '.join(missing)}")
    else:
        print("\n🚀 Totul este pregătit pentru partea de AI!")

if __name__ == "__main__":
    check_dependencies()