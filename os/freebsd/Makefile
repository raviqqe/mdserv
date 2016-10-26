DESTDIR ?= /
PREFIX ?= usr/local
RCSCRIPT = ${DESTDIR}${PREFIX}/etc/rc.d/mdserv


all:
	@echo nothing to do

install:
	install -m 755 mdserv.rc ${RCSCRIPT}

uninstall:
	rm -rf ${RCSCRIPT}

.PHONY: all install uninstall
