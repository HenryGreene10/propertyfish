.PHONY: check

check:
	python -m pytest -q
	python scripts/join_pipeline.py --enforce-stage1 0.8
