from flask import Flask, request
import stripe

app = Flask(_name_)

stripe.api_key = 'YOUR_STRIPE_API_KEY'

@app.route('/payment', methods=['POST'])
def payment():
    # Get the payment information from the request
    payment_info = request.form

    # Create a new Stripe customer
    customer = stripe.Customer.create(email=payment_info['email'])

    # Create a new Stripe payment method
    payment_method = stripe.PaymentMethod.create(
        type='card',
        card={
            'number': payment_info['card_number'],
            'exp_month': payment_info['exp_month'],
            'exp_year': payment_info['exp_year'],
            'cvc': payment_info['cvc']
        }
    )

    # Attach the payment method to the customer
    stripe.PaymentMethod.attach(
        payment_method.id,
        customer=customer.id
    )

    # Create a new Stripe subscription
    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[
            {'price': 'YOUR_STRIPE_PRICE_ID'}
        ]
    )

    return 'Payment successful!'