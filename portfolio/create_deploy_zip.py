import zipfile
import os

zip_name = 'portfolio_deploy.zip'
files_to_include = [
    'app.py',
    'requirements.txt',
    'messages.db',
    'static',
    'templates'
]

with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
    for item in files_to_include:
        if os.path.isfile(item):
            z.write(item)
            print(f"Added file: {item}")
        elif os.path.isdir(item):
            for root, dirs, files in os.walk(item):
                for file in files:
                    file_path = os.path.join(root, file)
                    z.write(file_path)
                    print(f"Added file from dir: {file_path}")

print(f"\nSuccessfully created {zip_name}")
