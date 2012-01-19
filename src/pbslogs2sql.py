#! /usr/bin/env python
#
"""Parse PBS accounting logs and inject the results in a DB.

Only job exit (E) lines are parsed, any other event is silently
ignored.  Example line::

  11/23/2009 00:00:00;E;2931170.ce01.lcg.cscs.ch;user=atlasplt group=atlas jobname=STDIN queue=egee48h ctime=1258930667 qtime=1258930667 etime=1258930667 start=1258930691 owner=atlasplt@ce01.lcg.cscs.ch exec_host=wn14.lcg.cscs.ch/7 Resource_List.cput=48:00:00 Resource_List.mem=2000mb Resource_List.neednodes=1 Resource_List.nodect=1 Resource_List.nodes=1 Resource_List.walltime=60:00:00 session=13810 end=1258930800 Exit_status=0 resources_used.cput=00:00:04 resources_used.mem=26312kb resources_used.vmem=253280kb resources_used.walltime=00:01:49

Results are written to DB 'pbs.db', in a table 'accounting'
which is created according to the following spec::

  CREATE TABLE accounting (
    jobid         VARCHAR(32) PRIMARY KEY,
    date          DATE NOT NULL,
    timestamp     INTEGER UNSIGNED,
    user          VARCHAR(32),
    vo            VARCHAR(32),
    role          VARCHAR(32),
    queue         VARCHAR(16),
    start_time    INTEGER UNSIGNED,
    end_time      INTEGER UNSIGNED,
    wn            VARCHAR(5),
    req_cputime   INTEGER UNSIGNED,
    req_walltime  INTEGER UNSIGNED,
    req_mem       BIGINT UNSIGNED,
    used_cputime  INTEGER UNSIGNED,
    used_walltime INTEGER UNSIGNED,
    used_mem      BIGINT UNSIGNED,
    used_vmem     BIGINT UNSIGNED,
    exit_status   INTEGER
  );

A MySQL db can be created with::

  mysql> create user 'pbs'@'ce01.lcg.cscs.ch' IDENTIFIED BY 'TheVerySecretPassword';
  mysql> GRANT ALL PRIVILEGES ON pbs.* TO 'pbs'@'ce01.lcg.cscs.ch' IDENTIFIED BY 'TheVerySecretPassword';

"""
__docformat__ = 'reStructuredText'


# customize the following to fit the current config
def creds_to_vo_and_role_map(user, group):
    """
    Given a pair `(user, group)` return a tuple `(vo, role)`
    comprising the VO and the VOMS role that are mapped to it.
    """
    # ATLAS
    if user=='atlasprd':
        return ('atlas', 'production')
    elif user=='atlasplt':
        return ('atlas', 'pilot')
    elif user=='nordugrid' or group=='nordugrid' or group=='atlas':
        return ('atlas', 'NULL')
    # CMS
    elif group=='prdcms':
        return ('cms', 'production')
    elif group=='pricms':
        return ('cms', 'priorityuser')
    elif group=='cms':
        return ('cms', 'NULL')
    # LHCb
    elif user=='lhcbprd':
        return ('lhcb', 'production')
    elif group=='lhcb':
        return ('lhcb', 'NULL')
    # if a (user,group) pair is not found in the table above,
    # then the group name is considered to be a VO name and
    # returned unchanged.
    else:
        return (group, 'NULL')


import sys

## parse command line
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-f", "--config", dest="config_file", default=None,
                  help="read DB connection parameters from this file (overrides other command-line options")
parser.add_option("-c", "--create-table", dest="create", 
                  action="store_true", default=False,
                  help="Create DB table to hold accounting data")
parser.add_option("-e", "--db-engine", dest="engine", default="mysql",
                  help="which database backend to use: mysql/sqlite")
parser.add_option("-D", "--db", dest="db",
                  help="connect to database DB", metavar="DB")
parser.add_option("-H", "--host", dest="host",
                  help="database server host")
parser.add_option("-u", "--user", dest="user", default="testme",
                  help="user for connecting to the database")
parser.add_option("-p", "--password", dest="passwd", default="TheVerySecretPassword",
                  help="password to connect to database")
(options, args) = parser.parse_args()


## import SQL
if options.engine == 'mysql':
    import MySQLdb as sql
    if options.host is None:
        options.host = 'localhost'
    if options.db is None:
        options.db = 'pbs'
elif options.engine == 'sqlite':
    import sqlite as sql
    if options.db is None:
        options.db = 'pbs.db'
else:
    sys.stderr.write('Unknown value for "--engine" option: %s,'
                     ' valid values are: mysql, sqlite' % options.engine)

if options.config_file:
    # get configuration options
    from ConfigParser import SafeConfigParser
    config = SafeConfigParser()
    config.read(options.config_file)
    options.db = config.get('database', 'db')
    options.user = config.get('database', 'user')
    options.host = config.get('database', 'host')
    options.passwd = config.get('database', 'password')


## main: run tests

# initialize DB
if options.engine == 'mysql':
    conn = sql.connect(host=options.host, user=options.user, 
                       passwd=options.passwd, db=options.db)
else: # sqlite
    conn = sql.connect(options.db, autocommit=0)
db = conn.cursor()
# XXX: SQLite-specific syntax?
if options.create:
                      db.execute("""
CREATE TABLE IF NOT EXISTS accounting (
  jobid         VARCHAR(32) PRIMARY KEY,
  date          DATE NOT NULL,
  timestamp     INTEGER UNSIGNED,
  user          VARCHAR(32),
  vo            VARCHAR(32),
  role          VARCHAR(32),
  queue         VARCHAR(16),
  start_time    INTEGER UNSIGNED,
  end_time      INTEGER UNSIGNED,
  wn            VARCHAR(4),
  req_cputime   INTEGER UNSIGNED,
  req_walltime  INTEGER UNSIGNED,
  req_mem       BIGINT UNSIGNED,
  used_cputime  INTEGER UNSIGNED,
  used_walltime INTEGER UNSIGNED,
  used_mem      BIGINT UNSIGNED,
  used_vmem     BIGINT UNSIGNED,
  exit_status   INTEGER,
  INDEX (vo),
  INDEX (role)
);
""")


class Record(object):
    
    ATTRS_TO_COLUMNS_MAP = {
        'Exit_status':'exit_status',
        'Resource_List.cput':'req_cputime',
        'Resource_List.mem':'req_mem',
        'Resource_List.pmem':None,
        'Resource_List.pvmem':None,
        'Resource_List.vmem':None,
        'Resource_List.neednodes':None,
        'Resource_List.nodect':None,
        'Resource_List.nodes':None,
        'Resource_List.walltime':'req_walltime',
        'ctime':None,
        'end':'end_time',
        'etime':'timestamp',
        'exec_host':'wn',
        'group':'group',
        'jobname':None,
        'owner':None,
        'queue':'queue',
        'qtime':None,
        'resources_used.cput':'used_cputime',
        'resources_used.mem':'used_mem',
        'resources_used.vmem':'used_vmem',
        'resources_used.walltime':'used_walltime',
        'session':None,
        'start':'start_time',
        'user':'user',
        }

    def __init__(self, jobid, timestamp, attrs):
        self.jobid = jobid
        
        # provide defaults
        self.req_mem = '0'
        self.req_cputime = '0:00:00'
        self.req_walltime = '0:00:00'

        # parse timestamp 
        date, time = timestamp.split()
        month, day, year = date.split("/")
        self.date = '%s-%s-%s' % (year, month, day)
        
        # parse attrs
        for kv in attrs.split():
            key, val = kv.split("=")
            try:
                key = Record.ATTRS_TO_COLUMNS_MAP[key]
            except KeyError: # no mapping, keep "key" unchanged
                pass
            if key is not None:
                setattr(self, key, val)

        # check required fields
        for attr in ['used_mem', 'used_vmem', 'used_cputime', 'used_walltime']:
            if not hasattr(self, attr):
                raise ValueError("missing required attribute '%s'" % attr)

        # only keep hostname for WNs
        self.wn = self.wn.split(".")[0]

        # convert group names to VO names
        self.vo, self.role = creds_to_vo_and_role_map(self.user, self.group)
                
        # convert memory units
        def to_bytes(val):
            if 'b' != val[-1]:
                return int(val)
            val = val[:-1] # strip off last char
            if 'k' == val[-1]:
                return int(val[:-1]) * 1024
            elif 'm' == val[-1]:
                return int(val[:-1]) * 1024 * 1024
            elif 'g' == val[-1]:
                return int(val[:-1]) * 1024 * 1024 * 1024
            return int(val)
        for attr in ['req_mem', 'used_mem', 'used_vmem']:
            setattr(self, attr, to_bytes(getattr(self, attr)))

        # convert time units
        def to_seconds(val):
            hrs, mins, secs = val.split(":")
            return (int(hrs)*3600 + int(mins)*60 + int(secs))
        for attr in ['req_cputime', 'req_walltime', 'used_cputime', 'used_walltime']:
            setattr(self, attr, to_seconds(getattr(self, attr)))


    def write(self, db):
        db.execute("REPLACE"
               " INTO accounting (jobid, date, timestamp, user, vo, role, queue, start_time, end_time, wn, req_cputime, req_walltime, req_mem, used_cputime, used_walltime, used_mem, used_vmem, exit_status)"
               " VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s', '%s')"
               % (self.jobid, self.date, self.timestamp, self.user, self.vo, self.role, self.queue, self.start_time, self.end_time, self.wn, self.req_cputime, self.req_walltime, self.req_mem, self.used_cputime, self.used_walltime, self.used_mem, self.used_vmem, self.exit_status))


# let's go
for filename in args:
    logfile = open(filename, 'r')
    for line in logfile:
        timestamp, kind, jobid, attrs = line.split(";")
        if kind != 'E':
            continue # with next line
        try:
            Record(jobid, timestamp, attrs).write(db)
        except ValueError, x:
            sys.stderr.write("Incomplete record: job %s at %s: %s\n" % (jobid, timestamp, x))


# done
if options.engine == 'sqlite':
    # actually write to DB
    conn.commit()
db.close()
conn.close()
