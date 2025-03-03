import re
import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 's3cr3t'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração para upload de arquivos Excel (XLS/XLSX)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

db = SQLAlchemy(app)

# ----------------------------------------------------------------------------------
# MODELOS DO BANCO DE DADOS
# ----------------------------------------------------------------------------------

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    measurements = db.Column(db.Text, nullable=True)  # Texto original com todas as medições
    measurement_values = db.relationship('MeasurementValue', backref='product', lazy=True)

class MeasurementValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)

# ----------------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ----------------------------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_measurements(text):
    """
    Faz o parse do texto de medições e retorna um dicionário com chaves (categorias) e os valores numéricos.
    
    Exemplo de entrada:
    
      comprimento:
      
      77 cm
      busto:
      
      114 cm
      cintura:
      
      112 cm
      comprimento manga:
      
      68 cm
      cava:
      
      25 cm
    """
    lines = [line.strip() for line in text.splitlines() if line.strip() != '']
    result = {}
    key = None
    for line in lines:
        if line.endswith(':'):
            key = line[:-1].strip().lower()
        else:
            if key:
                match = re.search(r'(\d+[.,]?\d*)\s*cm', line)
                if match:
                    value = float(match.group(1).replace(',', '.'))
                    result[key] = value
                key = None
            else:
                if ':' in line:
                    parts = line.split(':')
                    cat = parts[0].strip().lower()
                    match = re.search(r'(\d+[.,]?\d*)\s*cm', parts[1])
                    if match:
                        value = float(match.group(1).replace(',', '.'))
                        result[cat] = value
    return result

# ----------------------------------------------------------------------------------
# ROTAS DA APLICAÇÃO
# ----------------------------------------------------------------------------------

@app.route('/')
def index():
    """Exibe a lista de produtos e as médias dos valores de cada medição."""
    from sqlalchemy import func
    products = Product.query.all()
    averages = db.session.query(MeasurementValue.category, func.avg(MeasurementValue.value)) \
                          .group_by(MeasurementValue.category).all()
    return render_template('index.html', products=products, averages=averages)

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    """Formulário para cadastro manual de um produto."""
    if request.method == 'POST':
        url = request.form.get('url')
        measurements_text = request.form.get('measurements')
        price_text = request.form.get('price')
        
        if not (url and measurements_text and price_text):
            flash("Todos os campos são obrigatórios.", "danger")
            return redirect(url_for('add_product'))

        match_price = re.search(r'R\$[\s]?([\d.,]+)', price_text)
        if match_price:
            num_str = match_price.group(1).replace('.', '').replace(',', '.')
            try:
                price = float(num_str)
            except ValueError:
                flash("Preço inválido.", "danger")
                return redirect(url_for('add_product'))
        else:
            flash("Formato de preço não reconhecido.", "danger")
            return redirect(url_for('add_product'))
        
        product = Product(url=url, price=price, measurements=measurements_text)
        db.session.add(product)
        db.session.commit()
        
        measurements_dict = parse_measurements(measurements_text)
        for category, value in measurements_dict.items():
            mv = MeasurementValue(product_id=product.id, category=category, value=value)
            db.session.add(mv)
        db.session.commit()
        
        flash("Produto adicionado com sucesso!", "success")
        return redirect(url_for('index'))
    
    return render_template('add_product.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_products():
    """
    Rota para upload de planilhas Excel (XLS/XLSX) contendo as colunas:
    'URL', 'Measurements' e 'Price'.
    """
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash("Nenhum arquivo enviado.", "danger")
            return redirect(request.url)
        file = request.files['excel_file']
        if file.filename == '':
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            try:
                df = pd.read_excel(filepath)
            except Exception as e:
                flash(f"Erro ao ler o arquivo Excel: {e}", "danger")
                return redirect(request.url)
            
            expected_columns = ['URL', 'Measurements', 'Price']
            for col in expected_columns:
                if col not in df.columns:
                    flash(f"A coluna '{col}' não foi encontrada no arquivo Excel.", "danger")
                    return redirect(request.url)
            
            count = 0
            for index, row in df.iterrows():
                url = row['URL']
                measurements_text = row['Measurements']
                price_text = row['Price']
                
                if not (pd.notnull(url) and pd.notnull(measurements_text) and pd.notnull(price_text)):
                    continue
                
                match_price = re.search(r'R\$[\s]?([\d.,]+)', str(price_text))
                if match_price:
                    num_str = match_price.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = float(num_str)
                    except ValueError:
                        continue
                else:
                    continue
                
                product = Product(url=url, price=price, measurements=measurements_text)
                db.session.add(product)
                db.session.commit()
    
                measurements_dict = parse_measurements(measurements_text)
                for category, value in measurements_dict.items():
                    mv = MeasurementValue(product_id=product.id, category=category, value=value)
                    db.session.add(mv)
                db.session.commit()
                count += 1
            
            flash(f"Importação concluída: {count} produtos importados.", "success")
            return redirect(url_for('index'))
        else:
            flash("Formato de arquivo não permitido. Somente arquivos .xls ou .xlsx.", "danger")
            return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/search_clothes', methods=['GET', 'POST'])
def search_clothes():
    """
    Página com formulário para informar as medidas utilizadas na busca.
    Realiza a filtragem dos produtos do banco considerando uma tolerância
    e pontuando os candidatos com base na proximidade das medições.
    """
    search_results = []
    user_input = {}
    field_mapping = {
        'aba': 'aba',
        'altura': 'altura',
        'boca': 'boca',
        'busto': 'busto',
        'cano': 'cano',
        'cava': 'cava',
        'cintura': 'cintura',
        'circunferencia': 'circunferência',
        'comprimento': 'comprimento',
        'comprimento_manga': 'comprimento manga',
        'comprimento_total': 'comprimento total',
        'entrepernas': 'entrepernas',
        'gancho': 'gancho',
        'punho': 'punho',
        'quadril': 'quadril',
        'salto': 'salto',
        'solado': 'solado'
    }
    tolerance = 5.0  # tolerância em centímetros

    if request.method == 'POST':
        for form_field, measure_key in field_mapping.items():
            value = request.form.get(form_field)
            if value:
                try:
                    user_input[measure_key] = float(value)
                except ValueError:
                    pass
        
        all_products = Product.query.all()
        candidates = []
        for product in all_products:
            product_measures = {m.category: m.value for m in product.measurement_values}
            fields_found = 0
            match_count = 0
            total_diff = 0.0
            matched_details = {}
            for key, user_val in user_input.items():
                if key in product_measures:
                    fields_found += 1
                    diff = abs(user_val - product_measures[key])
                    total_diff += diff
                    matched_details[key] = diff
                    if diff <= tolerance:
                        match_count += 1
            if fields_found > 0:
                avg_diff = total_diff / fields_found
                candidate = {
                    'product': product,
                    'fields_found': fields_found,
                    'match_count': match_count,
                    'avg_diff': avg_diff,
                    'matched_details': matched_details
                }
                candidates.append(candidate)
        # Ordena: maior número de campos compatíveis e, em caso de empate, menor diferença média
        candidates.sort(key=lambda x: (-x['match_count'], x['avg_diff']))
        search_results = [c for c in candidates if c['match_count'] > 0]
    
    return render_template('search_clothes.html', results=search_results, user_input=user_input, fields=field_mapping)

# ----------------------------------------------------------------------------------
# EXECUÇÃO DA APLICAÇÃO
# ----------------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
