import requests
from django.conf import settings

def create_transaction(buy_order, session_id, amount, return_url):
    headers = {
        "Content-Type": "application/json",
        "Tbk-Api-Key-Id": settings.TRANSBANK_API_KEY_ID,
        "Tbk-Api-Key-Secret": settings.TRANSBANK_API_KEY_SECRET,
    }
    
    payload = {
        "buy_order": buy_order,
        "session_id": session_id,
        "amount": amount,
        "return_url": return_url
    }
    
    response = requests.post(
        settings.TRANSBANK_API_URL + "/rswebpaytransaction/api/webpay/v1.2/transactions",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Error al crear la transacción con Transbank."}
    
def commit_transaction(token):
    headers = {
        "Content-Type": "application/json",
        "Tbk-Api-Key-Id": settings.TRANSBANK_API_KEY_ID,
        "Tbk-Api-Key-Secret": settings.TRANSBANK_API_KEY_SECRET,
    }
    
    response = requests.put(
        f"{settings.TRANSBANK_API_URL}/rswebpaytransaction/api/webpay/v1.2/transactions/{token}",
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Error al confirmar la transacción con Transbank."}

