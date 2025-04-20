-- Sample Query Log for e-commerce database
-- Contains queries for customers, orders, products, categories
-- Timestamp: 2025-04-15 12:00:00

-- Customer queries
SELECT * FROM customers WHERE email = 'john.smith@example.com';
SELECT id, first_name, last_name FROM customers WHERE id = 123;
SELECT * FROM customers WHERE last_login > '2025-03-01';
SELECT c.id, c.first_name, c.last_name, COUNT(o.id) as order_count 
FROM customers c 
JOIN orders o ON c.id = o.customer_id 
GROUP BY c.id, c.first_name, c.last_name;

-- Order queries
SELECT * FROM orders WHERE customer_id = 123 ORDER BY order_date DESC;
SELECT o.id, o.order_date, o.total_amount, c.first_name, c.last_name 
FROM orders o 
JOIN customers c ON o.customer_id = c.id 
WHERE o.order_date > '2025-03-01';
SELECT o.id, p.name, oi.quantity, oi.price 
FROM orders o 
JOIN order_items oi ON o.id = oi.order_id 
JOIN products p ON oi.product_id = p.id 
WHERE o.id = 5001;

-- Frequently used product listing query
SELECT p.id, p.name, p.price, p.inventory_count, c.name as category_name 
FROM products p 
JOIN categories c ON p.category_id = c.id 
WHERE p.active = true 
ORDER BY p.name;

SELECT p.id, p.name, p.price, p.inventory_count, c.name as category_name 
FROM products p 
JOIN categories c ON p.category_id = c.id 
WHERE c.id = 5 AND p.active = true 
ORDER BY p.price;

-- Product inventory updates
UPDATE products SET inventory_count = inventory_count - 1 WHERE id = 42;
UPDATE products SET price = 29.99 WHERE id = 56;

-- Customer record insertion
INSERT INTO customers (first_name, last_name, email, address) 
VALUES ('Jane', 'Doe', 'jane.doe@example.com', '123 Main St');

-- New order creation
INSERT INTO orders (customer_id, order_date, total_amount, status) 
VALUES (123, '2025-04-15', 125.50, 'pending');

INSERT INTO order_items (order_id, product_id, quantity, price) 
VALUES (5002, 42, 2, 19.99);

-- Order status update
UPDATE orders SET status = 'shipped' WHERE id = 5001;

-- Product search queries
SELECT p.* FROM products p 
WHERE p.name LIKE '%keyboard%' OR p.description LIKE '%keyboard%';
SELECT p.* FROM products p 
JOIN categories c ON p.category_id = c.id 
WHERE c.name = 'Electronics';

-- Customer order history
SELECT o.id, o.order_date, o.total_amount, o.status 
FROM orders o 
WHERE o.customer_id = 123 
ORDER BY o.order_date DESC;

-- Sales report by category
SELECT c.name, SUM(oi.quantity * oi.price) as total_sales 
FROM categories c 
JOIN products p ON c.id = p.category_id 
JOIN order_items oi ON p.id = oi.product_id 
JOIN orders o ON oi.order_id = o.id 
WHERE o.order_date BETWEEN '2025-03-01' AND '2025-04-01' 
GROUP BY c.name 
ORDER BY total_sales DESC;

-- Product reviews
SELECT p.name, r.rating, r.comment, c.first_name 
FROM products p 
JOIN reviews r ON p.id = r.product_id 
JOIN customers c ON r.customer_id = c.id 
WHERE p.id = 42;

-- Active customers query
SELECT c.* FROM customers c 
JOIN orders o ON c.id = o.customer_id 
WHERE o.order_date > '2025-01-01' 
GROUP BY c.id 
HAVING COUNT(o.id) > 1;

-- Products with limited inventory
SELECT * FROM products WHERE inventory_count < 10;

-- Customer address update
UPDATE customers SET address = '456 Oak Ave' WHERE id = 123;

-- Deleting old order draft
DELETE FROM orders WHERE status = 'draft' AND created_at < '2025-03-01';

-- Top selling products
SELECT p.id, p.name, SUM(oi.quantity) as units_sold 
FROM products p 
JOIN order_items oi ON p.id = oi.product_id 
JOIN orders o ON oi.order_id = o.id 
WHERE o.order_date BETWEEN '2025-03-01' AND '2025-04-01' 
GROUP BY p.id, p.name 
ORDER BY units_sold DESC 
LIMIT 10;

-- Product category change
UPDATE products SET category_id = 6 WHERE id = 78;

-- Order shipment details
SELECT o.id, o.order_date, s.tracking_number, s.carrier, s.shipping_date 
FROM orders o 
JOIN shipments s ON o.id = s.order_id 
WHERE o.customer_id = 123;

-- Customer login check
SELECT id, password_hash FROM customers WHERE email = 'john.smith@example.com';

-- Repeat of some common queries to show frequency
SELECT p.id, p.name, p.price, p.inventory_count, c.name as category_name 
FROM products p 
JOIN categories c ON p.category_id = c.id 
WHERE p.active = true 
ORDER BY p.name;

SELECT o.id, o.order_date, o.total_amount, c.first_name, c.last_name 
FROM orders o 
JOIN customers c ON o.customer_id = c.id 
WHERE o.order_date > '2025-03-01';

SELECT * FROM customers WHERE email = 'jane.doe@example.com';

-- Product inventory check
SELECT id, name, inventory_count FROM products WHERE id IN (42, 56, 78);

-- Recent customer sign-ups
SELECT * FROM customers WHERE created_at > '2025-04-01' ORDER BY created_at DESC;