include ../make/help.mk

.DEFAULT_GOAL := help

.PHONY: sample-request
sample-request: ## Run sample request
	xh POST localhost:8001/chat \
	    messages:='[{"role":"user","content":"Backlog の未完了課題を教えて"}]'

.PHONY: health-check
health-check: ## Run health check
	xh GET localhost:8001/health
