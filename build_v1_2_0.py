import subprocess
import os
import shutil

def build():
    version = "1.2.0"
    print(f"--- Building Cafe POS v{version} ---")
    
    # Ensure dist folder is clean
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Use the venv's pyinstaller if available
    pyinstaller_path = os.path.join(".venv", "Scripts", "pyinstaller.exe")
    if not os.path.exists(pyinstaller_path):
        pyinstaller_path = "pyinstaller" # Fallback to system path

    cmd = [
        pyinstaller_path,
        "--noconsole",
        "--onefile",
        "--name", f"CafePOS_v{version}",
        "--clean",
        "--add-data", "app/database/schema.sql;app/database",
        "--add-data", "app_logo_circular.png;.",
        "--add-data", "app_icon.ico;app/ui",
        "--icon", "app_icon.ico",
        "main.py"
    ]
    
    try:
        print("Running PyInstaller...")
        subprocess.check_call(cmd)
        
        # Copy data folder to dist for testing
        if os.path.exists("data"):
            print("Copying data folder to dist...")
            # If dist/data exists, remove it first to ensure a clean copy
            target_data = os.path.join("dist", "data")
            if os.path.exists(target_data):
                shutil.rmtree(target_data)
            shutil.copytree("data", target_data)
            
        print("\n--- Build Successful! ---")
        print(f"Executable is located in: {os.path.join(os.getcwd(), 'dist')}")
    except Exception as e:
        print(f"Build failed: {e}")

if __name__ == "__main__":
    build()
