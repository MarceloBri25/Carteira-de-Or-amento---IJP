from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.simple_tag
def render_comanda(pedido_json):
    if not pedido_json:
        return ""

    try:
        data = json.loads(pedido_json) if isinstance(pedido_json, str) else pedido_json
    except (json.JSONDecodeError, TypeError):
        return mark_safe('<p class="text-danger">Erro ao ler o pedido.</p>')

    if not data:
        return ""

    html = '<ul class="list-group list-group-flush comanda-list">'

    # NEW format: A list of dictionaries, e.g., [{"item": "Agua", "quantity": 1}]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                # Handles both {'item':...} and {'name':...} structures
                item_name = item.get('item') or item.get('name')
                quantity = item.get('quantity', 1)
                if item_name:
                    html += f'<li class="list-group-item d-flex justify-content-between align-items-center bg-transparent border-bottom px-0">{item_name} <span class="badge bg-secondary rounded-pill">{quantity}</span></li>'
                else:
                    # Fallback for unexpected dict structure in list
                    html += f'<li>DEBUG: Dicionário em formato inesperado: {str(item)}</li>'
            else:
                # Fallback for unexpected item type in list
                html += f'<li>DEBUG: Item inesperado na lista: {str(item)}</li>'

    # OLD format: A dictionary of lists, e.g., {"Bebidas": ["Agua", "Coca"]}
    elif isinstance(data, dict):
        for category, items in data.items():
            if isinstance(items, list):
                for item_name in items:
                    # Old format has no quantity, so assume 1
                    html += f'<li class="list-group-item d-flex justify-content-between align-items-center bg-transparent border-bottom px-0">{item_name} <span class="badge bg-secondary rounded-pill">1</span></li>'
            else:
                # Fallback for unexpected value in dict
                html += f'<li>DEBUG: Valor inesperado para a chave "{category}": {str(items)}</li>'
                
    else:
        # Fallback for any other format
        html += f'<li>DEBUG: Formato de dados não reconhecido: {type(data).__name__}</li>'


    html += '</ul>'
    return mark_safe(html)