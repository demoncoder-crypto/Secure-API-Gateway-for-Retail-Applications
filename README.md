# Secure API Gateway for Retail Applications

A robust, secure API gateway designed specifically for retail applications, providing authentication, rate limiting, monitoring, and more.

## Features

- **Authentication & Authorization**: Integrated with Keycloak for robust OAuth2/OpenID Connect support
- **Rate Limiting**: Request rate limiting based on client identity
- **Monitoring & Logging**: Comprehensive logging and metrics collection with Prometheus and Grafana
- **High Security**: Protection against common API threats
- **Request Tracking**: Request ID propagation and correlation
- **Swagger Documentation**: Self-documenting API endpoints

## Architecture

The project consists of several components:

- **API Gateway**: A FastAPI application that routes requests to appropriate backend services
- **Keycloak**: Authentication and authorization server
- **Redis**: Used for rate limiting and caching
- **Prometheus & Grafana**: Monitoring and visualization
- **Mock Product Service**: A demo service for testing the gateway

## Prerequisites

- Docker and Docker Compose
- Git

## Quick Start

1. Clone the repository:
   ```
   git clone https://github.com/username/Secure-API-Gateway-for-Retail-Applications.git
   cd Secure-API-Gateway-for-Retail-Applications
   ```

2. Start the services:
   ```
   cd infrastructure
   docker-compose up -d
   ```

3. Access the services:
   - API Gateway: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Keycloak Admin: http://localhost:8080/admin (username: admin, password: admin)
   - Grafana: http://localhost:3000 (username: admin, password: admin)
   - Prometheus: http://localhost:9090

## Development Setup

### API Gateway Development

To develop the API Gateway:

1. Install Python 3.9+ and required packages:
   ```
   cd api-gateway
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the `infrastructure` directory with appropriate settings.

3. Run the API Gateway locally:
   ```
   cd api-gateway
   python main.py
   ```

## Testing

To run tests:

```
cd api-gateway
pytest
```

## API Documentation

When the API Gateway is running, visit `http://localhost:8000/docs` to see the interactive API documentation.

## Environment Variables

Key environment variables that can be configured:

| Variable | Description | Default |
|----------|-------------|---------|
| APP_ENVIRONMENT | Environment (development, production) | development |
| LOG_LEVEL | Logging level | INFO |
| REDIS_URL | Redis connection URL | redis://redis:6379/0 |
| OIDC_URL | Keycloak URL | http://keycloak:8080/auth |

## Security Considerations

- The API Gateway uses secure defaults and follows OWASP API security best practices
- Authentication is implemented using industry-standard OAuth2/OIDC
- All connections should use HTTPS in production
- Rate limiting helps prevent abuse and DoS attacks

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- FastAPI for the excellent API framework
- Keycloak for robust identity and access management
- The entire open-source community

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 