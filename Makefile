.PHONY: init run test clean demo
init:
	bash scripts/init_ca.sh
run:
	python3 run.py
test:
	python3 -m unittest discover tests -v
demo:
	bash scripts/demo.sh
clean:
	rm -rf pki/*/private/* pki/*/certs/* pki/*/crl/* pki/*/db/* pki/*/newcerts/* pki/leaf/csr/*
