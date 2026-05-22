import zipfile
with zipfile.ZipFile('portfolio_deploy.zip', 'r') as z:
    for name in z.namelist():
        print(name)
