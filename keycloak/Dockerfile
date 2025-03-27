FROM quay.io/keycloak/keycloak:20.0.3

# Add custom configurations
COPY realm-config /opt/keycloak/data/import/

# Enable features
ENV KC_FEATURES=token-exchange,admin-fine-grained-authz,declarative-user-profile
ENV KC_HTTP_RELATIVE_PATH=/auth
ENV KC_HEALTH_ENABLED=true

# Add custom startup options
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start-dev", "--import-realm"]
