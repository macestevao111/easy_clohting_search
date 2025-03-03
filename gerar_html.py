from flask import render_template
from app import app, db, Product, MeasurementValue  # Certifique-se de importar todas as classes necessárias
from sqlalchemy import func

with app.app_context():
    # Utilize um contexto de requisição de teste para habilitar o uso de url_for no template
    with app.test_request_context():
        products = Product.query.all()
        averages = db.session.query(
            MeasurementValue.category, func.avg(MeasurementValue.value)
        ).group_by(MeasurementValue.category).all()

        html_content = render_template('index.html', products=products, averages=averages)

        with open('static_output.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

print("Arquivo static_output.html gerado com sucesso!")
