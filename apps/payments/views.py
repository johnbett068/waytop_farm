from django.shortcuts import render

def payment(request):
    return render(request, "payments/payment.html")

