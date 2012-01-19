#!/bin/bash
(cd /opt/cscs/libexec/pbsplots && ./pbslogs2sql.py -H mon.lcg.cscs.ch -u pbs -D pbs /var/spool/pbs/server_priv/accounting/`perl -e 'use POSIX qw(strftime); print strftime("%Y%m%d", localtime(time()-86400));'`)
