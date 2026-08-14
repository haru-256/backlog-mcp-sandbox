include ../make/help.mk

.DEFAULT_GOAL := help

.PHONY: sample-request
sample-request: ## Run sample chat request
	xh POST localhost:8004/chat \
	    user_id=demo-user \
	    org_id=demo-org \
	    messages:='[{"role":"user","content":"Backlog の未完了課題を教えて"}]'

.PHONY: health-check
health-check: ## Run health check
	xh GET localhost:8004/health
