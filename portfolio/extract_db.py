import zipfile
with zipfile.ZipFile('portfolio_deploy.zip', 'r') as z:
    z.extract('messages.db', path='temp_zip_db')
