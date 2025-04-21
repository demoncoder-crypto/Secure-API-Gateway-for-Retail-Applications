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

