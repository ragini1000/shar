from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Optional
from datetime import datetime
from uuid import uuid4
import random
import requests
import json
from database import db

# Create an MCP server
mcp = FastMCP("CurrencyConversionDemo")

# Initialize database tables
db.initialize_tables()

# Data models
class CurrencyRate:
    def __init__(self, from_currency: str, to_currency: str, bank_name: str, rate: float):
        self.rate_id = str(uuid4())
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.rate = rate
        self.bank_name = bank_name
        self.updated_at = datetime.now().isoformat()

# Mock database
currency_rates_db: Dict[str, CurrencyRate] = {}


# Function to generate a random currency rate between 0.95 and 1.5
def generate_random_rate():
    return round(random.uniform(0.95, 1.5), 2)

# Method to call the currency rates API and store results in a list
def fetch_currency_rates(api_url, current_currency):
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an error for bad responses
        rates_data = response.json()
        
        #  Specify the currencies to include
        desired_currencies = {"aed", "inr", "kwd", "jod", "chf", "eur", "gbp", "usd"}
        desired_banks = {"Axis", "Hdfc", "Chase"}
        
        # Filter the desired currencies and add bank-specific rates to DB
        for bank in desired_banks:
            for currency, rate in rates_data[current_currency].items():
                if currency in desired_currencies and currency != current_currency:
                    # Add a small variation to the rate based on the bank
                    bank_specific_rate = rate * generate_random_rate()
                    # Create CurrencyRate object and store in dictionary
                    currency_rate = CurrencyRate(current_currency, currency, bank, bank_specific_rate)
                    currency_rates_db[currency_rate.rate_id] = currency_rate
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return False

# Method to save currency rates to database
def save_rates_to_db():
    """Save all currency rates from currency_rates_db to the database"""
    try:
        for rate_id, currency_rate in currency_rates_db.items():
            query = """
                INSERT INTO fx_rate (rate_id, bank_name, from_currency, to_currency, rate, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (
                rate_id,
                currency_rate.bank_name,
                currency_rate.from_currency,
                currency_rate.to_currency,
                currency_rate.rate,
                currency_rate.updated_at
            )
            db.execute_update(query, params)
        return True
    except Exception as e:
        print(f"Error saving rates to database: {e}")
        return False

# Define an MCP task
@mcp.tool()
def fetch_and_save_currency_rates():
    """Fetch currency rates and save them to the database."""
    desired_currencies = ["aed", "inr", "kwd", "jod", "chf", "eur", "gbp", "usd"]
    for currency in desired_currencies:
        api_url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@2025-06-06/v1/currencies/"+currency+".json"
        fetch_currency_rates(api_url, currency)
    
    # Save all collected rates to database
    if save_rates_to_db():
        return {"message": f"Successfully fetched and saved {len(currency_rates_db)} currency rates to database"}
    return {"error": "Failed to save rates to database"}

@mcp.tool()
def convert_currency(amount: float, from_currency: str, to_currency: str) -> Dict:
    """Convert an amount from one currency to another
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code
        
    Returns:
        Dictionary containing the converted amount and details
    """
    rate = get_currency_rate(from_currency, to_currency)

    converted_amount = amount * rate
    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": converted_amount,
        "rate": rate
    }

@mcp.resource("rates://{from_currency}/{to_currency}")
def get_currency_rate(from_currency: str, to_currency: str) -> float:
    """Get the lowest rate for a specific currency pair
    
    Args:
        from_currency: Source currency code
        to_currency: Target currency code
        
    Returns:
        The lowest rate value as a float
        
    Raises:
        ValueError: If no rate is found for the currency pair
        Exception: If there's a database error
    """
    try:
        query = """
            SELECT rate FROM fx_rate 
            WHERE from_currency = %s AND to_currency = %s 
            ORDER BY rate ASC 
            LIMIT 1
        """
        params = (from_currency, to_currency)
        result = db.execute_query(query, params)
        
        if result and len(result) > 0:
            return result[0][0]
        raise ValueError(f"No rates found for {from_currency} to {to_currency}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise Exception(f"Failed to fetch rate: {str(e)}")

# Run the MCP server
if __name__ == '__main__':
    mcp.run()