import requests
from bs4 import BeautifulSoup

import pandas as pd

# Define the URL for Amazon product listings (example)
url = 'https://www.amazon.com/gp/bestsellers/'

def fetch_amazon_products():
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Example: Extracting products
        products = []
        for item in soup.find_all('div', class_='a-section a-spacing-small'):
            title = item.find('span', class_='a-size-medium').text.strip()
            price = item.find('span', class_='a-offscreen').text.strip()

            # Additional attributes can be extracted as needed
            products.append({
                'title': title,
                'price': price
            })
        
        df = pd.DataFrame(products)
        print(df)
        df.to_csv('amazon_products.csv', index=False)
    else:
        print(f'Failed to fetch data. Status code: {response.status_code}')