from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ativa o fuso horário para a requisição.
        # O ideal é que esta informação venha do perfil de cada usuário.
        # Para esta correção, estamos usando 'America/Manaus' como padrão.
        if request.user.is_authenticated:
            timezone.activate('America/Manaus')
        else:
            timezone.deactivate()
        
        response = self.get_response(request)
        return response
