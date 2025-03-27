const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { v4: uuidv4 } = require('uuid');
const morgan = require('morgan');

// Initialize Express
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(morgan('combined'));

// Mock database
let products = [
  {
    id: '1',
    name: 'Smartphone X',
    description: 'Latest smartphone with advanced features',
    price: 999.99,
    category: 'Electronics',
    inStock: true,
    imageUrl: 'https://example.com/smartphone.jpg'
  },
  {
    id: '2',
    name: 'Laptop Pro',
    description: 'High-performance laptop for professionals',
    price: 1499.99,
    category: 'Electronics',
    inStock: true,
    imageUrl: 'https://example.com/laptop.jpg'
  },
  {
    id: '3',
    name: 'Wireless Headphones',
    description: 'Premium noise-cancelling headphones',
    price: 299.99,
    category: 'Audio',
    inStock: true,
    imageUrl: 'https://example.com/headphones.jpg'
  },
  {
    id: '4',
    name: 'Smart Watch',
    description: 'Fitness and health tracking smart watch',
    price: 249.99,
    category: 'Wearables',
    inStock: false,
    imageUrl: 'https://example.com/smartwatch.jpg'
  },
  {
    id: '5',
    name: 'Bluetooth Speaker',
    description: 'Portable waterproof speaker with great sound',
    price: 129.99,
    category: 'Audio',
    inStock: true,
    imageUrl: 'https://example.com/speaker.jpg'
  }
];

// Routes
// Health check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', service: 'product-service' });
});

// Get all products
app.get('/products', (req, res) => {
  res.json(products);
});

// Get product by ID
app.get('/products/:id', (req, res) => {
  const product = products.find(p => p.id === req.params.id);
  
  if (!product) {
    return res.status(404).json({ message: 'Product not found' });
  }
  
  res.json(product);
});

// Create new product
app.post('/products', (req, res) => {
  const newProduct = {
    id: uuidv4(),
    ...req.body,
    createdAt: new Date().toISOString()
  };
  
  products.push(newProduct);
  
  res.status(201).json(newProduct);
});

// Update product
app.put('/products/:id', (req, res) => {
  const productIndex = products.findIndex(p => p.id === req.params.id);
  
  if (productIndex === -1) {
    return res.status(404).json({ message: 'Product not found' });
  }
  
  const updatedProduct = {
    ...products[productIndex],
    ...req.body,
    id: req.params.id,
    updatedAt: new Date().toISOString()
  };
  
  products[productIndex] = updatedProduct;
  
  res.json(updatedProduct);
});

// Delete product
app.delete('/products/:id', (req, res) => {
  const productIndex = products.findIndex(p => p.id === req.params.id);
  
  if (productIndex === -1) {
    return res.status(404).json({ message: 'Product not found' });
  }
  
  products.splice(productIndex, 1);
  
  res.status(200).json({ message: 'Product deleted successfully' });
});

// Search products
app.get('/products/search', (req, res) => {
  const { query, category } = req.query;
  
  let filteredProducts = [...products];
  
  if (query) {
    const searchQuery = query.toLowerCase();
    filteredProducts = filteredProducts.filter(
      p => p.name.toLowerCase().includes(searchQuery) || 
           p.description.toLowerCase().includes(searchQuery)
    );
  }
  
  if (category) {
    filteredProducts = filteredProducts.filter(
      p => p.category.toLowerCase() === category.toLowerCase()
    );
  }
  
  res.json(filteredProducts);
});

// Start server
app.listen(PORT, () => {
  console.log(`Product service running on port ${PORT}`);
});