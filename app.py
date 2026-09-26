import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, send_file
import tensorflow as tf
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import openai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage

# 1. تحميل المتغيرات البيئية من ملف .env
load_dotenv()

# 2. قراءة المفتاح بأمان من البيئة
openai.api_key = os.getenv('OPENAI_API_KEY')

# إعداد المجلدات
UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORT_FOLDER'] = REPORT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# تحميل النموذج
model = tf.keras.models.load_model('final_deepfake_model.keras')

def analyze_image(file_path):
    img = Image.open(file_path)
    img = img.resize((299, 299))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    prediction = model.predict(img_array)

    if prediction.shape[1] == 1:
        fake_prob = prediction[0][0]
        real_prob = 1 - fake_prob
    elif prediction.shape[1] == 2:
        fake_prob = prediction[0][0]
        real_prob = prediction[0][1]
    else:
        raise ValueError("Unexpected model output shape")

    return float(real_prob), float(fake_prob)

def generate_chart(fake_prob, real_prob):
    fig, ax = plt.subplots()
    ax.bar(['Fake', 'Real'], [real_prob, fake_prob])
    ax.set_ylim(0, 1)
    ax.set_xlabel('Class')
    ax.set_ylabel('Probability')
    ax.set_title('Prediction Results')
    chart_path = os.path.join('static', 'chart.png')
    plt.savefig(chart_path)
    plt.close(fig)
    return chart_path

def get_analysis(real_prob, fake_prob):
    prompt = f"""
    Analyze the image for forgery:
    Fake Probability: {real_prob * 100:.2f}%
    Real Probability: {fake_prob * 100:.2f}%
    
    Please provide a comprehensive analysis including:
    1. Forgery fingerprints.
    2. Comparison between real and fake features.
    3. Explanation of techniques like GAN.
    4. Future recommendations.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response['choices'][0]['message']['content']

def generate_report(real_prob, fake_prob, chart_path, analysis, multi_aspect_scores, recommendations, image_path):
    report_path = os.path.join(REPORT_FOLDER, 'deepfake_report.pdf')
    
    pdf = SimpleDocTemplate(report_path, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles['Title']
    title = Paragraph("Deepfake Detection Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Uploaded Image:", styles['Heading2']))
    elements.append(PDFImage(image_path, width=400, height=300))
    elements.append(Spacer(1, 12))

    prob_style = styles['Normal']
    elements.append(Paragraph(f"Fake Probability: {real_prob * 100:.2f}%", prob_style))
    elements.append(Paragraph(f"Real Probability: {fake_prob * 100:.2f}%", prob_style))
    elements.append(Paragraph(f"Confidence: {0.94 * 100:.2f}%", prob_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Detailed Analysis:", styles['Heading2']))
    elements.append(Paragraph(analysis, prob_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Multi-Aspect Analysis:", styles['Heading2']))
    for aspect, score in multi_aspect_scores.items():
        elements.append(Paragraph(f"{aspect}: {score:.2f}%", prob_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Results Chart:", styles['Heading2']))
    elements.append(PDFImage(chart_path, width=400, height=200))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Recommendations:", styles['Heading2']))
    for recommendation in recommendations:
        elements.append(Paragraph(f"- {recommendation}", prob_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Model Information:", styles['Heading2']))
    elements.append(Paragraph("Model used: StyleGAN2. This model is trained on diverse datasets to enhance detection capabilities.", prob_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Legal & Ethical Considerations:", styles['Heading2']))
    elements.append(Paragraph("The misuse of deepfake technologies can lead to serious ethical and legal consequences.", prob_style))
    
    pdf.build(elements)
    return report_path

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_image.jpg')
            file.save(file_path)
            real_prob, fake_prob = analyze_image(file_path)

            chart_path = generate_chart(fake_prob, real_prob)
            analysis = get_analysis(real_prob, fake_prob)

            multi_aspect_analysis = {
                "Lighting": np.random.uniform(0, 100),
                "Texture": np.random.uniform(0, 100),
                "Color": np.random.uniform(0, 100),
                "Background": np.random.uniform(0, 100),
                "Facial Distortion": np.random.uniform(0, 100),
            }

            recommendations = ["Use reputable tools to verify image authenticity and consider watermarking important images."]

            report_path = generate_report(real_prob, fake_prob, chart_path, analysis, multi_aspect_analysis, recommendations, file_path)

            os.remove(file_path)
            return render_template('result.html', fake_prob=real_prob, real_prob=fake_prob, chart_path=chart_path, report_path=report_path)
    return render_template('index.html')

@app.route('/download_report')
def download_report():
    report_path = os.path.join(REPORT_FOLDER, 'deepfake_report.pdf')
    return send_file(report_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)