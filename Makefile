# Database management commands

.PHONY: db-test db-fresh help

# Test database connection
db-test:
	@echo "🔗 Testing database connection..."
	@python scripts/database/make-db-connect-test.py

# Initialize/rebuild fresh database
db-fresh:
	@echo "🔄 Setting up fresh database..."
	@python scripts/database/make-db-fresh.py

# Show available commands
help:
	@echo "Available commands:"
	@echo "  make db-test   - Test database connection"
	@echo "  make db-fresh  - Initialize/rebuild fresh database"
	@echo "  make help      - Show this help message"

# Default target
.DEFAULT_GOAL := help