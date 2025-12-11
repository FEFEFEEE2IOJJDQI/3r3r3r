"""
Flask Web App
Веб-интерфейс для просмотра заказов
"""
import asyncio
import asyncpg
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

from config import DATABASE_URL, FLASK_PORT, LOG_LEVEL, APP_TIMEZONE

# Настройка логирования
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

try:
    LOCAL_TZ = ZoneInfo(APP_TIMEZONE)
except ZoneInfoNotFoundError:
    LOCAL_TZ = ZoneInfo("UTC")
UTC_TZ = ZoneInfo("UTC")

async def get_db_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route('/')
def index():
    return redirect(url_for('orders_page'))

@app.route('/orders')
def orders_page():
    """Страница ленты заказов для Telegram Mini App"""
    return render_template('orders.html')

@app.route('/api/orders')
def get_orders():
    user_id = request.args.get('user_id')
    
    async def fetch_orders():
        pool = await get_db_pool()
        try:
            async with pool.acquire() as conn:
                if user_id:
                    orders = await conn.fetch('''
                        SELECT 
                            o.order_id,
                            o.customer_id,
                            o.price,
                            o.start_time,
                            o.address,
                            o.workers_count,
                            o.comment,
                            o.status,
                            o.created_at,
                            o.phone_number,
                            u.username as customer_username,
                            u.first_name as customer_name,
                            COALESCE(cp.rating, 0) as customer_rating,
                            COALESCE(cp.total_orders, 0) as customer_total_orders
                        FROM orders o
                        LEFT JOIN users u ON o.customer_id = u.user_id
                        LEFT JOIN customer_profiles cp ON o.customer_id = cp.user_id
                        WHERE o.status = 'open' 
                        AND o.is_deleted = FALSE
                        AND o.order_id NOT IN (SELECT order_id FROM hidden_orders WHERE user_id = $1)
                        ORDER BY o.created_at DESC
                        LIMIT 50
                    ''', int(user_id))
                else:
                    orders = await conn.fetch('''
                        SELECT 
                            o.order_id,
                            o.customer_id,
                            o.price,
                            o.start_time,
                            o.address,
                            o.workers_count,
                            o.comment,
                            o.status,
                            o.created_at,
                            o.phone_number,
                            u.username as customer_username,
                            u.first_name as customer_name,
                            COALESCE(cp.rating, 0) as customer_rating,
                            COALESCE(cp.total_orders, 0) as customer_total_orders
                        FROM orders o
                        LEFT JOIN users u ON o.customer_id = u.user_id
                        LEFT JOIN customer_profiles cp ON o.customer_id = cp.user_id
                        WHERE o.status = 'open' 
                        AND o.is_deleted = FALSE
                        ORDER BY o.created_at DESC
                        LIMIT 50
                    ''')
        finally:
            await pool.close()
        return [dict(o) for o in orders]
    
    try:
        orders = run_async(fetch_orders())
        for order in orders:
            created_at = order.get('created_at')
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC_TZ)
                order['created_at'] = created_at.astimezone(LOCAL_TZ).isoformat()
            order['price'] = float(order['price']) if order['price'] else 0
            order['customer_rating'] = float(order['customer_rating']) if order['customer_rating'] else 0
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reviews/<int:user_id>')
def get_reviews(user_id):
    async def fetch_reviews():
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            reviews = await conn.fetch('''
                SELECT 
                    r.rating,
                    r.comment,
                    r.created_at,
                    u.username as reviewer_username,
                    u.first_name as reviewer_name
                FROM reviews r
                LEFT JOIN users u ON r.reviewer_id = u.user_id
                WHERE r.reviewee_id = $1
                ORDER BY r.created_at DESC
                LIMIT 20
            ''', user_id)
            
            avg_rating = await conn.fetchval('''
                SELECT COALESCE(AVG(rating), 0) FROM reviews WHERE reviewee_id = $1
            ''', user_id)
            
            total_reviews = await conn.fetchval('''
                SELECT COUNT(*) FROM reviews WHERE reviewee_id = $1
            ''', user_id)
            
            user = await conn.fetchrow('''
                SELECT username, first_name FROM users WHERE user_id = $1
            ''', user_id)
        await pool.close()
        return reviews, avg_rating, total_reviews, user
    
    try:
        reviews, avg_rating, total_reviews, user = run_async(fetch_reviews())
        reviews_list = []
        for r in reviews:
            review_dict = dict(r)
            if review_dict.get('created_at'):
                review_dict['created_at'] = review_dict['created_at'].isoformat()
            reviews_list.append(review_dict)
        
        return jsonify({
            'success': True,
            'reviews': reviews_list,
            'avg_rating': float(avg_rating) if avg_rating else 0,
            'total_reviews': total_reviews,
            'user': dict(user) if user else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/respond', methods=['POST'])
def respond_to_order():
    data = request.json
    order_id = data.get('order_id')
    executor_id = data.get('executor_id')
    
    if not order_id or not executor_id:
        return jsonify({'success': False, 'error': 'Missing order_id or executor_id'}), 400
    
    async def create_response():
        pool = await get_db_pool()
        result = (False, 'unknown')
        try:
            async with pool.acquire() as conn:
                existing = await conn.fetchval('''
                    SELECT response_id FROM responses 
                    WHERE order_id = $1 AND executor_id = $2
                ''', order_id, executor_id)
                
                if existing:
                    result = (False, 'already_responded')
                else:
                    await conn.execute('''
                        INSERT INTO responses (order_id, executor_id, message)
                        VALUES ($1, $2, 'Отклик через мини-приложение')
                    ''', order_id, executor_id)
                    result = (True, 'success')
        finally:
            await pool.close()
        return result
    
    try:
        success, message = run_async(create_response())
        if success:
            return jsonify({'success': True, 'message': 'Отклик успешно отправлен!'})
        else:
            return jsonify({'success': False, 'error': 'Вы уже откликались на этот заказ'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/complaint', methods=['POST'])
def submit_complaint():
    data = request.json
    order_id = data.get('order_id')
    category = data.get('category')
    description = data.get('description')
    user_id = data.get('user_id')
    
    if not order_id or not description:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid order_id'}), 400
    description = description.strip()
    if not description:
        return jsonify({'success': False, 'error': 'Description is empty'}), 400
    category = (category or 'MiniApp').strip() or 'MiniApp'
    try:
        reporter_id = int(user_id)
    except (TypeError, ValueError):
        reporter_id = -1
    
    async def save_complaint():
        pool = await get_db_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO complaints (
                        user_id,
                        complaint_type,
                        target_id,
                        description,
                        status
                    ) VALUES ($1, $2, $3, $4, 'open')
                ''', reporter_id, 'order', order_id_int, f"{category}: {description}")
                return True
        except Exception as e:
            return False
        finally:
            await pool.close()
    
    try:
        success = run_async(save_complaint())
        if success:
            return jsonify({'success': True, 'message': 'Жалоба отправлена'})
        else:
            return jsonify({'success': False, 'error': 'Ошибка сохранения жалобы'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
