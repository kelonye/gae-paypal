test:
	@$(MAKE) test --no-print-directory -C test

example:
	@$(MAKE) --no-print-directory -C test

deps:
	@pip install -r requirements.txt

publish:
	@python setup.py sdist upload
	@$(MAKE) clean

clean:
	@rm -rf build dist gae_paypal.egg-info $(shell find -name '*.pyc')

.PHONY: clean publish deps example test
