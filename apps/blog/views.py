from django.shortcuts import render

def blog(request):
    return render(request, "blog/blog.html")

def article(request):
    return render(request, "blog/article.html")

