-- DEnode Sample SQL Query Log File
-- This file contains sample SQL queries that would typically appear in a database log
-- You can download this file and upload it to test the query log analysis functionality

-- SELECT queries
2025-04-20 10:15:32.456 UTC [12345] LOG:  EXECUTE: SELECT * FROM users WHERE id = 5;
2025-04-20 10:15:33.123 UTC [12345] LOG:  EXECUTE: SELECT username, email FROM users WHERE active = true ORDER BY created_at DESC LIMIT 10;
2025-04-20 10:15:34.789 UTC [12345] LOG:  EXECUTE: SELECT p.id, p.name, p.price, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.price < 50.00;
2025-04-20 10:15:35.012 UTC [12345] LOG:  EXECUTE: SELECT COUNT(*) FROM orders WHERE status = 'completed' AND created_at >= '2025-04-01';
2025-04-20 10:15:36.345 UTC [12345] LOG:  EXECUTE: SELECT AVG(price) FROM products GROUP BY category_id;

-- Common JOIN patterns
2025-04-20 10:16:12.678 UTC [12345] LOG:  EXECUTE: SELECT o.id, o.order_date, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = 'pending';
2025-04-20 10:16:13.901 UTC [12345] LOG:  EXECUTE: SELECT o.id, o.order_date, i.product_id, p.name, i.quantity FROM orders o JOIN order_items i ON o.id = i.order_id JOIN products p ON i.product_id = p.id WHERE o.id = 12345;
2025-04-20 10:16:14.234 UTC [12345] LOG:  EXECUTE: SELECT u.username, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id ORDER BY u.username;

-- INSERT statements
2025-04-20 10:20:45.678 UTC [12345] LOG:  EXECUTE: INSERT INTO users (username, email, password_hash, created_at) VALUES ('new_user', 'new@example.com', 'hash123', CURRENT_TIMESTAMP);
2025-04-20 10:20:46.789 UTC [12345] LOG:  EXECUTE: INSERT INTO products (name, description, price, category_id) VALUES ('New Product', 'A description', 29.99, 3);
2025-04-20 10:20:47.123 UTC [12345] LOG:  EXECUTE: INSERT INTO orders (user_id, status, total_amount, created_at) VALUES (42, 'pending', 129.99, CURRENT_TIMESTAMP);
2025-04-20 10:20:48.456 UTC [12345] LOG:  EXECUTE: INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (1001, 5, 2, 19.99);

-- UPDATE statements
2025-04-20 10:25:12.345 UTC [12345] LOG:  EXECUTE: UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 42;
2025-04-20 10:25:13.678 UTC [12345] LOG:  EXECUTE: UPDATE products SET price = price * 1.1 WHERE category_id = 3;
2025-04-20 10:25:14.901 UTC [12345] LOG:  EXECUTE: UPDATE orders SET status = 'shipped' WHERE id = 1001;
2025-04-20 10:25:15.234 UTC [12345] LOG:  EXECUTE: UPDATE inventory SET quantity = quantity - 10 WHERE product_id = 5;

-- DELETE statements
2025-04-20 10:30:23.456 UTC [12345] LOG:  EXECUTE: DELETE FROM cart_items WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
2025-04-20 10:30:24.789 UTC [12345] LOG:  EXECUTE: DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP;
2025-04-20 10:30:25.012 UTC [12345] LOG:  EXECUTE: DELETE FROM order_items WHERE order_id = 999;

-- Complex queries
2025-04-20 10:35:34.567 UTC [12345] LOG:  EXECUTE: SELECT u.username, COUNT(o.id) as order_count, SUM(o.total_amount) as total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id
HAVING COUNT(o.id) > 5
ORDER BY total_spent DESC
LIMIT 10;

2025-04-20 10:35:35.678 UTC [12345] LOG:  EXECUTE: SELECT 
    c.name as category_name,
    COUNT(p.id) as product_count,
    MIN(p.price) as min_price,
    MAX(p.price) as max_price,
    AVG(p.price) as avg_price
FROM categories c
JOIN products p ON c.id = p.category_id
GROUP BY c.id
ORDER BY product_count DESC;

2025-04-20 10:35:36.789 UTC [12345] LOG:  EXECUTE: SELECT 
    DATE_TRUNC('day', o.created_at) as order_date,
    COUNT(o.id) as order_count,
    SUM(o.total_amount) as daily_revenue
FROM orders o
WHERE o.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY order_date
ORDER BY order_date;

-- Subqueries
2025-04-20 10:40:45.123 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id IN (SELECT id FROM categories WHERE parent_id = 5);
2025-04-20 10:40:46.234 UTC [12345] LOG:  EXECUTE: SELECT * FROM users WHERE id NOT IN (SELECT user_id FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '90 days');
2025-04-20 10:40:47.345 UTC [12345] LOG:  EXECUTE: SELECT * FROM products p WHERE price > (SELECT AVG(price) FROM products WHERE category_id = p.category_id);

-- Repeated queries showing patterns
2025-04-20 10:45:56.456 UTC [12345] LOG:  EXECUTE: SELECT * FROM users WHERE id = 10;
2025-04-20 10:45:57.567 UTC [12345] LOG:  EXECUTE: SELECT * FROM users WHERE id = 15;
2025-04-20 10:45:58.678 UTC [12345] LOG:  EXECUTE: SELECT * FROM users WHERE id = 20;
2025-04-20 10:45:59.789 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE id = 30;
2025-04-20 10:46:00.890 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE id = 35;
2025-04-20 10:46:01.901 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE id = 40;

-- Full-text search queries
2025-04-20 10:50:12.345 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE to_tsvector('english', name || ' ' || description) @@ to_tsquery('english', 'wireless & headphones');
2025-04-20 10:50:13.456 UTC [12345] LOG:  EXECUTE: SELECT * FROM articles WHERE to_tsvector('english', title || ' ' || content) @@ to_tsquery('english', 'climate & (change | crisis)');

-- Queries with potential for optimization
2025-04-20 10:55:23.567 UTC [12345] LOG:  EXECUTE: SELECT * FROM orders WHERE user_id = 42 AND created_at > '2025-01-01';
2025-04-20 10:55:24.678 UTC [12345] LOG:  EXECUTE: SELECT o.*, u.username FROM orders o, users u WHERE o.user_id = u.id AND o.status = 'shipped';
2025-04-20 10:55:25.789 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE price BETWEEN 10 AND 50 AND category_id = 3;
2025-04-20 10:55:26.890 UTC [12345] LOG:  EXECUTE: SELECT * FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE user_id = 42);

-- Transactions
2025-04-20 11:00:34.901 UTC [12345] LOG:  EXECUTE: BEGIN;
2025-04-20 11:00:35.012 UTC [12345] LOG:  EXECUTE: INSERT INTO orders (user_id, status, total_amount, created_at) VALUES (42, 'pending', 129.99, CURRENT_TIMESTAMP) RETURNING id;
2025-04-20 11:00:36.123 UTC [12345] LOG:  EXECUTE: INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (1002, 5, 2, 19.99);
2025-04-20 11:00:37.234 UTC [12345] LOG:  EXECUTE: INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (1002, 10, 1, 89.99);
2025-04-20 11:00:38.345 UTC [12345] LOG:  EXECUTE: UPDATE inventory SET quantity = quantity - 2 WHERE product_id = 5;
2025-04-20 11:00:39.456 UTC [12345] LOG:  EXECUTE: UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 10;
2025-04-20 11:00:40.567 UTC [12345] LOG:  EXECUTE: COMMIT;

-- Repeated similar patterns
2025-04-20 11:05:45.678 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id = 1 LIMIT 10 OFFSET 0;
2025-04-20 11:05:46.789 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id = 1 LIMIT 10 OFFSET 10;
2025-04-20 11:05:47.890 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id = 1 LIMIT 10 OFFSET 20;
2025-04-20 11:05:48.901 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id = 2 LIMIT 10 OFFSET 0;
2025-04-20 11:05:49.012 UTC [12345] LOG:  EXECUTE: SELECT * FROM products WHERE category_id = 2 LIMIT 10 OFFSET 10;

-- Schema modification
2025-04-20 11:10:56.123 UTC [12345] LOG:  EXECUTE: ALTER TABLE products ADD COLUMN discontinued BOOLEAN DEFAULT FALSE;
2025-04-20 11:10:57.234 UTC [12345] LOG:  EXECUTE: CREATE INDEX idx_products_category ON products(category_id);
2025-04-20 11:10:58.345 UTC [12345] LOG:  EXECUTE: CREATE INDEX idx_orders_user_date ON orders(user_id, created_at);

-- End of sample log file