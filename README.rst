======================================================
  The JoPlot_ cluster usage reporting interface
======================================================

.. contents::

Introduction
============

JoPlot_ is a simple web interface for reporting and graphing PBS
accounting data of the PHOENIX cluster. It is VO- and VOMS-aware and can thus
aggregate data by VO or by VO and VOMS Role. Data can be plotted on a daily,
monthly or yearly basis. The web interface is intended to provide just minimal
functionality, and be self-explanatory.

The web interface is available at https://mon.lcg.cscs.ch/pbsplots/ To
access the web interface, a valid Grid certificate must be loaded in the
browser: only authorized people can access the web interface. At the moment of
this writing, the list of authorized DNs include all DNs registered in the
ATLAS, CMS and LHCb VOs at 2010-01-15; note there is no automated update of
the authorized DN list.

The web interface is just an HTML GUI on top of MySQL_ database queries;
for each VO/Role combination a SQL query must be issued. At the time of this
writing, a single query can take up to 10 seconds per VO/Role combo per month;
therefore yearly queries over many VO/Role combinations can easily result in
internal CGI timeouts ("Internal server error").


Maintenance and HOW-TOs
=======================

How to restrict view to authorized people
-----------------------------------------

JoPlot_ does not perform any kind of authorization by itself: it
relies on the web server to perform the screening and autorization of
users. 

An example configuration snippet for the `Apache webserver`_ file is
provided as file ``etc/joplot.apache.conf``


How to change the UNIX user/group to VO/Role mapping
----------------------------------------------------

JoPlot_ gathers its information from the TORQUE/PBS logs, which keep no
trace of the Grid-level credentials used for job submission. Therefore, a
mapping mechanism must be implemented, that deduces the Grid level information
(VO, VOMS Role) from the UNIX-level user and group ID.

This mapping is implemented in the function
``creds_to_vo_and_role_map`` in file
``/opt/cscs/libexec/pbsplots/pbslogs2sql.py``.  There is currently no
way of configuring this mapping other than altering this file;
however, the code should be fairly easy to modify.

**Note:** The mapping function is only run _when data is injected into the
database._ Modifications to the mapping function will only affect new DB
entries (jobs running from the day after onwards). To retroactively update
entries, one must reload _all_ TORQUE log files into the database. (The
``pbslogs2sql.py`` script is idem-potent, so it does not hurt to run it many
times over the same log file.)


JoPlot developers' info
=======================

Architecture
------------

JoPlot_ consists of 2 scripts:

  * the log injector ``pbsplots2sql.py``, which reads the TORQUE log files
specified on the command-line, parses them, and loads the results into a
MySQL_ database

  * the web interface ``pbsplots.py``, which runs as a CGI script, connecting to
the MySQL_ DB and displaying the results as a HTML page.

The ``pbslogs2sql.py`` script is designed to run on the TORQUE/PBS
server (or any host that can access the PBS/TORQUE server logs) and
stores the data in a MySQL_ database. 

The ``pbsplots.py`` CGI script can run on any host that has access to the
MySQL_ database.

The ``pbslogs2sql.py`` runs once a day (e.g., 10 minutes after
midnight) and parses the TORQUE logs from the previous day, injecting
the results in the database.


Current deployment and how to install new versions
--------------------------------------------------

All the scripts and configuration files are `hosted on GitHub`_::

      # grab a copy of the current sources
      git clone http://github.com/riccardomurri/joplot

The GIT repository tracks all the files needed for a working installation of
JoPlot_:

  * ``pbsplots.py`` the CGI script;

  * ``pbsplots.template.html`` the HTML page template (uses Python
``%=-formatting conventions; use =%%`` to get a literal percent sign);

  * ``pbslogs2sql.py`` the DB data injection script;

  * ``pbsplots.cron`` crontab snippet for running the injection script nightly;

  * ``pbsplots.ini`` DB connection parameters;

  * ``pbsplots.apache.conf`` Apache configuration snippet; link it from
``/etc/httpd/conf.d/pbsplots.conf`` (in addition, the ``htpasswd.users`` file
needs to be created; see section "How to authorise a new user" above).

Installation on the PBS/TORQUE server and the HTTP+MySQL server can be
done by checking out a copy of the repository:

  * on the HTTP+MySQL server in directory ``/var/www/html/pbsplots``

  * on the PBS/TORQUE server, in any directory from whence the
  ``pbslog2sql.py`` script can be executed from a cron job.

You should indeed setup a cron job (e.g., symlink to
``pbslogs2sql.cron``) to run nightly on the PBS/TORQUE server (e.g. at
00:15) and import the PBS accounting data from the day before into the
DB on the MySQL server.


-- Riccardo Murri - 2012-01-18


.. References

.. _JoPlot: http://github.com/riccardomurri/joplot
.. _MySQL: http://www.mysql.com
.. _SQLite: http://www.sqlite.org
.. _GitHub: http://github.com/
.. _`Apache webserver`: http://www.apache.org/
