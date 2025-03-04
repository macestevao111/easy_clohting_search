import re
import os
import pandas as pd
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Configuração de logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    gender = db.Column(db.String(10), nullable=False)  # 'M' para masculino, 'F' para feminino
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
    logger.debug(f"Iniciando parse de medidas. Texto recebido: {text}")
    lines = [line.strip() for line in text.splitlines() if line.strip() != '']
    result = {}
    key = None
    for line in lines:
        if line.endswith(':'):
            key = line[:-1].strip().lower()
            logger.debug(f"Categoria encontrada: {key}")
        else:
            if key:
                match = re.search(r'(\d+[.,]?\d*)\s*cm', line)
                if match:
                    value = float(match.group(1).replace(',', '.'))
                    result[key] = value
                    logger.debug(f"Valor encontrado para {key}: {value}")
                key = None
            else:
                if ':' in line:
                    parts = line.split(':')
                    cat = parts[0].strip().lower()
                    match = re.search(r'(\d+[.,]?\d*)\s*cm', parts[1])
                    if match:
                        value = float(match.group(1).replace(',', '.'))
                        result[cat] = value
                        logger.debug(f"Valor encontrado para {cat}: {value}")
    logger.debug(f"Resultado final do parse: {result}")
    return result

# ----------------------------------------------------------------------------------
# ROTAS DA APLICAÇÃO
# ----------------------------------------------------------------------------------

@app.route('/')
def index():
    """Exibe a lista de produtos e as médias dos valores de cada medição."""
    return render_template('index.html')

@app.route('/masculino')
def masculino():
    """Exibe a lista de produtos masculinos e suas médias."""
    from sqlalchemy import func
    products = Product.query.filter_by(gender='M').all()
    averages = db.session.query(
        MeasurementValue.category, 
        func.avg(MeasurementValue.value)
    ).join(Product).filter(
        Product.gender == 'M'
    ).group_by(MeasurementValue.category).all()
    return render_template('products.html', 
                         products=products, 
                         averages=averages, 
                         gender='masculino')

@app.route('/feminino')
def feminino():
    """Exibe a lista de produtos femininos e suas médias."""
    from sqlalchemy import func
    products = Product.query.filter_by(gender='F').all()
    averages = db.session.query(
        MeasurementValue.category, 
        func.avg(MeasurementValue.value)
    ).join(Product).filter(
        Product.gender == 'F'
    ).group_by(MeasurementValue.category).all()
    return render_template('products.html', 
                         products=products, 
                         averages=averages, 
                         gender='feminino')

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    """Formulário para cadastro manual de um produto."""
    if request.method == 'POST':
        url = request.form.get('url')
        measurements_text = request.form.get('measurements')
        price_text = request.form.get('price')
        gender = request.form.get('gender')
        
        logger.debug(f"Tentando adicionar produto - URL: {url}")
        logger.debug(f"Medidas recebidas: {measurements_text}")
        logger.debug(f"Preço recebido: {price_text}")
        logger.debug(f"Gênero: {gender}")
        
        if not (url and measurements_text and price_text and gender):
            logger.warning("Campos obrigatórios faltando")
            flash("Todos os campos são obrigatórios.", "danger")
            return redirect(url_for('add_product'))

        if gender not in ['M', 'F']:
            logger.warning(f"Gênero inválido: {gender}")
            flash("Gênero inválido.", "danger")
            return redirect(url_for('add_product'))

        match_price = re.search(r'R\$[\s]?([\d.,]+)', price_text)
        if match_price:
            num_str = match_price.group(1).replace('.', '').replace(',', '.')
            try:
                price = float(num_str)
                logger.debug(f"Preço convertido com sucesso: {price}")
            except ValueError:
                logger.error(f"Erro ao converter preço: {num_str}")
                flash("Preço inválido.", "danger")
                return redirect(url_for('add_product'))
        else:
            logger.warning(f"Formato de preço não reconhecido: {price_text}")
            flash("Formato de preço não reconhecido.", "danger")
            return redirect(url_for('add_product'))
        
        try:
            product = Product(url=url, price=price, measurements=measurements_text, gender=gender)
            db.session.add(product)
            db.session.commit()
            logger.info(f"Produto base criado com ID: {product.id}")
            
            measurements_dict = parse_measurements(measurements_text)
            logger.debug(f"Medidas parseadas: {measurements_dict}")
            
            for category, value in measurements_dict.items():
                mv = MeasurementValue(product_id=product.id, category=category, value=value)
                db.session.add(mv)
            db.session.commit()
            logger.info("Medidas salvas com sucesso")
            
            flash("Produto adicionado com sucesso!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Erro ao salvar produto: {str(e)}")
            db.session.rollback()
            flash("Erro ao salvar produto.", "danger")
            return redirect(url_for('add_product'))
    
    return render_template('add_product.html')

@app.route('/upload_products', methods=['GET', 'POST'])
def upload_products():
    if request.method == 'POST':
        logger.debug("Iniciando processo de upload")
        
        # Verificar se foi selecionado um gênero
        gender = request.form.get('gender')
        if not gender:
            logger.warning("Gênero não selecionado")
            flash("Por favor, selecione o gênero dos produtos.", "danger")
            return redirect(request.url)
        
        if gender not in ['M', 'F']:
            logger.warning(f"Gênero inválido: {gender}")
            flash("Gênero inválido.", "danger")
            return redirect(request.url)
        
        # Verificar se foram enviados arquivos
        if 'excel_files' not in request.files:
            logger.warning("Nenhum arquivo enviado")
            flash("Nenhum arquivo enviado.", "danger")
            return redirect(request.url)
        
        files = request.files.getlist('excel_files')
        if not files or files[0].filename == '':
            logger.warning("Nenhum arquivo selecionado")
            flash("Nenhum arquivo selecionado.", "danger")
            return redirect(request.url)
        
        total_count = 0
        total_errors = 0
        processed_files = 0
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                logger.debug(f"Salvando arquivo: {filepath}")
                file.save(filepath)
                
                try:
                    logger.debug(f"Tentando ler arquivo Excel: {filename}")
                    df = pd.read_excel(filepath)
                    logger.debug(f"Colunas encontradas: {df.columns.tolist()}")
                except Exception as e:
                    logger.error(f"Erro ao ler arquivo Excel {filename}: {str(e)}")
                    flash(f"Erro ao ler o arquivo {filename}: {e}", "danger")
                    continue
                
                expected_columns = ['URL', 'Measurements', 'Price']
                missing_columns = [col for col in expected_columns if col not in df.columns]
                if missing_columns:
                    logger.error(f"Colunas ausentes em {filename}: {missing_columns}")
                    flash(f"As seguintes colunas não foram encontradas em {filename}: {', '.join(missing_columns)}", "danger")
                    continue
                
                count = 0
                errors = 0
                
                for index, row in df.iterrows():
                    try:
                        logger.debug(f"Processando linha {index + 1} do arquivo {filename}")
                        url = row['URL']
                        measurements_text = row['Measurements']
                        price_text = row['Price']
                        
                        if not (pd.notnull(url) and pd.notnull(measurements_text) and pd.notnull(price_text)):
                            logger.warning(f"Dados incompletos na linha {index + 1} do arquivo {filename}")
                            errors += 1
                            continue
                        
                        match_price = re.search(r'R\$[\s]?([\d.,]+)', str(price_text))
                        if match_price:
                            num_str = match_price.group(1).replace('.', '').replace(',', '.')
                            try:
                                price = float(num_str)
                                logger.debug(f"Preço convertido: {price}")
                            except ValueError:
                                logger.warning(f"Erro ao converter preço na linha {index + 1} do arquivo {filename}")
                                errors += 1
                                continue
                        else:
                            logger.warning(f"Formato de preço inválido na linha {index + 1} do arquivo {filename}")
                            errors += 1
                            continue
                        
                        product = Product(url=url, price=price, measurements=measurements_text, gender=gender)
                        db.session.add(product)
                        db.session.commit()
                        
                        measurements_dict = parse_measurements(measurements_text)
                        for category, value in measurements_dict.items():
                            mv = MeasurementValue(product_id=product.id, category=category, value=value)
                            db.session.add(mv)
                        db.session.commit()
                        count += 1
                        logger.info(f"Produto {count} importado com sucesso do arquivo {filename}")
                    except Exception as e:
                        logger.error(f"Erro ao processar linha {index + 1} do arquivo {filename}: {str(e)}")
                        errors += 1
                        db.session.rollback()
                        continue
                
                total_count += count
                total_errors += errors
                processed_files += 1
                
                logger.info(f"Arquivo {filename} processado: {count} produtos importados, {errors} erros")
            else:
                logger.warning(f"Formato de arquivo não permitido: {file.filename}")
                flash(f"Arquivo {file.filename} ignorado: formato não permitido. Use apenas .xls ou .xlsx.", "warning")
        
        if processed_files > 0:
            logger.info(f"Importação finalizada: {total_count} produtos importados, {total_errors} erros em {processed_files} arquivos")
            flash(f"Importação concluída: {total_count} produtos importados, {total_errors} erros em {processed_files} arquivos.", 
                  "success" if total_count > 0 else "warning")
        else:
            flash("Nenhum arquivo foi processado com sucesso.", "danger")
        
        return redirect(url_for('index'))
    
    return render_template('upload.html')

@app.route('/search_clothes', methods=['GET', 'POST'])
def search_clothes():
    search_results = []
    user_input = {}
    gender = request.args.get('gender', 'M')  # Default para masculino se não especificado
    
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
    tolerance = 5.0

    if request.method == 'POST':
        gender = request.form.get('gender', 'M')
        logger.debug(f"Iniciando busca de roupas - Gênero: {gender}")
        
        for form_field, measure_key in field_mapping.items():
            value = request.form.get(form_field)
            if value:
                try:
                    user_input[measure_key] = float(value)
                except ValueError:
                    logger.warning(f"Valor inválido para {measure_key}: {value}")
                    continue
        
        logger.debug(f"Medidas informadas: {user_input}")
        
        all_products = Product.query.filter_by(gender=gender).all()
        logger.debug(f"Total de produtos para análise: {len(all_products)}")
        
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
                logger.debug(f"Produto {product.id} - Matches: {match_count}/{fields_found}, Diff média: {avg_diff:.2f}")
        
        candidates.sort(key=lambda x: (-x['match_count'], x['avg_diff']))
        search_results = [c for c in candidates if c['match_count'] > 0]
        logger.info(f"Busca finalizada: {len(search_results)} resultados encontrados")
    
    return render_template('search_clothes.html', 
                         results=search_results, 
                         user_input=user_input, 
                         fields=field_mapping,
                         gender=gender)

# ----------------------------------------------------------------------------------
# EXECUÇÃO DA APLICAÇÃO
# ----------------------------------------------------------------------------------

# Garantir que o banco de dados seja criado/atualizado antes de iniciar a aplicação
def init_db():
    with app.app_context():
        # Isso vai dropar todas as tabelas existentes e recriar
        db.drop_all()
        db.create_all()
        
        # Verificar se as tabelas foram criadas corretamente
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f"Tabelas no banco de dados: {tables}")
        
        # Verificar as colunas da tabela Product
        columns = [col['name'] for col in inspector.get_columns('product')]
        logger.info(f"Colunas na tabela Product: {columns}")

if __name__ == '__main__':
    # Inicializar o banco de dados
    init_db()
    
    # Iniciar a aplicação
    app.run(debug=True)
