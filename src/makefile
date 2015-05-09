# makefile for mdserv, markdown http server

PREFIX = /usr/local
BINDIR = ${PREFIX}/bin
PROG = ${BINDIR}/mdserv

RM = rm -rf

all:
	@echo nothing to do

install: main.rb
	install -m 755 main.rb ${PROG}

deinstall: uninstall
uninstall:
	${RM} ${PROG}

.PHONY: all install deinstall uninstall
