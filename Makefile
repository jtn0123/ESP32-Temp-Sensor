# ESP32 Device Manager - Makefile
# Simple entry points for common operations

.PHONY: dev run help clean install check

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)ESP32 Device Manager$(NC)"
	@echo "$(CYAN)════════════════════$(NC)"
	@echo ""
	@echo "$(GREEN)Usage:$(NC)"
	@echo "  make <target>"
	@echo ""
	@echo "$(GREEN)Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make dev     - Start everything and open browser"
	@echo ""

dev: ## Start all services and open browser (recommended)
	@./scripts/run_device_manager.sh --open-browser

run: ## Start all services without opening browser
	@./scripts/run_device_manager.sh

dev-hot: ## Start with frontend hot-reload for development
	@./scripts/run_device_manager.sh --dev --open-browser

install: ## Install all dependencies
	@echo "$(CYAN)Installing dependencies...$(NC)"
	@python3 -m venv venv 2>/dev/null || true
	@. venv/bin/activate && pip install -q -r requirements.txt -r requirements-manager.txt 2>/dev/null || true
	@cd web/manager && npm install 2>/dev/null || true
	@echo "$(GREEN)Dependencies installed$(NC)"

build: ## Build the frontend for production
	@echo "$(CYAN)Building frontend...$(NC)"
	@cd web/manager && npm run build
	@echo "$(GREEN)Build complete$(NC)"

check: ## Run health check on services
	@echo "$(CYAN)Checking service health...$(NC)"
	@curl -s http://localhost:8080/api/health 2>/dev/null && echo "" || echo "$(RED)Backend not running$(NC)"

clean: ## Clean build artifacts and caches
	@echo "$(CYAN)Cleaning...$(NC)"
	@rm -rf web/manager/dist
	@rm -rf web/manager/node_modules/.cache
	@rm -rf __pycache__ scripts/__pycache__ scripts/device_manager/__pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean complete$(NC)"

logs: ## Show recent logs from the device manager
	@tail -f /tmp/device_manager.log 2>/dev/null || echo "$(YELLOW)No log file found$(NC)"

stop: ## Stop all running services
	@echo "$(CYAN)Stopping services...$(NC)"
	@pkill -f "start_device_manager.py" 2>/dev/null || true
	@pkill -f "mosquitto" 2>/dev/null || true
	@echo "$(GREEN)Services stopped$(NC)"

status: ## Show status of all services
	@echo "$(CYAN)Service Status$(NC)"
	@echo "$(CYAN)══════════════$(NC)"
	@echo -n "Backend (8080):  "; lsof -i :8080 >/dev/null 2>&1 && echo "$(GREEN)Running$(NC)" || echo "$(RED)Stopped$(NC)"
	@echo -n "MQTT (18884):    "; lsof -i :18884 >/dev/null 2>&1 && echo "$(GREEN)Running$(NC)" || echo "$(RED)Stopped$(NC)"
	@echo -n "Frontend (5173): "; lsof -i :5173 >/dev/null 2>&1 && echo "$(GREEN)Running$(NC)" || echo "$(YELLOW)Not started$(NC)"
