from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from models import db, Category, Investment, AppData
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from math import pow
import json
import requests  # Add this import for backend API calls
import yfinance as yf  # Add this import for Yahoo Finance API
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
CORS(app)  # Enable CORS for all routes
db.init_app(app)

# Initialize database
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/view_data')
def view_data():
    categories = Category.query.all()
    return render_template('view_data.html', categories=categories)

@app.route('/save_data', methods=['POST'])
def save_data():
    data = request.json
    for cat_data in data['categories']:
        category_name = cat_data['name']
        duration = cat_data.get('duration', 0)
        return_rate = cat_data.get('return_rate', 0.0)
        category = Category.query.filter_by(name=category_name).first()
        if category is None:
            category = Category(name=category_name, duration=duration, return_rate=return_rate)
            db.session.add(category)
        else:
            category.duration = duration
            category.return_rate = return_rate
        db.session.flush()  # Ensure category.id is available
        for inv_data in cat_data.get('investments', []):
            family_member = inv_data['family_member']
            current_value = inv_data.get('current_value', 0)
            investment = Investment.query.filter_by(category_id=category.id, family_member=family_member).first()
            if investment is None:
                investment = Investment(category_id=category.id, family_member=family_member, current_value=current_value)
                db.session.add(investment)
            else:
                investment.current_value = current_value
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/get_data', methods=['GET'])
def get_data():
    categories = Category.query.all()
    data = []
    for category in categories:
        cat_data = {
            'name': category.name,
            'duration': category.duration,
            'return_rate': category.return_rate,
            'investments': [
                {
                    'family_member': inv.family_member,
                    'current_value': inv.current_value
                } for inv in category.investments
            ]
        }
        data.append(cat_data)
    return jsonify({'categories': data})

@app.route('/download_excel', methods=['GET'])
def download_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "Financial Data"

    headers = ["Category", "Duration (Years)", "Return Rate (%)", "Family Member", "Current Value (₹)"]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    categories = Category.query.all()
    for category in categories:
        for investment in category.investments:
            ws.append([
                category.name,
                category.duration,
                category.return_rate,
                investment.family_member,
                investment.current_value
            ])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2) * 1.2
        ws.column_dimensions[column].width = adjusted_width

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        download_name="financial_data.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/analytics', methods=['GET'])
def analytics():
    categories = Category.query.all()
    bar_labels = []
    bar_current = []
    bar_future = []
    pie_labels = []
    pie_data = []
    # Pie and bar chart data (only for investment categories)
    for category in categories:
        if category.investments:
            current_total = sum(inv.current_value for inv in category.investments)
            future_total = 0
            # Use category duration and return_rate for all investments in this category
            for inv in category.investments:
                future_total += inv.current_value * pow(1 + category.return_rate / 100, category.duration)
            if current_total > 0 or future_total > 0:
                bar_labels.append(category.name)
                bar_current.append(current_total)
                bar_future.append(future_total)
            if current_total > 0:
                pie_labels.append(category.name)
                pie_data.append(current_total)
    return jsonify({
        'bar': {
            'labels': bar_labels,
            'current': bar_current,
            'future': bar_future
        },
        'pie': {
            'labels': pie_labels,
            'data': pie_data
        }
    })

@app.route('/api/news')
def api_news():
    NEWS_API_KEY = '983f7bfd900040febf553b76cc54b585'  # <-- Your NewsAPI key
    url = f'https://newsapi.org/v2/top-headlines?language=en&apiKey={NEWS_API_KEY}'  # Global English news
    try:
        resp = requests.get(url, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/market-prices')
def api_market_prices():
    results = {}
    
    # NIFTY 50
    try:
        nifty_resp = requests.get('https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050', headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        }, timeout=10)
        nifty_data = nifty_resp.json()
        results['nifty'] = nifty_data['data'][0] if 'data' in nifty_data and nifty_data['data'] else None
    except Exception as e:
        results['nifty'] = {'error': str(e)}
    
    # Gold using Yahoo Finance
    try:
        gold_ticker = yf.Ticker("GC=F")  # Gold Futures
        gold_info = gold_ticker.info
        gold_price = gold_ticker.history(period="1d")
        
        if not gold_price.empty:
            current_price = gold_price['Close'].iloc[-1]
            results['gold'] = {
                'price': round(current_price, 2),
                'currency': 'USD',
                'symbol': 'GC=F',
                'name': 'Gold Futures',
                'change': round(gold_price['Close'].iloc[-1] - gold_price['Open'].iloc[0], 2) if len(gold_price) > 0 else 0,
                'change_percent': round(((gold_price['Close'].iloc[-1] - gold_price['Open'].iloc[0]) / gold_price['Open'].iloc[0]) * 100, 2) if len(gold_price) > 0 else 0
            }
        else:
            results['gold'] = {'error': 'No data available'}
    except Exception as e:
        results['gold'] = {'error': str(e)}
    
    # Silver using Yahoo Finance
    try:
        silver_ticker = yf.Ticker("SI=F")  # Silver Futures
        silver_info = silver_ticker.info
        silver_price = silver_ticker.history(period="1d")
        
        if not silver_price.empty:
            current_price = silver_price['Close'].iloc[-1]
            results['silver'] = {
                'price': round(current_price, 2),
                'currency': 'USD',
                'symbol': 'SI=F',
                'name': 'Silver Futures',
                'change': round(silver_price['Close'].iloc[-1] - silver_price['Open'].iloc[0], 2) if len(silver_price) > 0 else 0,
                'change_percent': round(((silver_price['Close'].iloc[-1] - silver_price['Open'].iloc[0]) / silver_price['Open'].iloc[0]) * 100, 2) if len(silver_price) > 0 else 0
            }
        else:
            results['silver'] = {'error': 'No data available'}
    except Exception as e:
        results['silver'] = {'error': str(e)}
    
    return jsonify(results)

@app.route('/api/save_all', methods=['POST'])
def api_save_all():
    payload = request.json
    for key in ('categories', 'members', 'values'):
        if key in payload:
            record = AppData.query.filter_by(key=key).first()
            if record:
                record.data = json.dumps(payload[key])
            else:
                record = AppData(key=key, data=json.dumps(payload[key]))
                db.session.add(record)
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/load_all', methods=['GET'])
def api_load_all():
    result = {}
    for key in ('categories', 'members', 'values'):
        record = AppData.query.filter_by(key=key).first()
        if record:
            result[key] = json.loads(record.data)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)