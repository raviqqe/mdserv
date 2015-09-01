# makefile for mdserv, markdown http server

DESTDIR ?= /
PREFIX ?= usr/local
BINDIR = ${DESTDIR}${PREFIX}/bin
RCDIR = ${DESTDIR}${PREFIX}/etc/rc.d

BIN = ${BINDIR}/mdserv
RCSCRIPT = ${RCDIR}/mdserv

RM = rm -rf


all:
	@echo nothing to do

install: ${PROG_SRC}
	install -m 755 mdserv.py ${BIN}
	install -m 755 mdserv.rc ${RCSCRIPT}

deinstall: uninstall
uninstall:
	${RM} ${BIN} ${RCSCRIPT}

.PHONY: all install deinstall uninstall clean
