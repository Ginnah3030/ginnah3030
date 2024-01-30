from flask import Flask, render_template, request, jsonify
from twilio.rest import Client
from flask_sqlalchemy import SQLAlchemy
import threading
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Meter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meter_number = db.Column(db.String(255), unique=True, nullable=False)
    remaining_kilowatts = db.Column(db.Float, default=0.0)

with app.app_context():
    db.create_all()

# Twilio credentials
account_sid = 'AC2c5e4a95e86bd5353f511d31c5015c6e'
auth_token = 'c0af8d875d15e3bb7b9a744a3f0d1107'
twilio_phone_number = '+12293982236'
client = Client(account_sid, auth_token)

def send_confirmation_sms(user_phone_number, meter_number, amount=None):
    try:
        if amount is not None:
            message_body = f"Token purchase for {meter_number} is successful. You've bought {amount} kilowatts. Thank you!"
        else:
            message_body = f"Token purchase for {meter_number} is successful. Thank you!"

        message = client.messages.create(
            body=message_body,
            from_=twilio_phone_number,
            to=user_phone_number
        )

        print(f"SMS sent successfully. SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False




def update_remaining_kilowatts(meter_number, amount):
    with app.app_context():
        meter = Meter.query.filter_by(meter_number=meter_number).first()
        if meter:
            meter.remaining_kilowatts += amount
            db.session.commit()

def send_low_balance_notification(meter_number):
    # Replace 'your_phone_number' with your actual phone number
    user_phone_number = '+263715512554'

    # Send a notification about low balance
    send_confirmation_sms(user_phone_number, meter_number)
    print(f"Low balance notification sent for {meter_number}.")

def deduct_kilowatts_periodically(meter_number):
    while True:
        try:
            time.sleep(2)
            with app.app_context():
                meter = Meter.query.filter_by(meter_number=meter_number).first()
                if meter:
                    print(f"Meter found: {meter}")
                    if meter.remaining_kilowatts is not None:
                        print(f"Remaining kilowatts before deduction: {meter.remaining_kilowatts}")
                        try:
                            if meter.remaining_kilowatts >= 5:
                                meter.remaining_kilowatts = max(0, meter.remaining_kilowatts - 5)
                                db.session.commit()
                                print(f"Deducted 5 kilowatts from {meter_number}. Remaining: {meter.remaining_kilowatts}")
                                if meter.remaining_kilowatts <= 20.0:
                                    send_low_balance_notification(meter_number)
                            else:
                                print(f"Insufficient balance. Stopping deductions.")
                                break
                        except Exception as inner_exception:
                            print(f"Exception during deduction: {inner_exception}")
                    else:
                        print("Meter remaining_kilowatts is None. Setting it to 0.")
                        meter.remaining_kilowatts = 0
                        db.session.commit()
                else:
                    print(f"Meter {meter_number} not found. Stopping deductions.")
                    break
        except Exception as e:
            print(f"Exception in deduct_kilowatts_periodically: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/purchase', methods=['POST'])
def purchase():
    meter_number = request.form['meter_number']
    user_phone_number = request.form['phone']
    amount = float(request.form['amount'])

    # Create the meter in the database if it doesn't exist
    with app.app_context():
        meter = Meter.query.filter_by(meter_number=meter_number).first()
        if not meter:
            meter = Meter(meter_number=meter_number)
            db.session.add(meter)
            db.session.commit()

    # Update the remaining kilowatts
    update_remaining_kilowatts(meter_number, amount)

    # Send confirmation SMS
    if send_confirmation_sms(user_phone_number, meter_number):
        return render_template('index.html', success_message=f"Recharge for {meter_number} is successful")
    else:
        return render_template('index.html', error_message="Failed to send SMS")

@app.route('/retrieve')
def retrieve():
    return render_template('retrieve.html')

@app.route('/get-remaining-kilowatts/<meter_number>')
def get_remaining_kilowatts_endpoint(meter_number):
    with app.app_context():
        meter = Meter.query.filter_by(meter_number=meter_number).first()
        if meter:
            remaining_kilowatts = meter.remaining_kilowatts
        else:
            remaining_kilowatts = None
    return jsonify({'remaining_kilowatts': remaining_kilowatts})

if __name__ == '__main__':
    meter_numbers = ['112233445566', '223344556677','123456789101112','000000000000']
    deduction_threads = [threading.Thread(target=deduct_kilowatts_periodically, args=(meter_number,))
                         for meter_number in meter_numbers]

    for thread in deduction_threads:
        thread.start()

    app.run(debug=True)
