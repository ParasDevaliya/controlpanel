from django.shortcuts import render
from django.http import JsonResponse
import json
from .git_handler import handle_git_clone_and_docker
from django.views.decorators.csrf import csrf_exempt

def home(request):
    return render(request, 'index.html')

@csrf_exempt
def git(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    try:
        print("called from ipless react router app")
        data = json.loads(request.body)
        result, status = handle_git_clone_and_docker(data)
        return JsonResponse(result, status=status)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Unexpected error', 'details': str(e)}, status=500)
