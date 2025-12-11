"""
Модуль базы данных
Все операции с PostgreSQL базой данных
"""
import asyncpg
import logging
from datetime import datetime, timedelta
from config import DATABASE_URL

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None

    def is_connected(self):
        """Проверка наличия подключения к БД"""
        return self.pool is not None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        await self.create_tables()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    user_role VARCHAR(20) DEFAULT 'customer',
                    photo_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT FALSE,
                    ban_reason TEXT,
                    banned_at TIMESTAMP,
                    is_admin BOOLEAN DEFAULT FALSE,
                    suspicious_orders_notifications BOOLEAN DEFAULT TRUE,
                    complaints_notifications BOOLEAN DEFAULT TRUE,
                    quiet_mode BOOLEAN DEFAULT FALSE,
                    moderation_sensitivity VARCHAR(20) DEFAULT 'medium',
                    captcha_passed BOOLEAN DEFAULT FALSE
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS executor_profiles (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    rating DECIMAL(3,2) DEFAULT 0.0,
                    completed_orders INTEGER DEFAULT 0,
                    level VARCHAR(20) DEFAULT 'новичок',
                    bio TEXT,
                    badges TEXT[],
                    penalty_points DECIMAL(5,2) DEFAULT 0.0,
                    base_rating DECIMAL(3,2) DEFAULT 5.0
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS customer_profiles (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    rating DECIMAL(3,2) DEFAULT 0.0,
                    total_orders INTEGER DEFAULT 0
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id SERIAL PRIMARY KEY,
                    customer_id BIGINT REFERENCES users(user_id),
                    executor_id BIGINT REFERENCES users(user_id),
                    price DECIMAL(10,2),
                    start_time VARCHAR(50),
                    address VARCHAR(500),
                    workers_count INTEGER NOT NULL DEFAULT 1,
                    comment TEXT,
                    status VARCHAR(50) DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    is_urgent BOOLEAN DEFAULT FALSE,
                    decline_reason TEXT,
                    declined_at TIMESTAMP,
                    phone_number VARCHAR(20),
                    is_deleted BOOLEAN DEFAULT FALSE
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS responses (
                    response_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                    executor_id BIGINT REFERENCES users(user_id),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id),
                    reviewer_id BIGINT REFERENCES users(user_id),
                    reviewee_id BIGINT REFERENCES users(user_id),
                    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id),
                    user1_id BIGINT REFERENCES users(user_id),
                    user2_id BIGINT REFERENCES users(user_id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id SERIAL PRIMARY KEY,
                    chat_id INTEGER REFERENCES chats(chat_id) ON DELETE CASCADE,
                    sender_id BIGINT REFERENCES users(user_id),
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS complaints (
                    complaint_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    complaint_type VARCHAR(20) NOT NULL CHECK (complaint_type IN ('order', 'user', 'idea')),
                    target_id VARCHAR(100),
                    description TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'resolved')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    admin_note TEXT
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    message TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS moderation_patterns (
                    pattern_id SERIAL PRIMARY KEY,
                    keyword VARCHAR(255) NOT NULL UNIQUE,
                    category VARCHAR(50) NOT NULL,
                    risk_weight INTEGER NOT NULL DEFAULT 1,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS whitelist_phrases (
                    phrase_id SERIAL PRIMARY KEY,
                    phrase VARCHAR(255) NOT NULL UNIQUE,
                    category VARCHAR(50),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS moderation_logs (
                    log_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id),
                    risk_score INTEGER NOT NULL,
                    matched_patterns TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS admin_moderation_decisions (
                    decision_id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(order_id),
                    admin_id BIGINT REFERENCES users(user_id),
                    decision VARCHAR(20) NOT NULL,
                    order_text TEXT,
                    risk_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key VARCHAR(50) PRIMARY KEY,
                    setting_value VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by BIGINT REFERENCES users(user_id)
                )
            ''')
            
            # Инициализируем глобальную настройку чувствительности модерации
            await conn.execute('''
                INSERT INTO system_settings (setting_key, setting_value) 
                VALUES ('moderation_sensitivity', 'medium') 
                ON CONFLICT (setting_key) DO NOTHING
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_bot_messages (
                    user_id BIGINT PRIMARY KEY,
                    last_bot_message_id BIGINT,
                    chat_id BIGINT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS hidden_orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                    hidden_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, order_id)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS penalty_log (
                    id SERIAL PRIMARY KEY,
                    executor_id BIGINT REFERENCES users(user_id),
                    order_id INTEGER REFERENCES orders(order_id),
                    penalty DECIMAL(5,2) NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def get_user(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)

    async def create_user(self, user_id, username, first_name):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING',
                user_id, username, first_name
            )
            await conn.execute(
                'INSERT INTO executor_profiles (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING',
                user_id
            )
            await conn.execute(
                'INSERT INTO customer_profiles (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING',
                user_id
            )
        
        # Apply migrations
        await self._apply_migrations()

    async def _apply_migrations(self):
        """Apply any pending database migrations"""
        async with self.pool.acquire() as conn:
            try:
                # Add work_type column to orders table if it doesn't exist
                await conn.execute('''
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS work_type VARCHAR(50);
                ''')
                await conn.execute('''
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS captcha_passed BOOLEAN DEFAULT FALSE;
                ''')
                await conn.execute('''
                    ALTER TABLE executor_profiles ADD COLUMN IF NOT EXISTS penalty_points DECIMAL(5,2) DEFAULT 0.0;
                ''')
                await conn.execute('''
                    ALTER TABLE executor_profiles ADD COLUMN IF NOT EXISTS base_rating DECIMAL(3,2) DEFAULT 5.0;
                ''')
            except Exception as e:
                logger.debug(f"Migration error (may be already applied): {e}")

    async def update_role(self, user_id, role):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET user_role = $1 WHERE user_id = $2', role, user_id)

    async def create_order(self, customer_id, price, start_time, address, workers_count, comment, phone_number=None, work_type=None):
        async with self.pool.acquire() as conn:
            order_id = await conn.fetchval(
                '''INSERT INTO orders (customer_id, price, start_time, address, workers_count, comment, phone_number, work_type)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING order_id''',
                customer_id, price, start_time, address, workers_count, comment, phone_number, work_type
            )
            return order_id

    async def get_customer_orders(self, customer_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE customer_id = $1 AND status NOT IN (\'completed\', \'deleted\') AND is_deleted = FALSE ORDER BY created_at DESC',
                customer_id
            )

    async def get_open_orders(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE status = \'open\' AND is_deleted = FALSE ORDER BY created_at DESC'
            )

    async def get_all_active_orders(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE status NOT IN (\'completed\', \'deleted\', \'cancelled\') AND is_deleted = FALSE ORDER BY created_at DESC'
            )

    async def get_order(self, order_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('SELECT * FROM orders WHERE order_id = $1', order_id)

    # Filter methods
    async def get_orders_by_work_type(self, work_type):
        """Get open orders filtered by work type"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE status = \'open\' AND work_type = $1 AND is_deleted = FALSE ORDER BY created_at DESC',
                work_type
            )
    
    async def get_orders_by_price_range(self, min_price, max_price):
        """Get open orders filtered by price range"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE status = \'open\' AND price >= $1 AND price <= $2 AND is_deleted = FALSE ORDER BY price ASC',
                min_price, max_price
            )
    
    async def get_orders_by_location(self, location):
        """Get open orders filtered by location (substring match)"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE status = \'open\' AND address ILIKE $1 AND is_deleted = FALSE ORDER BY created_at DESC',
                f'%{location}%'
            )
    
    async def get_orders_by_rating_threshold(self, min_rating):
        """Get open orders from customers with minimum rating"""
        async with self.pool.acquire() as conn:
            return await conn.fetch('''
                SELECT o.* FROM orders o
                JOIN users u ON o.customer_id = u.user_id
                JOIN customer_profiles cp ON u.user_id = cp.user_id
                WHERE o.status = 'open' AND cp.rating >= $1 AND o.is_deleted = FALSE
                ORDER BY o.created_at DESC
            ''', min_rating)

    async def delete_order(self, order_id):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE orders SET is_deleted = TRUE WHERE order_id = $1', order_id)
    
    async def get_deleted_orders(self, customer_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE customer_id = $1 AND is_deleted = TRUE ORDER BY created_at DESC',
                customer_id
            )
    
    async def get_customer_completed_orders(self, customer_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE customer_id = $1 AND status = \'completed\' AND is_deleted = FALSE ORDER BY created_at DESC',
                customer_id
            )
    
    async def restore_order(self, order_id):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE orders SET is_deleted = FALSE WHERE order_id = $1', order_id)
    
    async def delete_all_customer_orders(self, customer_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE orders SET is_deleted = TRUE WHERE customer_id = $1 AND status NOT IN (\'completed\', \'deleted\') AND is_deleted = FALSE',
                customer_id
            )
    
    async def permanent_delete_order(self, order_id):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM orders WHERE order_id = $1', order_id)
    
    async def delete_all_user_orders(self, user_id):
        """Удаляет все активные заказы пользователя (и как заказчика, и как исполнителя)"""
        async with self.pool.acquire() as conn:
            # Удаляем заказы где пользователь заказчик (сбрасываем назначение и помечаем удаленными)
            await conn.execute(
                '''UPDATE orders 
                   SET is_deleted = TRUE, 
                       status = 'cancelled',
                       executor_id = NULL, 
                       assigned_at = NULL
                   WHERE customer_id = $1 
                   AND status NOT IN ('completed', 'deleted') 
                   AND is_deleted = FALSE''',
                user_id
            )
            # Возвращаем в открытые заказы где пользователь исполнитель
            await conn.execute(
                '''UPDATE orders 
                   SET status = 'open', executor_id = NULL, assigned_at = NULL
                   WHERE executor_id = $1 
                   AND status IN ('assigned', 'in_progress', 'awaiting_confirmation')
                   AND is_deleted = FALSE''',
                user_id
            )

    async def create_response(self, order_id, executor_id, message):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO responses (order_id, executor_id, message) VALUES ($1, $2, $3)',
                order_id, executor_id, message
            )

    async def get_responses(self, order_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                '''SELECT r.*, u.username, u.first_name, ep.rating, ep.completed_orders, ep.level
                   FROM responses r
                   JOIN users u ON r.executor_id = u.user_id
                   JOIN executor_profiles ep ON r.executor_id = ep.user_id
                   WHERE r.order_id = $1
                   ORDER BY ep.rating DESC, ep.completed_orders DESC''',
                order_id
            )

    async def get_response_by_executor(self, order_id, executor_id):
        """Получает отклик исполнителя на конкретный заказ"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM responses WHERE order_id = $1 AND executor_id = $2',
                order_id, executor_id
            )

    async def assign_executor(self, order_id, executor_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE orders SET executor_id = $1, status = \'assigned\', assigned_at = $2 WHERE order_id = $3',
                executor_id, datetime.now(), order_id
            )

    async def get_executor_orders(self, executor_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM orders WHERE executor_id = $1 AND status IN (\'assigned\', \'in_progress\', \'awaiting_confirmation\') AND is_deleted = FALSE ORDER BY created_at DESC',
                executor_id
            )
    
    async def get_executor_active_order(self, executor_id):
        async with self.pool.acquire() as conn:
            # Исключаем 'awaiting_confirmation' чтобы исполнитель мог брать новые заказы
            return await conn.fetchrow(
                'SELECT * FROM orders WHERE executor_id = $1 AND status IN (\'assigned\', \'in_progress\') AND status != \'awaiting_confirmation\' AND is_deleted = FALSE ORDER BY created_at DESC LIMIT 1',
                executor_id
            )
    
    async def get_executor_history(self, executor_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                '''
                SELECT 
                    o.*,
                    r.rating,
                    r.comment as review_comment,
                    r.created_at as review_date
                FROM orders o
                LEFT JOIN reviews r ON o.order_id = r.order_id AND r.reviewer_id = o.customer_id AND r.reviewee_id = o.executor_id
                WHERE o.executor_id = $1 AND o.status IN ('completed', 'deleted', 'cancelled', 'excluded')
                ORDER BY o.completed_at DESC NULLS LAST, o.created_at DESC
                LIMIT 50
                ''',
                executor_id
            )
    
    async def clear_executor_history(self, executor_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE orders SET status = \'archived\' WHERE executor_id = $1 AND status IN (\'completed\', \'deleted\', \'cancelled\', \'excluded\')',
                executor_id
            )

    async def complete_order(self, order_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE orders SET status = \'completed\', completed_at = $1 WHERE order_id = $2',
                datetime.now(), order_id
            )
    
    async def decline_order(self, order_id, decline_reason):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE orders SET status = \'open\', executor_id = NULL, decline_reason = $1, declined_at = $2 WHERE order_id = $3',
                decline_reason, datetime.now(), order_id
            )

    async def create_review(self, order_id, reviewer_id, reviewee_id, rating, comment):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO reviews (order_id, reviewer_id, reviewee_id, rating, comment) VALUES ($1, $2, $3, $4, $5)',
                order_id, reviewer_id, reviewee_id, rating, comment
            )
            
            avg_rating = await conn.fetchval(
                'SELECT AVG(rating) FROM reviews WHERE reviewee_id = $1',
                reviewee_id
            )
            
            user = await conn.fetchrow('SELECT user_role FROM users WHERE user_id = $1', reviewee_id)
            if user['user_role'] == 'executor':
                await conn.execute(
                    'UPDATE executor_profiles SET rating = $1 WHERE user_id = $2',
                    round(avg_rating, 2), reviewee_id
                )
            else:
                await conn.execute(
                    'UPDATE customer_profiles SET rating = $1 WHERE user_id = $2',
                    round(avg_rating, 2), reviewee_id
                )

    async def update_executor_rating(self, user_id, new_rating):
        """Обновляет рейтинг исполнителя напрямую (для админов)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE executor_profiles SET rating = $1 WHERE user_id = $2',
                round(float(new_rating), 2), user_id
            )
    
    async def update_customer_rating(self, user_id, new_rating):
        """Обновляет рейтинг заказчика напрямую (для админов)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE customer_profiles SET rating = $1 WHERE user_id = $2',
                round(float(new_rating), 2), user_id
            )

    async def get_executor_profile(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM executor_profiles WHERE user_id = $1',
                user_id
            )
    
    async def get_customer_rating(self, user_id):
        async with self.pool.acquire() as conn:
            profile = await conn.fetchrow(
                'SELECT rating FROM customer_profiles WHERE user_id = $1',
                user_id
            )
            return profile['rating'] if profile else 0.0

    async def get_user_by_username(self, username):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM users WHERE username = $1',
                username.lstrip('@')
            )
    
    async def get_reviews(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                '''SELECT r.*, u.username, u.first_name 
                   FROM reviews r
                   JOIN users u ON r.reviewer_id = u.user_id
                   WHERE r.reviewee_id = $1
                   ORDER BY r.created_at ASC''',
                user_id
            )

    async def update_executor_stats(self, executor_id):
        async with self.pool.acquire() as conn:
            completed = await conn.fetchval(
                'SELECT COUNT(*) FROM orders WHERE executor_id = $1 AND status = \'completed\'',
                executor_id
            )
            
            level = 'новичок'
            if completed >= 50:
                level = 'топ'
            elif completed >= 10:
                level = 'опытный'
            
            await conn.execute(
                'UPDATE executor_profiles SET completed_orders = $1, level = $2 WHERE user_id = $3',
                completed, level, executor_id
            )

    async def get_leaderboard(self, role='executor', limit=10):
        async with self.pool.acquire() as conn:
            if role == 'executor':
                return await conn.fetch(
                    '''SELECT u.user_id, u.username, u.first_name, ep.rating, ep.completed_orders, ep.level
                       FROM users u
                       JOIN executor_profiles ep ON u.user_id = ep.user_id
                       ORDER BY ep.rating DESC, ep.completed_orders DESC
                       LIMIT $1''',
                    limit
                )
            else:
                return await conn.fetch(
                    '''SELECT u.user_id, u.username, u.first_name, cp.rating, cp.total_orders
                       FROM users u
                       JOIN customer_profiles cp ON u.user_id = cp.user_id
                       ORDER BY cp.rating DESC, cp.total_orders DESC
                       LIMIT $1''',
                    limit
                )

    async def get_top_active_executors_24h(self, limit=2):
        """Получить топ активных исполнителей за последние 24 часа"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                '''SELECT u.user_id, u.username, u.first_name, ep.rating,
                          COUNT(o.order_id) as orders_24h
                   FROM users u
                   JOIN executor_profiles ep ON u.user_id = ep.user_id
                   LEFT JOIN orders o ON u.user_id = o.executor_id 
                                     AND o.completed_at >= NOW() - INTERVAL '24 hours'
                                     AND o.status = 'completed'
                   WHERE u.user_role = 'executor'
                   GROUP BY u.user_id, u.username, u.first_name, ep.rating
                   ORDER BY orders_24h DESC, ep.rating DESC
                   LIMIT $1''',
                limit
            )

    async def create_notification(self, user_id, message):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO notifications (user_id, message) VALUES ($1, $2)',
                user_id, message
            )

    async def ban_user(self, user_id, reason):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET is_banned = TRUE, ban_reason = $1, banned_at = $2 WHERE user_id = $3',
                reason, datetime.now(), user_id
            )

    async def unban_user(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET is_banned = FALSE, ban_reason = NULL, banned_at = NULL WHERE user_id = $1',
                user_id
            )

    async def make_admin(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET is_admin = TRUE WHERE user_id = $1', user_id)

    async def get_all_users(self, limit=20, offset=0):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2',
                limit, offset
            )
    
    async def get_all_admins(self):
        """Получить всех администраторов"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM users WHERE is_admin = TRUE'
            )
    
    async def get_all_executors(self):
        """Получить всех исполнителей (пользователей с ролью executor)"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                'SELECT * FROM users WHERE user_role = \'executor\' AND is_banned = FALSE'
            )
    
    async def hide_order_for_user(self, user_id, order_id):
        """Скрыть заказ для конкретного пользователя"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO hidden_orders (user_id, order_id) VALUES ($1, $2) ON CONFLICT (user_id, order_id) DO NOTHING',
                user_id, order_id
            )
    
    async def is_order_hidden(self, user_id, order_id):
        """Проверить, скрыт ли заказ для пользователя"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                'SELECT 1 FROM hidden_orders WHERE user_id = $1 AND order_id = $2',
                user_id, order_id
            )
            return result is not None
    
    async def get_hidden_orders_for_user(self, user_id):
        """Получить список ID скрытых заказов для пользователя"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT order_id FROM hidden_orders WHERE user_id = $1',
                user_id
            )
            return [row['order_id'] for row in rows]

    async def get_stats(self):
        async with self.pool.acquire() as conn:
            total_users = await conn.fetchval('SELECT COUNT(*) FROM users')
            total_orders = await conn.fetchval('SELECT COUNT(*) FROM orders')
            active_orders = await conn.fetchval('SELECT COUNT(*) FROM orders WHERE status IN (\'open\', \'assigned\', \'in_progress\')')
            completed_orders = await conn.fetchval('SELECT COUNT(*) FROM orders WHERE status = \'completed\'')
            
            return {
                'total_users': total_users,
                'total_orders': total_orders,
                'active_orders': active_orders,
                'completed_orders': completed_orders
            }

    async def get_or_create_chat(self, order_id, user1_id, user2_id):
        async with self.pool.acquire() as conn:
            chat = await conn.fetchrow(
                'SELECT * FROM chats WHERE order_id = $1',
                order_id
            )
            if not chat:
                chat_id = await conn.fetchval(
                    'INSERT INTO chats (order_id, user1_id, user2_id) VALUES ($1, $2, $3) RETURNING chat_id',
                    order_id, user1_id, user2_id
                )
                return chat_id
            return chat['chat_id']

    async def send_message(self, chat_id, sender_id, message):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO messages (chat_id, sender_id, message) VALUES ($1, $2, $3)',
                chat_id, sender_id, message
            )

    async def get_chat_messages(self, chat_id, limit=50):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                '''SELECT m.*, u.first_name, u.username 
                   FROM messages m
                   JOIN users u ON m.sender_id = u.user_id
                   WHERE m.chat_id = $1
                   ORDER BY m.created_at DESC
                   LIMIT $2''',
                chat_id, limit
            )

    async def create_complaint(self, user_id, complaint_type, target_id, description):
        async with self.pool.acquire() as conn:
            complaint_id = await conn.fetchval(
                '''INSERT INTO complaints (user_id, complaint_type, target_id, description) 
                   VALUES ($1, $2, $3, $4) RETURNING complaint_id''',
                user_id, complaint_type, target_id, description
            )
            return complaint_id

    async def get_complaints(self, status=None):
        async with self.pool.acquire() as conn:
            if status:
                return await conn.fetch(
                    'SELECT * FROM complaints WHERE status = $1 ORDER BY created_at DESC',
                    status
                )
            else:
                return await conn.fetch(
                    'SELECT * FROM complaints ORDER BY created_at DESC'
                )

    async def get_complaint(self, complaint_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM complaints WHERE complaint_id = $1',
                complaint_id
            )

    async def resolve_complaint(self, complaint_id, admin_note=None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''UPDATE complaints 
                   SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, admin_note = $2
                   WHERE complaint_id = $1''',
                complaint_id, admin_note
            )

    async def get_complaints_count(self, status=None):
        async with self.pool.acquire() as conn:
            if status:
                return await conn.fetchval(
                    'SELECT COUNT(*) FROM complaints WHERE status = $1',
                    status
                )
            else:
                return await conn.fetchval('SELECT COUNT(*) FROM complaints')

    async def get_completed_orders(self, user_id, role='customer'):
        async with self.pool.acquire() as conn:
            if role == 'customer':
                return await conn.fetch(
                    'SELECT * FROM orders WHERE customer_id = $1 AND status = \'completed\' AND is_deleted = FALSE ORDER BY completed_at DESC',
                    user_id
                )
            else:
                return await conn.fetch(
                    'SELECT * FROM orders WHERE executor_id = $1 AND status = \'completed\' AND is_deleted = FALSE ORDER BY completed_at DESC',
                    user_id
                )

    async def update_customer_stats(self, customer_id):
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                'SELECT COUNT(*) FROM orders WHERE customer_id = $1',
                customer_id
            )
            await conn.execute(
                '''INSERT INTO customer_profiles (user_id, total_orders) 
                   VALUES ($1, $2) 
                   ON CONFLICT (user_id) 
                   DO UPDATE SET total_orders = $2''',
                customer_id, total
            )

    async def init_moderation_patterns(self):
        """Заполняет базу подозрительных паттернов (расширенная база из интернет-исследований 2024-2025)"""
        patterns = [
            # === НАРКОТИКИ И КУРЬЕРЫ-ЗАКЛАДЧИКИ (приоритет 5) ===
            ('закладчик', 'наркотики', 5),
            ('закладки', 'наркотики', 5),
            ('кладмен', 'наркотики', 5),
            ('минер', 'наркотики', 5),
            ('фасовщик', 'наркотики', 5),
            ('трафаретчик', 'наркотики', 5),
            ('легальная продукция', 'наркотики', 5),
            ('клад', 'наркотики', 4),
            ('развешивать по пакетикам', 'наркотики', 5),
            ('мастер-квест', 'наркотики', 4),
            ('спайс', 'наркотики', 5),
            ('соль', 'наркотики', 3),
            ('скорость', 'наркотики', 2),
            ('курьер', 'наркотики', 2),
            ('развозка', 'наркотики', 2),
            ('доставка посылок', 'наркотики', 2),
            ('доставка лёгких заказов', 'наркотики', 4),
            ('пешие курьеры', 'наркотики', 3),
            ('анонимно', 'наркотики', 3),
            ('конфиденциально', 'наркотики', 2),
            ('без опыта', 'наркотики', 1),
            ('быстрые деньги', 'наркотики', 3),
            ('наличные сразу', 'наркотики', 2),
            ('телеграм только', 'наркотики', 3),
            ('пишите в тг', 'наркотики', 2),
            ('фото паспорта', 'наркотики', 4),
            ('страховой взнос', 'наркотики', 4),
            ('залог', 'наркотики', 2),
            ('нефасованный опт', 'наркотики', 5),
            ('мина', 'наркотики', 3),
            
            # === НЕРЕАЛЬНЫЕ СУММЫ (признак мошенничества) ===
            ('лёгкий заработок', 'мошенничество', 4),
            ('высокий доход', 'мошенничество', 3),
            ('быстрый заработок', 'мошенничество', 4),
            ('300 тысяч в месяц', 'мошенничество', 5),
            ('500 тысяч в месяц', 'мошенничество', 5),
            ('900 тысяч', 'мошенничество', 5),
            ('30 тысяч в день', 'мошенничество', 5),
            ('50 тысяч в день', 'мошенничество', 5),
            ('3-4 часа в день', 'мошенничество', 2),
            ('свободный график', 'мошенничество', 1),
            
            # === АЗАРТНЫЕ ИГРЫ ===
            ('казино', 'азартные_игры', 5),
            ('ставки', 'азартные_игры', 4),
            ('букмекер', 'азартные_игры', 5),
            ('покер', 'азартные_игры', 4),
            ('слоты', 'азартные_игры', 5),
            ('рулетка', 'азартные_игры', 5),
            ('выигрыш', 'азартные_игры', 3),
            ('бонус за регистрацию', 'азартные_игры', 4),
            
            # === ИНТИМ УСЛУГИ И ПОРНОГРАФИЯ ===
            ('порно', 'порнография', 5),
            ('эскорт', 'порнография', 5),
            ('интим', 'порнография', 5),
            ('интим услуги', 'порнография', 5),
            ('проститутки', 'порнография', 5),
            ('девушки по вызову', 'порнография', 5),
            ('массаж для мужчин', 'порнография', 4),
            ('знакомства 18+', 'порнография', 4),
            ('вебкам', 'порнография', 5),
            ('onlyfans', 'порнография', 4),
            
            # === ОРУЖИЕ И ВЗРЫВЧАТКА ===
            ('оружие', 'оружие', 5),
            ('пистолет', 'оружие', 5),
            ('взрывчатка', 'оружие', 5),
            ('автомат', 'оружие', 5),
            ('патроны', 'оружие', 5),
            ('граната', 'оружие', 5),
            
            # === ФИНАНСОВОЕ МОШЕННИЧЕСТВО ===
            ('обнал', 'финансовые_махинации', 5),
            ('обналичка', 'финансовые_махинации', 5),
            ('отмыв денег', 'финансовые_махинации', 5),
            ('фальшивые', 'финансовые_махинации', 5),
            ('поддельные документы', 'финансовые_махинации', 5),
            ('липовые', 'финансовые_махинации', 4),
            ('чёрный нал', 'финансовые_махинации', 5),
            ('крипта', 'криптовалюта', 2),
            ('btc', 'криптовалюта', 2),
            ('usdt', 'криптовалюта', 2),
            ('киви-кошелёк', 'финансовые_махинации', 2),
            
            # === МЕДИЦИНСКИЕ И ФАРМАЦЕВТИЧЕСКИЕ ===
            ('виагра', 'медицина', 4),
            ('сиалис', 'медицина', 4),
            ('аптека без рецепта', 'медицина', 4),
            ('лекарства запрещённые', 'медицина', 5),
            ('стероиды', 'медицина', 4),
            ('100% результат', 'медицина', 3),
            ('гарантия излечения', 'медицина', 4),
            
            # === АГРЕССИВНЫЙ МАРКЕТИНГ (Telegram/Avito запреты) ===
            ('только сегодня', 'агрессивный_маркетинг', 2),
            ('не упусти', 'агрессивный_маркетинг', 2),
            ('последний шанс', 'агрессивный_маркетинг', 3),
            ('лучший', 'агрессивный_маркетинг', 1),
            ('самый выгодный', 'агрессивный_маркетинг', 2),
            ('топовый', 'агрессивный_маркетинг', 1),
        ]
        
        logging.info("Loading moderation patterns...")
        async with self.pool.acquire() as conn:
            for keyword, category, weight in patterns:
                await conn.execute(
                    '''INSERT INTO moderation_patterns (keyword, category, risk_weight, is_active) 
                       VALUES ($1, $2, $3, TRUE) 
                       ON CONFLICT (keyword) 
                       DO UPDATE SET 
                           category = EXCLUDED.category,
                           risk_weight = EXCLUDED.risk_weight,
                           is_active = TRUE''',
                    keyword, category, weight
                )
            
            # Проверка что все паттерны загружены
            count = await conn.fetchval('SELECT COUNT(*) FROM moderation_patterns WHERE is_active = TRUE')
            if count < len(patterns):
                logging.warning(f"Only {count}/{len(patterns)} patterns loaded! Some patterns may be missing.")
            else:
                logging.info(f"Successfully loaded {count} moderation patterns (expected {len(patterns)})")

    async def init_whitelist(self):
        """Заполняет whitelist легальных формулировок"""
        phrases = [
            ('грузчик', 'легальная_работа'),
            ('разнорабочий', 'легальная_работа'),
            ('уборка', 'легальная_работа'),
            ('клининг', 'легальная_работа'),
            ('ремонт', 'легальная_работа'),
            ('демонтаж', 'легальная_работа'),
            ('стройка', 'легальная_работа'),
            ('переезд', 'легальная_работа'),
            ('погрузка', 'легальная_работа'),
            ('разгрузка', 'легальная_работа'),
            ('сборка мебели', 'легальная_работа'),
            ('покраска', 'легальная_работа'),
            ('монтаж', 'легальная_работа'),
            ('сантехник', 'легальная_работа'),
            ('электрик', 'легальная_работа'),
            ('штукатурка', 'легальная_работа'),
            ('поклейка обоев', 'легальная_работа'),
        ]
        
        logging.info("Loading whitelist phrases...")
        async with self.pool.acquire() as conn:
            for phrase, category in phrases:
                await conn.execute(
                    '''INSERT INTO whitelist_phrases (phrase, category) 
                       VALUES ($1, $2) 
                       ON CONFLICT (phrase) DO NOTHING''',
                    phrase, category
                )
        logging.info(f"Loaded {len(phrases)} whitelist phrases")

    async def check_order_content(self, text, price):
        """Проверяет контент заказа на подозрительность"""
        text_lower = text.lower()
        risk_score = 0
        matched_patterns = []
        
        async with self.pool.acquire() as conn:
            # Проверяем whitelist
            whitelist = await conn.fetch(
                'SELECT phrase FROM whitelist_phrases WHERE is_active = TRUE'
            )
            for row in whitelist:
                if row['phrase'].lower() in text_lower:
                    return 0, []
            
            # Проверяем подозрительные паттерны
            patterns = await conn.fetch(
                'SELECT keyword, category, risk_weight FROM moderation_patterns WHERE is_active = TRUE'
            )
            
            for pattern in patterns:
                keyword = pattern['keyword'].lower()
                if keyword in text_lower:
                    risk_score += pattern['risk_weight']
                    matched_patterns.append(f"{pattern['keyword']} (+{pattern['risk_weight']})")
            
            # Дополнительная проверка на подозрительную цену для курьеров
            if 'курьер' in text_lower and price > 4000:
                risk_score += 3
                matched_patterns.append("курьер+высокая_цена (+3)")
            
            if 'доставка' in text_lower and price > 4000:
                risk_score += 2
                matched_patterns.append("доставка+высокая_цена (+2)")
        
        return risk_score, matched_patterns

    async def log_moderation(self, order_id, risk_score, matched_patterns):
        """Логирует результат модерации"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO moderation_logs (order_id, risk_score, matched_patterns) 
                   VALUES ($1, $2, $3)''',
                order_id, risk_score, ', '.join(matched_patterns) if matched_patterns else ''
            )

    async def get_suspicious_orders(self, min_risk_score=4):
        """Получает список подозрительных заказов"""
        async with self.pool.acquire() as conn:
            # Сначала пытаемся получить из moderation_logs
            logged = await conn.fetch(
                '''SELECT o.*, m.risk_score, m.matched_patterns, m.created_at as checked_at
                   FROM orders o
                   JOIN moderation_logs m ON o.order_id = m.order_id
                   WHERE m.risk_score >= $1 AND o.is_deleted = FALSE
                   ORDER BY m.created_at DESC
                   LIMIT 50''',
                min_risk_score
            )
            
            if logged:
                return logged
            
            # Если в moderation_logs пусто, получаем все недавние объявления и считаем риск
            # (последние 7 дней, которые могут быть подозрительными)
            all_orders = await conn.fetch(
                '''SELECT * FROM orders 
                   WHERE is_deleted = FALSE 
                   AND created_at > NOW() - INTERVAL '7 days'
                   ORDER BY created_at DESC
                   LIMIT 50'''
            )
            
            return all_orders or []

    async def toggle_notifications(self, user_id, notification_type, enabled):
        """Переключает уведомления для админа"""
        async with self.pool.acquire() as conn:
            if notification_type == 'suspicious_orders':
                await conn.execute(
                    'UPDATE users SET suspicious_orders_notifications = $1 WHERE user_id = $2',
                    enabled, user_id
                )
            elif notification_type == 'complaints':
                await conn.execute(
                    'UPDATE users SET complaints_notifications = $1 WHERE user_id = $2',
                    enabled, user_id
                )

    async def get_admin_notification_settings(self, user_id):
        """Получает настройки уведомлений админа"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT suspicious_orders_notifications, complaints_notifications, quiet_mode FROM users WHERE user_id = $1',
                user_id
            )

    async def toggle_quiet_mode(self, user_id):
        """Переключает режим спокойствия для админа"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                'UPDATE users SET quiet_mode = NOT quiet_mode WHERE user_id = $1 RETURNING quiet_mode',
                user_id
            )
            return result['quiet_mode'] if result else False

    async def detect_anomalies(self, text, address):
        """Анализирует текст и адрес на аномалии"""
        anomalies = []
        risk_points = 0
        
        # Проверка длины текста
        if len(text.strip()) < 10:
            anomalies.append("слишком_короткий_текст (+2)")
            risk_points += 2
        
        # Проверка на бессмысленные символы
        import re
        if re.search(r'(.)\1{4,}', text):  # Повторяющиеся символы (аааааа, ккккк)
            anomalies.append("повторяющиеся_символы (+3)")
            risk_points += 3
        
        # Проверка адреса на подозрительность
        if len(address.strip()) < 5:
            anomalies.append("подозрительный_адрес (+2)")
            risk_points += 2
        
        # Проверка на случайный набор букв
        if not any(word in text.lower() for word in ['работа', 'нужно', 'требуется', 'ищу', 'надо', 'заказ', 'услуга']):
            if len(text.strip()) < 20:
                anomalies.append("несвязный_текст (+2)")
                risk_points += 2
        
        # Проверка на большое количество эмодзи
        emoji_count = sum(1 for char in text if ord(char) > 127462)
        if emoji_count > 5:
            anomalies.append("избыток_эмодзи (+1)")
            risk_points += 1
        
        return risk_points, anomalies

    async def check_order_content_smart(self, text, price, address, user_id, sensitivity='medium'):
        """Улучшенная проверка контента с анализом аномалий и адаптивной чувствительностью"""
        text_lower = text.lower()
        risk_score = 0
        matched_patterns = []
        
        # Пороги чувствительности
        sensitivity_thresholds = {
            'off': 999,      # Фактически выключено
            'low': 6,        # Только очень подозрительное
            'medium': 4,     # Средний уровень (по умолчанию)
            'high': 2        # Строгая модерация
        }
        
        async with self.pool.acquire() as conn:
            # Проверяем новый ли пользователь (зарегистрирован менее 48 часов назад)
            user = await conn.fetchrow(
                'SELECT created_at FROM users WHERE user_id = $1',
                user_id
            )
            if user:
                from datetime import datetime, timedelta
                user_age = datetime.now() - user['created_at']
                if user_age < timedelta(hours=48):
                    risk_score += 2
                    matched_patterns.append("новый_пользователь (<48ч) (+2)")
                elif user_age < timedelta(hours=168):  # Менее недели
                    risk_score += 1
                    matched_patterns.append("молодой_аккаунт (<7д) (+1)")
            
            # Проверяем whitelist
            whitelist = await conn.fetch(
                'SELECT phrase FROM whitelist_phrases WHERE is_active = TRUE'
            )
            for row in whitelist:
                if row['phrase'].lower() in text_lower:
                    return 0, [], sensitivity_thresholds.get(sensitivity, 4)
            
            # Проверяем подозрительные паттерны
            patterns = await conn.fetch(
                'SELECT keyword, category, risk_weight FROM moderation_patterns WHERE is_active = TRUE'
            )
            
            for pattern in patterns:
                keyword = pattern['keyword'].lower()
                if keyword in text_lower:
                    risk_score += pattern['risk_weight']
                    matched_patterns.append(f"{pattern['keyword']} (+{pattern['risk_weight']})")
            
            # Дополнительная проверка на подозрительную цену для курьеров
            if 'курьер' in text_lower and price > 4000:
                risk_score += 3
                matched_patterns.append("курьер+высокая_цена (+3)")
            
            if 'доставка' in text_lower and price > 4000:
                risk_score += 2
                matched_patterns.append("доставка+высокая_цена (+2)")
            
            # Анализ аномалий
            anomaly_score, anomalies = await self.detect_anomalies(text, address)
            risk_score += anomaly_score
            matched_patterns.extend(anomalies)
        
        threshold = sensitivity_thresholds.get(sensitivity, 4)
        return risk_score, matched_patterns, threshold

    async def save_admin_decision(self, order_id, admin_id, decision, order_text, risk_score):
        """Сохраняет решение админа для обучения системы"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO admin_moderation_decisions 
                   (order_id, admin_id, decision, order_text, risk_score) 
                   VALUES ($1, $2, $3, $4, $5)''',
                order_id, admin_id, decision, order_text, risk_score
            )
            
            # Если админ заблокировал объявление, извлекаем ключевые слова для будущего обучения
            if decision == 'blocked':
                # Простое извлечение подозрительных слов (можно улучшить)
                words = order_text.lower().split()
                suspicious_words = [w for w in words if len(w) > 4 and w not in ['работа', 'нужно', 'требуется']]
                logging.info(f"Admin blocked order {order_id}. Potential patterns: {suspicious_words[:5]}")

    async def get_moderation_sensitivity(self):
        """Получает глобальную настройку чувствительности модерации системы"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT setting_value FROM system_settings WHERE setting_key = 'moderation_sensitivity'"
            )
            return result['setting_value'] if result else 'medium'

    async def set_moderation_sensitivity(self, sensitivity, admin_id):
        """Устанавливает глобальную чувствительность модерации (может изменить любой админ)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''UPDATE system_settings 
                   SET setting_value = $1, updated_at = CURRENT_TIMESTAMP, updated_by = $2 
                   WHERE setting_key = 'moderation_sensitivity' ''',
                sensitivity, admin_id
            )

    async def get_moderation_stats(self):
        """Получает статистику эффективности модерации"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                '''SELECT 
                    COUNT(*) as total_checks,
                    COUNT(*) FILTER (WHERE risk_score >= 4) as flagged_count,
                    AVG(risk_score) as avg_risk_score
                   FROM moderation_logs
                   WHERE created_at > NOW() - INTERVAL '30 days' '''
            )
            
            admin_decisions = await conn.fetchrow(
                '''SELECT 
                    COUNT(*) FILTER (WHERE decision = 'blocked') as blocked_count,
                    COUNT(*) FILTER (WHERE decision = 'approved') as approved_count
                   FROM admin_moderation_decisions
                   WHERE created_at > NOW() - INTERVAL '30 days' '''
            )
            
            return {
                'total_checks': stats['total_checks'] if stats else 0,
                'flagged_count': stats['flagged_count'] if stats else 0,
                'avg_risk_score': float(stats['avg_risk_score']) if stats and stats['avg_risk_score'] else 0,
                'blocked_by_admins': admin_decisions['blocked_count'] if admin_decisions else 0,
                'approved_by_admins': admin_decisions['approved_count'] if admin_decisions else 0
            }

    async def save_last_bot_message(self, user_id: int, message_id: int, chat_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO user_bot_messages (user_id, last_bot_message_id, chat_id, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET 
                    last_bot_message_id = $2, 
                    chat_id = $3,
                    updated_at = CURRENT_TIMESTAMP
            ''', user_id, message_id, chat_id)
    
    async def get_last_bot_message(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT last_bot_message_id, chat_id FROM user_bot_messages WHERE user_id = $1',
                user_id
            )
    
    async def delete_last_bot_message(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM user_bot_messages WHERE user_id = $1', user_id)

    async def mark_captcha_passed(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET captcha_passed = TRUE WHERE user_id = $1',
                user_id,
            )

    async def add_executor_penalty(self, executor_id: int, penalty_amount: float, reason: str, order_id: int = None):
        """Adds penalty points to executor and logs the reason"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''UPDATE executor_profiles 
                   SET penalty_points = COALESCE(penalty_points, 0) + $1 
                   WHERE user_id = $2''',
                penalty_amount, executor_id
            )
            await conn.execute(
                '''INSERT INTO penalty_log (executor_id, order_id, penalty, reason) 
                   VALUES ($1, $2, $3, $4)''',
                executor_id, order_id, penalty_amount, reason
            )

    async def get_executor_rating_with_penalty(self, executor_id: int) -> float:
        """Returns executor rating adjusted by penalty points"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                '''SELECT COALESCE(base_rating, 5.0) as base, 
                          COALESCE(penalty_points, 0) as penalty 
                   FROM executor_profiles WHERE user_id = $1''',
                executor_id
            )
            if not result:
                return 5.0
            base = float(result['base'])
            penalty = float(result['penalty'])
            return max(1.0, base - penalty)

    async def prune_old_bot_messages(self, hours: int = 48):
        """Удаляет записи о последних сообщениях бота старше указанного срока."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                'DELETE FROM user_bot_messages WHERE updated_at < NOW() - ($1 || " hours")::INTERVAL',
                hours,
            )

    async def close(self):
        if self.pool:
            await self.pool.close()
