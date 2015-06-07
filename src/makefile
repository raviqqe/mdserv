# makefile for mdserv, markdown http server

PREFIX = /usr/local
BINDIR = ${PREFIX}/bin
PROG_SRC = main.py
PROG = ${BINDIR}/mdserv

RM = rm -rf

all:
	@echo nothing to do

install: ${PROG_SRC}
	install -m 755 ${PROG_SRC} ${PROG}

deinstall: uninstall
uninstall:
	${RM} ${PROG}

.PHONY: all install deinstall uninstall clean
