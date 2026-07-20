from django.shortcuts import render

def branches(request):
    return render(request, "branches/branches.html")

