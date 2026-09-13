import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')
django.setup()

from django.conf import settings
from app1.crud import get_payzen_auth_header
import requests, json
import uuid

headers = get_payzen_auth_header()
order_id = "TEST-" + uuid.uuid4().hex[:10]

payload1 = {
    "amount": 1000,
    "currency": "ARS",
    "orderId": order_id,
    "channelOptions": {"channelType": "URL"},
    "paymentMethodTypes": ["NARANJA"]
}
r1 = requests.post(settings.PAYZEN_URL, json=payload1, headers=headers)
print("payload1 (paymentMethodTypes):", r1.json())

order_id = "TEST-" + uuid.uuid4().hex[:10]
payload2 = {
    "amount": 1000,
    "currency": "ARS",
    "orderId": order_id,
    "channelOptions": {"channelType": "URL"},
    "paymentCards": "NARANJA"
}
r2 = requests.post(settings.PAYZEN_URL, json=payload2, headers=headers)
print("payload2 (paymentCards):", r2.json())

