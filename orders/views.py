from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.conf import settings
from carts.models import CartItem
from store.models import Product
from .forms import OrderForm
from .models import Order, OrderProduct, Payment
import datetime
from .transbank_utils import create_transaction, commit_transaction
from django.template.loader import render_to_string

def payments(request):
    return render(request, 'orders/payments.html')

def place_order(request):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()

    if cart_count <= 0:
        return redirect('store')

    total = sum(cart_item.product.price * cart_item.quantity for cart_item in cart_items)
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)

        if form.is_valid():
            data = form.save(commit=False)
            data.user = current_user
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            current_date = datetime.datetime.now().strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)

            # Llamar a Transbank para crear la transacción
            response = create_transaction(
                buy_order=order_number,
                session_id=str(order.id),
                amount=grand_total,
                return_url=settings.TRANSBANK_RETURN_URL  # Usar la URL de retorno desde la configuración
            )

            if 'token' in response and 'url' in response:
                # Redirigir al usuario a la URL de Transbank para completar el pago
                transbank_url = response['url'] + '?token_ws=' + response['token']
                return redirect(transbank_url)
            else:
                # Manejo de errores
                context = {
                    'order': order,
                    'cart_items': cart_items,
                    'total': total,
                    'tax': tax,
                    'grand_total': grand_total,
                    'error': 'Error al crear la transacción con Transbank. Intente nuevamente.'
                }
                return render(request, 'orders/payments.html', context)
        else:
            return redirect('checkout')
    else:
        return redirect('checkout')
    
def payment_return(request):
    token = request.GET.get('token_ws')

    if token:
        # Confirmar la transacción con Transbank
        response = commit_transaction(token)
        
        if response.get('status') == 'AUTHORIZED':
            order_number = response.get('buy_order')
            order = Order.objects.get(order_number=order_number)
            order.is_ordered = True
            order.save()

            # Registrar el pago en la base de datos
            payment = Payment(
                user=order.user,
                payment_id=token,
                payment_method='Webpay',
                amount_id=str(order.order_total),  # Cambiado a amount_id como un string
                status=response.get('status')
            )
            payment.save()

            # Mover todos los carrito items hacia la tabla order product
            cart_items = CartItem.objects.filter(user=order.user)
            for item in cart_items:
                orderproduct = OrderProduct()
                orderproduct.order_id = order.id
                orderproduct.payment = payment
                orderproduct.user_id = request.user.id
                orderproduct.product_id = item.product_id
                orderproduct.quantity = item.quantity
                orderproduct.product_price = item.product.price
                orderproduct.ordered = True
                orderproduct.save()

                cart_item = CartItem.objects.get(id=item.id)
                product_variation = cart_item.variations.all()
                orderproduct = OrderProduct.objects.get(id=orderproduct.id)
                orderproduct.variation.set(product_variation)
                orderproduct.save()

                product = Product.objects.get(id=item.product_id)
                product.stock -= item.quantity
                product.save()

            CartItem.objects.filter(user=order.user).delete()

            # Enviar correo electrónico de confirmación
            mail_subject = 'Gracias por tu compra'
            body = render_to_string('orders/order_recieved_email.html', {
                'user': order.user,
                'order': order,
            })
            to_email = order.user.email
            send_email = EmailMessage(mail_subject, body, to=[to_email])
            send_email.send()
            
            # Obtener la información necesaria para mostrar en la página de éxito de pago
            ordered_products = OrderProduct.objects.filter(order_id=order.id)

            subtotal = 0
            for i in ordered_products:
                subtotal += i.product_price * i.quantity

            context = {
                'order': order,
                'ordered_products': ordered_products,
                'order_number': order.order_number,
                'transID': payment.payment_id,
                'payment': payment,
                'subtotal': subtotal,
                'message': 'Su pago fue exitoso. Gracias por su compra.'
            }
            return render(request, 'orders/payment_success.html', context)
        else:
            context = {
                'message': 'Hubo un problema con su pago. Por favor, intente nuevamente.'
            }
            return render(request, 'orders/payment_failure.html', context)
    else:
        return redirect('store')
