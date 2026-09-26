from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/detect', methods=['POST'])
def detect():
    # Get the input file from the request
    input_file = request.files['fileInput']

    # Send the input file to your AI LLM service
    files = {'input_file': input_file}
    response = requests.post(
        'https://detection.odoo.com/',
        files=files
    )

    # Return the response from your AI LLM service
    return jsonify({'response': response.json()})

@app.route('/upload', methods=['POST'])
def upload():
    # Get the input file from the request
    input_file = request.files['fileInput']

    # Check file extension
    file_name = input_file.filename
    file_extension = file_name.split('.').pop().lower()
    if file_extension not in ['jpg', 'jpeg', 'png', 'gif']:
        return jsonify({'error': 'Only JPG, JPEG, PNG, or GIF image files are allowed.'})

    # Simulate a 2-second detection process
    import time
    time.sleep(2)

    # Return a random detection result
    import random
    result = 'Authentic' if random.random() >= 0.5 else 'Deepfake'
    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(debug=True)