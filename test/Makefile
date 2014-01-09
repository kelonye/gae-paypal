boot: lib
	@dev_appserver.py . --port 5000 --admin_port 7000 --clear_datastore

test: lib
	@python tests.py -f

lib:
	@ln -fs $(PWD)/$@ $@

.PHONY: test boot
